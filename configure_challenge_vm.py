#!/usr/bin/env python3
"""CLI helper: toggle VM on a challenge, or set global template config."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from CTFd import create_app
from CTFd.models import db
from CTFd.plugins.proxmox_vms.models import ChallengeVM, ProxmoxGlobalConfig


def set_global_config(template_id, name, hours):
    app = create_app()
    with app.app_context():
        config = ProxmoxGlobalConfig.query.first()
        if not config:
            config = ProxmoxGlobalConfig(proxmox_template_id=template_id)
            db.session.add(config)
        config.proxmox_template_id = template_id
        config.vm_template_name = name
        config.max_duration_hours = hours
        db.session.commit()
        print(f"OK Global config: template={template_id} name={name} hours={hours}")


def toggle_challenge(challenge_id, enable):
    app = create_app()
    with app.app_context():
        existing = ChallengeVM.query.filter_by(challenge_id=challenge_id).first()
        if enable and not existing:
            db.session.add(ChallengeVM(challenge_id=challenge_id))
            db.session.commit()
            print(f"OK VM enabled for challenge {challenge_id}")
        elif not enable and existing:
            db.session.delete(existing)
            db.session.commit()
            print(f"OK VM disabled for challenge {challenge_id}")
        else:
            state = "enabled" if existing else "disabled"
            print(f"No change — challenge {challenge_id} VM already {state}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 configure_challenge_vm.py config <template_vmid> <name> <hours>")
        print("  python3 configure_challenge_vm.py enable  <challenge_id>")
        print("  python3 configure_challenge_vm.py disable <challenge_id>")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == 'config' and len(sys.argv) == 5:
        set_global_config(int(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
    elif cmd == 'enable' and len(sys.argv) == 3:
        toggle_challenge(int(sys.argv[2]), True)
    elif cmd == 'disable' and len(sys.argv) == 3:
        toggle_challenge(int(sys.argv[2]), False)
    else:
        print("Invalid arguments. Run without args for usage.")
        sys.exit(1)
