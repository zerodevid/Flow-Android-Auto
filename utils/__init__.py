"""
Auto Register Utils Package
"""

from .adb_ui import AdbUiPortal, Element, connect, list_devices
from .android_utils import AndroidDevice, get_device
from .totp import generate_totp, get_totp_with_remaining, wait_for_fresh_totp, TOTPManager

# Backward compatibility alias
DroidrunPortal = AdbUiPortal

__all__ = [
    "AdbUiPortal",
    "DroidrunPortal",  # backward compat alias
    "Element", 
    "connect",
    "list_devices",
    "AndroidDevice",
    "get_device",
    "generate_totp",
    "get_totp_with_remaining",
    "wait_for_fresh_totp",
    "TOTPManager",
]
