import os

class ProxmoxConfig:
    PROXMOX_HOST = os.getenv('PROXMOX_HOST', 'proxmox.local')
    PROXMOX_USER = os.getenv('PROXMOX_USER', 'ctfd@pve')
    PROXMOX_TOKEN_NAME = os.getenv('PROXMOX_TOKEN_NAME', 'ctfd')
    PROXMOX_TOKEN_VALUE = os.getenv('PROXMOX_TOKEN_VALUE', '')
    PROXMOX_NODE = os.getenv('PROXMOX_NODE', 'pve')
    PROXMOX_VERIFY_SSL = os.getenv('PROXMOX_VERIFY_SSL', 'false').lower() == 'true'
