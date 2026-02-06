from flask import Blueprint, jsonify, request, session
from CTFd.cache import cache
from CTFd.models import db, Users, Challenges
from CTFd.utils.decorators import authed_only, admins_only
from .models import ProxmoxVM, ChallengeVM, ProxmoxGlobalConfig
from .proxmox_api import ProxmoxManager
from datetime import datetime, timedelta

proxmox_blueprint = Blueprint('proxmox', __name__)

ADMIN_VM_CACHE_KEY = 'proxmox_admin_vm_list'
ADMIN_VM_CACHE_TTL = 30  # seconds


# ---------------------------------------------------------------------------
# User routes — all per-user (no challenge_id), one VM shared across all
# ---------------------------------------------------------------------------

@proxmox_blueprint.route('/vm/create', methods=['POST'])
@authed_only
def create_vm():
    user_id = session['id']

    config = ProxmoxGlobalConfig.query.first()
    if not config:
        return jsonify({'success': False, 'error': 'VM system not configured yet'}), 503

    existing = ProxmoxVM.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({'success': False, 'error': 'VM already exists', 'vm': existing.to_dict()}), 400

    pm = ProxmoxManager()
    try:
        vmid = pm.clone_template(config.proxmox_template_id, user_id)

        vm = ProxmoxVM(
            user_id=user_id,
            proxmox_vmid=vmid,
            vm_name=f'ctfd-u{user_id}',
            status='creating',
            expires_at=datetime.utcnow() + timedelta(hours=config.max_duration_hours),
            ctfd_managed=True,
        )
        db.session.add(vm)
        db.session.commit()

        pm.start_vm(vmid)
        vm.status = 'running'
        vm.last_started = datetime.utcnow()
        db.session.commit()

        cache.delete(ADMIN_VM_CACHE_KEY)
        return jsonify({'success': True, 'vm': vm.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@proxmox_blueprint.route('/vm/status', methods=['GET'])
@authed_only
def get_vm_status():
    user_id = session['id']

    vm = ProxmoxVM.query.filter_by(user_id=user_id).first()
    if not vm:
        return jsonify({'success': False, 'error': 'No VM found'}), 404

    pm = ProxmoxManager()
    try:
        status = pm.get_vm_status(vm.proxmox_vmid)
        vm.status = status['status']

        if status['status'] == 'running':
            ip = pm.get_vm_ip(vm.proxmox_vmid)
            if ip:
                vm.vm_ip = ip

        db.session.commit()
        return jsonify({'success': True, 'vm': vm.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@proxmox_blueprint.route('/vm/power/<action>', methods=['POST'])
@authed_only
def vm_power_action(action):
    user_id = session['id']

    if action not in ('start', 'stop', 'restart'):
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

    vm = ProxmoxVM.query.filter_by(user_id=user_id).first()
    if not vm:
        return jsonify({'success': False, 'error': 'VM not found'}), 404

    if vm.expires_at and datetime.utcnow() > vm.expires_at:
        return jsonify({'success': False, 'error': 'VM has expired'}), 403

    pm = ProxmoxManager()
    try:
        if action == 'start':
            pm.start_vm(vm.proxmox_vmid)
            vm.status = 'running'
            vm.last_started = datetime.utcnow()
        elif action == 'stop':
            pm.stop_vm(vm.proxmox_vmid)
            vm.status = 'stopped'
        elif action == 'restart':
            pm.restart_vm(vm.proxmox_vmid)
            vm.status = 'running'
            vm.last_started = datetime.utcnow()

        db.session.commit()
        return jsonify({'success': True, 'vm': vm.to_dict()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@proxmox_blueprint.route('/vnc', methods=['POST'])
@authed_only
def get_vnc_connection():
    """Return a one-time VNC ticket + WebSocket URL for noVNC."""
    user_id = session['id']

    vm = ProxmoxVM.query.filter_by(user_id=user_id).first()
    if not vm:
        return jsonify({'success': False, 'error': 'No VM found'}), 404
    if vm.status != 'running':
        return jsonify({'success': False, 'error': 'VM is not running'}), 400

    pm = ProxmoxManager()
    try:
        vnc = pm.get_vnc_ticket(vm.proxmox_vmid)
        host = pm.config.PROXMOX_HOST
        node = pm.config.PROXMOX_NODE
        vmid = vm.proxmox_vmid
        port = vnc['port']
        ticket = vnc['ticket']

        ws_url = (
            f"wss://{host}:8006/api2/json/nodes/{node}"
            f"/qemu/{vmid}/vncwebsocket?port={port}&vncticket={ticket}"
        )
        return jsonify({
            'success': True,
            'ws_url': ws_url,
            'ticket': ticket,
            'proxmox_host': host,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@proxmox_blueprint.route('/admin/config', methods=['GET'])
@admins_only
def admin_get_config():
    config = ProxmoxGlobalConfig.query.first()
    if config:
        return jsonify({
            'success': True,
            'config': {
                'proxmox_template_id': config.proxmox_template_id,
                'vm_template_name': config.vm_template_name,
                'max_duration_hours': config.max_duration_hours,
            },
        })
    return jsonify({'success': True, 'config': None})


@proxmox_blueprint.route('/admin/config', methods=['POST'])
@admins_only
def admin_set_config():
    data = request.get_json() or request.form

    config = ProxmoxGlobalConfig.query.first()
    if not config:
        config = ProxmoxGlobalConfig(proxmox_template_id=0)
        db.session.add(config)

    config.proxmox_template_id = int(data.get('proxmox_template_id', 0))
    config.vm_template_name = data.get('vm_template_name', 'CTFd VM')
    config.max_duration_hours = int(data.get('max_duration_hours', 4))

    db.session.commit()
    return jsonify({'success': True})


@proxmox_blueprint.route('/admin/challenges', methods=['GET'])
@admins_only
def admin_list_challenges():
    """Return all challenges with their VM-enabled flag."""
    challenges = Challenges.query.order_by(Challenges.id).all()
    enabled_ids = {
        row.challenge_id
        for row in ChallengeVM.query.with_entities(ChallengeVM.challenge_id).all()
    }
    result = []
    for c in challenges:
        result.append({
            'id': c.id,
            'name': c.name,
            'category': c.category,
            'vm_enabled': c.id in enabled_ids,
        })
    return jsonify({'success': True, 'challenges': result})


@proxmox_blueprint.route('/admin/challenges/<int:challenge_id>/vm', methods=['POST'])
@admins_only
def admin_toggle_challenge_vm(challenge_id):
    data = request.get_json() or request.form
    enabled = str(data.get('enabled', 'false')).lower() in ('true', '1', 'yes')

    existing = ChallengeVM.query.filter_by(challenge_id=challenge_id).first()
    if enabled and not existing:
        db.session.add(ChallengeVM(challenge_id=challenge_id))
        db.session.commit()
    elif not enabled and existing:
        db.session.delete(existing)
        db.session.commit()

    return jsonify({'success': True, 'vm_enabled': enabled})


@proxmox_blueprint.route('/admin/vms', methods=['GET'])
@admins_only
def admin_list_vms():
    cached = cache.get(ADMIN_VM_CACHE_KEY)
    if cached is not None:
        return jsonify({'success': True, 'vms': cached})

    pm = ProxmoxManager()
    vms = ProxmoxVM.query.filter_by(ctfd_managed=True).all()

    vm_data = []
    for vm in vms:
        try:
            status = pm.get_vm_status(vm.proxmox_vmid)
            vm.status = status['status']
            if status['status'] == 'running':
                ip = pm.get_vm_ip(vm.proxmox_vmid)
                if ip:
                    vm.vm_ip = ip
            db.session.commit()
        except Exception:
            pass

        user = Users.query.get(vm.user_id)
        vm_dict = vm.to_dict()
        vm_dict['username'] = user.name if user else 'Unknown'
        vm_data.append(vm_dict)

    cache.set(ADMIN_VM_CACHE_KEY, vm_data, timeout=ADMIN_VM_CACHE_TTL)
    return jsonify({'success': True, 'vms': vm_data})


@proxmox_blueprint.route('/admin/vm/power/<int:vm_id>/<action>', methods=['POST'])
@admins_only
def admin_vm_power(vm_id, action):
    if action not in ('start', 'stop', 'restart', 'delete'):
        return jsonify({'success': False, 'error': 'Invalid action'}), 400

    vm = ProxmoxVM.query.get(vm_id)
    if not vm or not vm.ctfd_managed:
        return jsonify({'success': False, 'error': 'VM not found'}), 404

    pm = ProxmoxManager()
    try:
        if action == 'start':
            pm.start_vm(vm.proxmox_vmid)
            vm.status = 'running'
        elif action == 'stop':
            pm.stop_vm(vm.proxmox_vmid)
            vm.status = 'stopped'
        elif action == 'restart':
            pm.restart_vm(vm.proxmox_vmid)
            vm.status = 'running'
        elif action == 'delete':
            pm.delete_vm(vm.proxmox_vmid)
            db.session.delete(vm)

        db.session.commit()
        cache.delete(ADMIN_VM_CACHE_KEY)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
