import logging
import time

from proxmoxer import ProxmoxAPI

from .config import ProxmoxConfig

logger = logging.getLogger(__name__)

CLONE_POLL_INTERVAL = 2   # seconds between status checks
CLONE_TIMEOUT = 300       # max seconds to wait for clone to finish


class ProxmoxManager:
    def __init__(self):
        self.config = ProxmoxConfig()
        self.proxmox = ProxmoxAPI(
            self.config.PROXMOX_HOST,
            user=self.config.PROXMOX_USER,
            token_name=self.config.PROXMOX_TOKEN_NAME,
            token_value=self.config.PROXMOX_TOKEN_VALUE,
            verify_ssl=self.config.PROXMOX_VERIFY_SSL
        )
        self.node = self.config.PROXMOX_NODE

    def clone_template(self, template_id, user_id):
        new_vmid = self.proxmox.cluster.nextid.get()
        upid = self.proxmox.nodes(self.node).qemu(template_id).clone.post(
            newid=new_vmid,
            name=f'ctfd-u{user_id}',
            full=0,
            description=f'CTFd VM for user {user_id}'
        )
        self._wait_for_task(upid)
        return new_vmid

    def _wait_for_task(self, upid):
        elapsed = 0
        while elapsed < CLONE_TIMEOUT:
            task = self.proxmox.nodes(self.node).tasks(upid).status.get()
            if task.get('status') == 'stopped':
                if task.get('exitstatus') != 'OK':
                    raise RuntimeError(
                        f"Proxmox task {upid} failed: {task.get('exitstatus')}"
                    )
                return
            time.sleep(CLONE_POLL_INTERVAL)
            elapsed += CLONE_POLL_INTERVAL
        raise TimeoutError(
            f"Proxmox task {upid} did not complete within {CLONE_TIMEOUT}s"
        )

    def start_vm(self, vmid):
        return self.proxmox.nodes(self.node).qemu(vmid).status.start.post()

    def stop_vm(self, vmid):
        return self.proxmox.nodes(self.node).qemu(vmid).status.shutdown.post()

    def restart_vm(self, vmid):
        return self.proxmox.nodes(self.node).qemu(vmid).status.reboot.post()

    def delete_vm(self, vmid):
        try:
            status = self.get_vm_status(vmid)
            if status['status'] == 'running':
                self.stop_vm(vmid)
                time.sleep(5)
        except Exception as e:
            logger.warning("Error checking/stopping VM %s before delete: %s", vmid, e)
        return self.proxmox.nodes(self.node).qemu(vmid).delete()

    def get_vm_status(self, vmid):
        status = self.proxmox.nodes(self.node).qemu(vmid).status.current.get()
        return {
            'status': status['status'],
            'uptime': status.get('uptime', 0),
        }

    def get_vm_ip(self, vmid):
        try:
            interfaces = self.proxmox.nodes(self.node).qemu(vmid).agent(
                'network-get-interfaces'
            ).get()
            for iface in interfaces['result']:
                if iface['name'] in ['eth0', 'ens18', 'ens19', 'ens3']:
                    for addr in iface.get('ip-addresses', []):
                        if (addr['ip-address-type'] == 'ipv4'
                                and not addr['ip-address'].startswith('127.')):
                            return addr['ip-address']
            return None
        except Exception as e:
            logger.debug("Could not get IP for VM %s: %s", vmid, e)
            return None

    def get_vnc_ticket(self, vmid):
        """Get a one-time VNC ticket from Proxmox for noVNC connection."""
        result = self.proxmox.nodes(self.node).qemu(vmid).vncproxy.post()
        return {
            'port': result['port'],
            'ticket': result['ticket'],
        }
