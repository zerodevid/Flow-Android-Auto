"""
Android Utils - Additional ADB utilities
"""

import subprocess
import time
import os
from typing import Optional, Tuple


class AndroidDevice:
    """
    ADB Device utilities untuk operasi Android umum
    """
    
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self._adb_prefix = ["adb"]
        if device_id:
            self._adb_prefix = ["adb", "-s", device_id]
    
    def _run(self, *args, check: bool = True) -> str:
        """Run ADB command"""
        cmd = self._adb_prefix + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            raise RuntimeError(f"ADB failed: {result.stderr}")
        return result.stdout.strip()
    
    # ==================== Device Info ====================
    
    def get_devices(self) -> list:
        """Get list of connected devices"""
        output = subprocess.run(["adb", "devices"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines = output.stdout.strip().split("\n")[1:]  # Skip header
        devices = []
        for line in lines:
            if "\tdevice" in line:
                devices.append(line.split("\t")[0])
        return devices
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution (width, height)"""
        output = self._run("shell", "wm", "size")
        # "Physical size: 1080x2400"
        match = output.split(": ")[-1]
        w, h = match.split("x")
        return int(w), int(h)
    
    def get_screen_density(self) -> int:
        """Get screen density (dpi)"""
        output = self._run("shell", "wm", "density")
        return int(output.split(": ")[-1])
    
    def get_android_version(self) -> str:
        """Get Android version"""
        return self._run("shell", "getprop", "ro.build.version.release")
    
    def get_sdk_version(self) -> int:
        """Get SDK/API level"""
        return int(self._run("shell", "getprop", "ro.build.version.sdk"))
    
    def get_device_model(self) -> str:
        """Get device model name"""
        return self._run("shell", "getprop", "ro.product.model")
    
    # ==================== Screen Control ====================
    
    def screenshot(self, save_path: str) -> str:
        """
        Take screenshot and save to local path
        
        Args:
            save_path: Local path to save screenshot (e.g., "screen.png")
        """
        remote_path = "/sdcard/screenshot.png"
        self._run("shell", "screencap", "-p", remote_path)
        self._run("pull", remote_path, save_path)
        self._run("shell", "rm", remote_path)
        return save_path
    
    def screen_record(self, save_path: str, duration: int = 10) -> str:
        """
        Record screen video
        
        Args:
            save_path: Local path to save video
            duration: Recording duration in seconds (max 180)
        """
        remote_path = "/sdcard/screenrecord.mp4"
        self._run("shell", "screenrecord", "--time-limit", str(duration), remote_path)
        self._run("pull", remote_path, save_path)
        self._run("shell", "rm", remote_path)
        return save_path
    
    def is_screen_on(self) -> bool:
        """Check if screen is on"""
        output = self._run("shell", "dumpsys", "power")
        return "mWakefulness=Awake" in output
    
    def wake_screen(self) -> None:
        """Wake up screen if off"""
        if not self.is_screen_on():
            self._run("shell", "input", "keyevent", "KEYCODE_WAKEUP")
    
    def lock_screen(self) -> None:
        """Lock screen"""
        self._run("shell", "input", "keyevent", "KEYCODE_SLEEP")
    
    def unlock_screen(self, pin: Optional[str] = None) -> None:
        """
        Unlock screen (swipe + optional PIN)
        
        Args:
            pin: Optional PIN/password to enter
        """
        self.wake_screen()
        time.sleep(0.3)
        
        # Swipe up to dismiss lock screen
        w, h = self.get_screen_size()
        self._run("shell", "input", "swipe", 
                 str(w//2), str(h*3//4), str(w//2), str(h//4), "300")
        
        if pin:
            time.sleep(0.5)
            self._run("shell", "input", "text", pin)
            self._run("shell", "input", "keyevent", "66")  # Enter
    
    # ==================== App Management ====================
    
    def install_apk(self, apk_path: str, replace: bool = True) -> None:
        """
        Install APK
        
        Args:
            apk_path: Path to APK file
            replace: Replace existing app if installed
        """
        args = ["install"]
        if replace:
            args.append("-r")
        args.append(apk_path)
        self._run(*args)
    
    def uninstall_app(self, package_name: str) -> None:
        """Uninstall app by package name"""
        self._run("uninstall", package_name)
    
    def clear_app_data(self, package_name: str) -> None:
        """Clear app data and cache"""
        self._run("shell", "pm", "clear", package_name)
    
    def is_app_installed(self, package_name: str) -> bool:
        """Check if app is installed"""
        output = self._run("shell", "pm", "list", "packages", package_name, check=False)
        return f"package:{package_name}" in output
    
    def get_app_version(self, package_name: str) -> str:
        """Get installed app version"""
        output = self._run("shell", "dumpsys", "package", package_name)
        for line in output.split("\n"):
            if "versionName=" in line:
                return line.split("=")[1].strip()
        return ""
    
    def grant_permission(self, package_name: str, permission: str) -> None:
        """Grant runtime permission to app"""
        self._run("shell", "pm", "grant", package_name, permission)
    
    def grant_all_permissions(self, package_name: str) -> None:
        """Grant all requested permissions"""
        common_permissions = [
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.CAMERA",
            "android.permission.READ_CONTACTS",
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.RECORD_AUDIO",
        ]
        for perm in common_permissions:
            try:
                self.grant_permission(package_name, perm)
            except:
                pass  # Permission not requested by app
    
    # ==================== Intent/Activity ====================
    
    def start_activity(self, package_name: str, activity_name: str, 
                       extras: Optional[dict] = None) -> None:
        """
        Start activity with optional extras
        
        Args:
            package_name: App package name
            activity_name: Activity class name
            extras: Optional dict of intent extras
        """
        cmd = ["shell", "am", "start", "-n", f"{package_name}/{activity_name}"]
        
        if extras:
            for key, value in extras.items():
                if isinstance(value, str):
                    cmd.extend(["--es", key, value])
                elif isinstance(value, int):
                    cmd.extend(["--ei", key, str(value)])
                elif isinstance(value, bool):
                    cmd.extend(["--ez", key, str(value).lower()])
        
        self._run(*cmd)
    
    def broadcast(self, action: str, extras: Optional[dict] = None) -> None:
        """Send broadcast intent"""
        cmd = ["shell", "am", "broadcast", "-a", action]
        
        if extras:
            for key, value in extras.items():
                if isinstance(value, str):
                    cmd.extend(["--es", key, value])
        
        self._run(*cmd)
    
    def open_url(self, url: str) -> None:
        """Open URL in default browser"""
        self._run("shell", "am", "start", "-a", "android.intent.action.VIEW", 
                 "-d", url)
    
    def open_settings(self, setting: str = "") -> None:
        """
        Open Android settings
        
        Args:
            setting: Specific setting page (e.g., "wifi", "bluetooth", "accessibility")
        """
        settings_map = {
            "": "android.settings.SETTINGS",
            "wifi": "android.settings.WIFI_SETTINGS",
            "bluetooth": "android.settings.BLUETOOTH_SETTINGS",
            "accessibility": "android.settings.ACCESSIBILITY_SETTINGS",
            "apps": "android.settings.APPLICATION_SETTINGS",
            "display": "android.settings.DISPLAY_SETTINGS",
            "location": "android.settings.LOCATION_SOURCE_SETTINGS",
        }
        
        action = settings_map.get(setting, f"android.settings.{setting.upper()}_SETTINGS")
        self._run("shell", "am", "start", "-a", action)
    
    # ==================== File Transfer ====================
    
    def push(self, local_path: str, remote_path: str) -> None:
        """Push file to device"""
        self._run("push", local_path, remote_path)
    
    def pull(self, remote_path: str, local_path: str) -> None:
        """Pull file from device"""
        self._run("pull", remote_path, local_path)
    
    # ==================== System ====================
    
    def reboot(self) -> None:
        """Reboot device"""
        self._run("reboot")
    
    def get_battery_level(self) -> int:
        """Get battery level percentage"""
        output = self._run("shell", "dumpsys", "battery")
        for line in output.split("\n"):
            if "level:" in line:
                return int(line.split(":")[1].strip())
        return -1
    
    def is_charging(self) -> bool:
        """Check if device is charging"""
        output = self._run("shell", "dumpsys", "battery")
        for line in output.split("\n"):
            if "status:" in line:
                status = int(line.split(":")[1].strip())
                return status == 2  # BATTERY_STATUS_CHARGING
        return False
    
    def set_airplane_mode(self, enabled: bool) -> None:
        """Toggle airplane mode (requires root on some devices)"""
        value = "1" if enabled else "0"
        self._run("shell", "settings", "put", "global", "airplane_mode_on", value)
        self.broadcast("android.intent.action.AIRPLANE_MODE")
    
    def enable_wifi(self, enabled: bool = True) -> None:
        """Enable/disable WiFi"""
        cmd = "enable" if enabled else "disable"
        self._run("shell", "svc", "wifi", cmd)
    
    def enable_mobile_data(self, enabled: bool = True) -> None:
        """Enable/disable mobile data"""
        cmd = "enable" if enabled else "disable"
        self._run("shell", "svc", "data", cmd)


def get_device(device_id: Optional[str] = None) -> AndroidDevice:
    """Get AndroidDevice instance"""
    return AndroidDevice(device_id)


if __name__ == "__main__":
    device = get_device()
    print(f"Device: {device.get_device_model()}")
    print(f"Android: {device.get_android_version()} (API {device.get_sdk_version()})")
    print(f"Screen: {device.get_screen_size()}")
    print(f"Battery: {device.get_battery_level()}%")
