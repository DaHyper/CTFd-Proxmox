#!/usr/bin/env python3
"""Cron job: delete expired user VMs from Proxmox and the DB."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CTFd import create_app
from CTFd.models import db
from CTFd.plugins.proxmox_vms.models import ProxmoxVM
from CTFd.plugins.proxmox_vms.proxmox_api import ProxmoxManager

app = create_app()
with app.app_context():
    pm = ProxmoxManager()
    expired = ProxmoxVM.query.filter(
        ProxmoxVM.expires_at <= datetime.utcnow(),
        ProxmoxVM.ctfd_managed == True,
    ).all()
    print(f"[{datetime.utcnow()}] Deleting {len(expired)} expired VMs")
    for vm in expired:
        try:
            pm.delete_vm(vm.proxmox_vmid)
            db.session.delete(vm)
            db.session.commit()
            print(f"  OK Deleted VM {vm.proxmox_vmid} (user {vm.user_id})")
        except Exception as e:
            print(f"  FAIL VM {vm.proxmox_vmid}: {e}")
