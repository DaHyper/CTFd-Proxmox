from CTFd.models import db
from datetime import datetime


class ProxmoxGlobalConfig(db.Model):
    """Global VM config — single row. Template to clone, duration, etc."""
    __tablename__ = 'proxmox_global_config'
    id = db.Column(db.Integer, primary_key=True)
    proxmox_template_id = db.Column(db.Integer, nullable=False)
    vm_template_name = db.Column(db.String(100), default='CTFd VM')
    max_duration_hours = db.Column(db.Integer, default=4)


class ChallengeVM(db.Model):
    """Flag table: row exists = challenge has VM enabled."""
    __tablename__ = 'challenge_vms'
    id = db.Column(db.Integer, primary_key=True)
    challenge_id = db.Column(
        db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'), unique=True
    )


class ProxmoxVM(db.Model):
    """One VM per user, shared across all challenges."""
    __tablename__ = 'proxmox_vms'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    proxmox_vmid = db.Column(db.Integer, unique=True)
    vm_name = db.Column(db.String(100))
    vm_ip = db.Column(db.String(45))
    status = db.Column(db.String(20), default='creating')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    last_started = db.Column(db.DateTime)
    ctfd_managed = db.Column(db.Boolean, default=True)

    def get_remaining_time(self):
        if not self.expires_at:
            return 0
        return max(0, int((self.expires_at - datetime.utcnow()).total_seconds()))

    def get_remaining_time_formatted(self):
        seconds = self.get_remaining_time()
        return f"{seconds // 3600}h {(seconds % 3600) // 60}m"

    def to_dict(self):
        return {
            'id': self.id,
            'proxmox_vmid': self.proxmox_vmid,
            'vm_name': self.vm_name,
            'vm_ip': self.vm_ip,
            'status': self.status,
            'remaining_time': self.get_remaining_time(),
            'remaining_time_formatted': self.get_remaining_time_formatted(),
        }
