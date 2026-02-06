from flask import render_template
from CTFd.plugins import register_plugin_assets_directory, register_admin_plugin_menu_bar, register_admin_plugin_script
from CTFd.utils.decorators import admins_only
from .models import ProxmoxVM, ChallengeVM, ProxmoxGlobalConfig
from .routes import proxmox_blueprint


def load(app):
    app.db.create_all()
    app.register_blueprint(proxmox_blueprint, url_prefix='/proxmox')
    register_plugin_assets_directory(app, base_path="/plugins/proxmox_vms/assets/")
    register_admin_plugin_menu_bar(title='Proxmox VMs', route='/admin/proxmox-vms')
    register_admin_plugin_script('/plugins/proxmox_vms/assets/admin_challenge_vm_toggle.js')

    @app.context_processor
    def inject_vm_control():
        def challenge_has_vm(challenge_id):
            return ChallengeVM.query.filter_by(challenge_id=challenge_id).first() is not None
        return dict(challenge_has_vm=challenge_has_vm)

    @app.route('/admin/proxmox-vms')
    @admins_only
    def admin_proxmox_vms():
        return render_template(
            'plugins/proxmox_vms/templates/proxmox_vms/admin_vm_management.html'
        )

    print("[+] Proxmox VM Plugin loaded successfully")
