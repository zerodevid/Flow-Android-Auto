"""
ADB UI Portal - Pure ADB + UIAutomator Android Automation
Drop-in replacement for DroidRun Portal - no app installation required.
Works with any Android device/emulator including LDPlayer.
"""

import subprocess
import json
import time
import re
import os
import tempfile
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any, Tuple, Union, Callable
from dataclasses import dataclass


@dataclass
class Element:
    """Represents a UI element from accessibility tree"""
    index: int
    resource_id: str
    class_name: str
    text: str
    bounds: Tuple[int, int, int, int]  # left, top, right, bottom
    children: List['Element']
    raw: Dict[str, Any]
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center coordinates of element"""
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)
    
    @property
    def width(self) -> int:
        return self.bounds[2] - self.bounds[0]
    
    @property
    def height(self) -> int:
        return self.bounds[3] - self.bounds[1]


class AdbUiPortal:
    """
    ADB UI Portal - Pure ADB + UIAutomator automation
    Drop-in replacement for DroidrunPortal without app installation.
    Uses uiautomator dump for UI tree and adb input for interactions.
    """
    
    def __init__(self, device_id: Optional[str] = None):
        """
        Initialize AdbUiPortal
        
        Args:
            device_id: Optional ADB device ID (for multi-device)
        """
        self.device_id = device_id
        self._adb_prefix = ["adb"]
        if device_id:
            self._adb_prefix = ["adb", "-s", device_id]
        self._element_counter = 0
        self._screen_size: Optional[Tuple[int, int]] = None
    
    def _run_adb(self, *args, timeout: int = 15) -> str:
        """Run ADB command and return output"""
        cmd = self._adb_prefix + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
            if result.returncode != 0:
                stderr = result.stderr.strip()
                # Some commands return non-zero but still work
                if stderr and "error" in stderr.lower():
                    raise RuntimeError(f"ADB command failed: {stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"ADB command timed out: {' '.join(cmd)}")
    
    def _run_adb_bytes(self, *args, timeout: int = 15) -> bytes:
        """Run ADB command and return raw bytes"""
        cmd = self._adb_prefix + list(args)
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0:
            stderr = result.stderr.decode(errors='replace').strip()
            if stderr and "error" in stderr.lower():
                raise RuntimeError(f"ADB command failed: {stderr}")
        return result.stdout

    # ==================== UI Tree (replaces a11y_tree) ====================
    
    def _dump_ui_xml(self) -> str:
        """
        Dump UI hierarchy using uiautomator and return XML string.
        Uses /sdcard/ for compatibility with all devices.
        """
        remote_path = "/sdcard/ui_dump.xml"
        
        # Dump UI hierarchy
        self._run_adb("shell", "uiautomator", "dump", remote_path, timeout=10)
        
        # Read the file content directly via shell cat (avoids pull)
        xml_content = self._run_adb("shell", "cat", remote_path, timeout=10)
        
        # Cleanup
        try:
            self._run_adb("shell", "rm", "-f", remote_path, timeout=5)
        except:
            pass
        
        return xml_content
    
    def _parse_bounds_str(self, bounds_str: str) -> Tuple[int, int, int, int]:
        """Parse bounds string like '[0,0][1080,2400]' to (left, top, right, bottom)"""
        # Match [left,top][right,bottom]
        match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
        if match:
            return (int(match.group(1)), int(match.group(2)), 
                    int(match.group(3)), int(match.group(4)))
        return (0, 0, 0, 0)
    
    def _parse_xml_element(self, xml_elem, counter_ref: List[int]) -> Element:
        """Parse XML element to Element object"""
        attrib = xml_elem.attrib
        
        # Parse bounds
        bounds_str = attrib.get('bounds', '[0,0][0,0]')
        bounds = self._parse_bounds_str(bounds_str)
        
        # Get text (prefer text, fallback to content-desc)
        text = attrib.get('text', '') or attrib.get('content-desc', '')
        
        # Build raw dict
        raw = {
            'resourceId': attrib.get('resource-id', ''),
            'className': attrib.get('class', ''),
            'text': attrib.get('text', ''),
            'contentDescription': attrib.get('content-desc', ''),
            'bounds': bounds_str,
            'clickable': attrib.get('clickable', 'false') == 'true',
            'enabled': attrib.get('enabled', 'true') == 'true',
            'focusable': attrib.get('focusable', 'false') == 'true',
            'focused': attrib.get('focused', 'false') == 'true',
            'scrollable': attrib.get('scrollable', 'false') == 'true',
            'selected': attrib.get('selected', 'false') == 'true',
            'checkable': attrib.get('checkable', 'false') == 'true',
            'checked': attrib.get('checked', 'false') == 'true',
            'package': attrib.get('package', ''),
        }
        
        # Assign index
        idx = counter_ref[0]
        counter_ref[0] += 1
        
        # Parse children
        children = []
        for child_xml in xml_elem:
            children.append(self._parse_xml_element(child_xml, counter_ref))
        
        return Element(
            index=idx,
            resource_id=attrib.get('resource-id', ''),
            class_name=attrib.get('class', ''),
            text=text,
            bounds=bounds,
            children=children,
            raw=raw
        )
    
    def get_a11y_tree(self, full: bool = False, filter_small: bool = True) -> List[Dict]:
        """
        Get accessibility tree (compatibility with DroidRun API)
        
        Returns:
            List of element dictionaries (nested tree structure)
        """
        xml_str = self._dump_ui_xml()
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            return []
        
        def xml_to_dict(elem):
            attrib = elem.attrib
            bounds_str = attrib.get('bounds', '[0,0][0,0]')
            bounds = self._parse_bounds_str(bounds_str)
            
            d = {
                'resourceId': attrib.get('resource-id', ''),
                'className': attrib.get('class', ''),
                'text': attrib.get('text', ''),
                'contentDescription': attrib.get('content-desc', ''),
                'bounds': f"{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}",
                'children': [xml_to_dict(c) for c in elem]
            }
            
            if full:
                d.update({
                    'clickable': attrib.get('clickable', 'false') == 'true',
                    'enabled': attrib.get('enabled', 'true') == 'true',
                    'focusable': attrib.get('focusable', 'false') == 'true',
                    'scrollable': attrib.get('scrollable', 'false') == 'true',
                    'package': attrib.get('package', ''),
                })
            
            return d
        
        result = []
        for child in root:
            result.append(xml_to_dict(child))
        return result
    
    def get_elements(self, full: bool = False) -> List[Element]:
        """Get UI elements as Element objects"""
        xml_str = self._dump_ui_xml()
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError:
            return []
        
        counter_ref = [0]
        elements = []
        for child in root:
            elements.append(self._parse_xml_element(child, counter_ref))
        return elements
    
    # ==================== Phone State ====================
    
    def get_phone_state(self) -> Dict[str, Any]:
        """
        Get current phone state
        Returns: packageName, activityName, keyboardVisible
        """
        state = {}
        
        # Get current activity/package via dumpsys window
        try:
            output = self._run_adb("shell", "dumpsys", "window", "windows", timeout=5)
            # Look for mCurrentFocus or mFocusedApp
            for line in output.split('\n'):
                if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                    # Pattern: {hash ActivityRecord{hash u0 com.package/.Activity t123}}
                    match = re.search(r'([\w.]+)/([\w.$]+)', line)
                    if match:
                        state['packageName'] = match.group(1)
                        activity = match.group(2)
                        # If activity starts with '.', prepend package
                        if activity.startswith('.'):
                            activity = match.group(1) + activity
                        state['activityName'] = activity
                        break
        except:
            state['packageName'] = ''
            state['activityName'] = ''
        
        # Check keyboard visibility via dumpsys input_method
        try:
            output = self._run_adb("shell", "dumpsys", "input_method", timeout=5)
            state['keyboardVisible'] = 'mInputShown=true' in output
        except:
            state['keyboardVisible'] = False
        
        return state
    
    def get_packages(self) -> List[Dict[str, Any]]:
        """Get list of installed launchable apps"""
        output = self._run_adb("shell", "pm", "list", "packages", "-3")
        packages = []
        for line in output.split('\n'):
            if line.startswith('package:'):
                pkg = line.replace('package:', '').strip()
                packages.append({'packageName': pkg})
        return packages
    
    def get_state(self, full: bool = False) -> Dict[str, Any]:
        """Get combined state (phone_state + a11y_tree)"""
        state = self.get_phone_state()
        state['a11y_tree'] = self.get_a11y_tree(full=full)
        return state
    
    # ==================== Element Parsing ====================
    
    def _parse_bounds(self, bounds_str: str) -> Tuple[int, int, int, int]:
        """Parse bounds string to tuple (left, top, right, bottom)"""
        parts = [int(x.strip()) for x in bounds_str.split(",")]
        return (parts[0], parts[1], parts[2], parts[3])
    
    def _parse_element(self, data: Dict) -> Element:
        """Parse raw element dict to Element object"""
        bounds = data.get("bounds", "0, 0, 0, 0")
        if isinstance(bounds, str):
            bounds = self._parse_bounds(bounds)
        elif isinstance(bounds, dict):
            bounds = (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])
        
        children = [self._parse_element(c) for c in data.get("children", [])]
        
        return Element(
            index=data.get("index", 0),
            resource_id=data.get("resourceId", ""),
            class_name=data.get("className", ""),
            text=data.get("text", "") or data.get("contentDescription", ""),
            bounds=bounds,
            children=children,
            raw=data
        )
    
    # ==================== Element Finding ====================
    
    def _flatten_elements(self, elements: List[Element]) -> List[Element]:
        """Flatten nested element tree to flat list"""
        result = []
        for elem in elements:
            result.append(elem)
            result.extend(self._flatten_elements(elem.children))
        return result
    
    def find_by_text(self, text: str, exact: bool = False, 
                     elements: Optional[List[Element]] = None) -> Optional[Element]:
        """Find element by text content"""
        if elements is None:
            elements = self.get_elements()
        
        all_elements = self._flatten_elements(elements)
        
        for elem in all_elements:
            if exact:
                if elem.text == text:
                    return elem
            else:
                if text.lower() in elem.text.lower():
                    return elem
        return None
    
    def find_all_by_text(self, text: str, exact: bool = False,
                         elements: Optional[List[Element]] = None) -> List[Element]:
        """Find all elements matching text"""
        if elements is None:
            elements = self.get_elements()
        
        all_elements = self._flatten_elements(elements)
        results = []
        
        for elem in all_elements:
            if exact:
                if elem.text == text:
                    results.append(elem)
            else:
                if text.lower() in elem.text.lower():
                    results.append(elem)
        return results
    
    def find_by_resource_id(self, resource_id: str,
                            elements: Optional[List[Element]] = None) -> Optional[Element]:
        """Find element by resourceId"""
        if elements is None:
            elements = self.get_elements()
        
        all_elements = self._flatten_elements(elements)
        
        for elem in all_elements:
            if elem.resource_id == resource_id:
                return elem
        return None
    
    def find_by_index(self, index: int,
                      elements: Optional[List[Element]] = None) -> Optional[Element]:
        """Find element by overlay index"""
        if elements is None:
            elements = self.get_elements()
        
        all_elements = self._flatten_elements(elements)
        
        for elem in all_elements:
            if elem.index == index:
                return elem
        return None
    
    def find_by_class(self, class_name: str,
                      elements: Optional[List[Element]] = None) -> List[Element]:
        """Find all elements by className (e.g., 'Button', 'EditText')"""
        if elements is None:
            elements = self.get_elements()
        
        all_elements = self._flatten_elements(elements)
        
        return [elem for elem in all_elements 
                if class_name.lower() in elem.class_name.lower()]
    
    # ==================== Input Actions ====================
    
    def tap(self, x: int, y: int) -> None:
        """Tap at screen coordinates"""
        self._run_adb("shell", "input", "tap", str(x), str(y))
    
    def tap_element(self, element: Element) -> None:
        """Tap center of element"""
        x, y = element.center
        self.tap(x, y)
    
    def tap_text(self, text: str, exact: bool = False) -> bool:
        """Find element by text and tap it"""
        elem = self.find_by_text(text, exact=exact)
        if elem:
            self.tap_element(elem)
            return True
        return False
    
    def tap_resource_id(self, resource_id: str) -> bool:
        """Find element by resourceId and tap it"""
        elem = self.find_by_resource_id(resource_id)
        if elem:
            self.tap_element(elem)
            return True
        return False
    
    def tap_index(self, index: int) -> bool:
        """Find element by index and tap it"""
        elem = self.find_by_index(index)
        if elem:
            self.tap_element(elem)
            return True
        return False
    
    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        """Long press at coordinates"""
        self._run_adb("shell", "input", "swipe", 
                     str(x), str(y), str(x), str(y), str(duration_ms))
    
    def long_press_element(self, element: Element, duration_ms: int = 1000) -> None:
        """Long press center of element"""
        x, y = element.center
        self.long_press(x, y, duration_ms)
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, 
              duration_ms: int = 300) -> None:
        """Swipe from (x1,y1) to (x2,y2)"""
        self._run_adb("shell", "input", "swipe",
                     str(x1), str(y1), str(x2), str(y2), str(duration_ms))
    
    def _get_screen_size(self) -> Tuple[int, int]:
        """Get screen resolution (cached)"""
        if self._screen_size is None:
            try:
                output = self._run_adb("shell", "wm", "size")
                match = output.split(": ")[-1]
                w, h = match.split("x")
                self._screen_size = (int(w.strip()), int(h.strip()))
            except:
                self._screen_size = (1080, 2400)  # Default fallback
        return self._screen_size
    
    def swipe_up(self, distance: int = 500, duration_ms: int = 300) -> None:
        """Swipe up from center of screen"""
        w, h = self._get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy + distance // 2, cx, cy - distance // 2, duration_ms)
    
    def swipe_down(self, distance: int = 500, duration_ms: int = 300) -> None:
        """Swipe down from center of screen"""
        w, h = self._get_screen_size()
        cx = w // 2
        cy = h // 2
        self.swipe(cx, cy - distance // 2, cx, cy + distance // 2, duration_ms)
    
    def scroll_to_text(self, text: str, max_swipes: int = 5, 
                       direction: str = "up") -> Optional[Element]:
        """Scroll until text is visible"""
        for _ in range(max_swipes):
            elem = self.find_by_text(text)
            if elem:
                return elem
            
            if direction == "up":
                self.swipe_up()
            else:
                self.swipe_down()
            time.sleep(0.5)
        
        return self.find_by_text(text)
    
    # ==================== Keyboard Input ====================
    
    def type_text(self, text: str, clear_first: bool = True, delay_between_keys: float = 0) -> None:
        """
        Type text into focused input field
        
        Uses ADB input text for ASCII. For special characters,
        falls back to character-by-character key events or broadcast.
        """
        if clear_first:
            self.clear_text()
            time.sleep(0.2)

        if delay_between_keys > 0:
            for char in text:
                if ord(char) < 128:
                    escaped = char.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"').replace(" ", "%s").replace("&", "\\&").replace("|", "\\|").replace(";", "\\;").replace("(", "\\(").replace(")", "\\)").replace("<", "\\<").replace(">", "\\>")
                    self._run_adb("shell", "input", "text", escaped)
                else:
                    self._run_adb("shell", "am", "broadcast", "-a", "clipcopy", "--es", "text", char)
                    time.sleep(0.1)
                    self._run_adb("shell", "input", "keyevent", "279")  # PASTE
                    time.sleep(0.1)
                time.sleep(delay_between_keys)
            return
        
        # Check if text is pure ASCII (adb input text only supports ASCII)
        if all(ord(c) < 128 for c in text):
            # Escape special shell characters
            escaped = text.replace("\\", "\\\\")
            escaped = escaped.replace("'", "\\'")
            escaped = escaped.replace('"', '\\"')
            escaped = escaped.replace(" ", "%s")
            escaped = escaped.replace("&", "\\&")
            escaped = escaped.replace("|", "\\|")
            escaped = escaped.replace(";", "\\;")
            escaped = escaped.replace("(", "\\(")
            escaped = escaped.replace(")", "\\)")
            escaped = escaped.replace("<", "\\<")
            escaped = escaped.replace(">", "\\>")
            
            self._run_adb("shell", "input", "text", escaped)
        else:
            # For Unicode/special chars, try ADBKeyboard broadcast first
            try:
                import base64
                encoded = base64.b64encode(text.encode('utf-8')).decode()
                self._run_adb("shell", "am", "broadcast", 
                             "-a", "ADB_INPUT_B64",
                             "--es", "msg", encoded)
            except:
                # Fallback: type char by char using input text for ASCII,
                # and clipboard for non-ASCII
                for char in text:
                    if ord(char) < 128:
                        escaped = char.replace(" ", "%s")
                        self._run_adb("shell", "input", "text", escaped)
                    else:
                        # Use clipboard for this character
                        self._run_adb("shell", "am", "broadcast",
                                     "-a", "clipcopy", "--es", "text", char)
                        time.sleep(0.1)
                        self._run_adb("shell", "input", "keyevent", "279")  # PASTE
                        time.sleep(0.1)
    
    def clear_text(self) -> None:
        """Clear text in focused input field"""
        # Select all (Ctrl+A) then delete
        # KEYCODE_MOVE_END to go to end
        self._run_adb("shell", "input", "keyevent", "123")  # MOVE_END
        time.sleep(0.1)
        # Send backspaces in chunks to avoid ADB command timeout
        for _ in range(5):
            self._run_adb("shell", "input", "keyevent", 
                          "67", "67", "67", "67", "67", 
                          "67", "67", "67", "67", "67")
    
    def press_key(self, key_code: int) -> None:
        """
        Send key event
        
        Common key codes:
            Enter=66, Backspace=67, Tab=61, Escape=111
            Home=3, Back=4, Up=19, Down=20, Left=21, Right=22
        """
        self._run_adb("shell", "input", "keyevent", str(key_code))
    
    def press_enter(self) -> None:
        """Press Enter key"""
        self.press_key(66)
    
    def press_back(self) -> None:
        """Press Back button"""
        self.press_key(4)
    
    def press_home(self) -> None:
        """Press Home button"""
        self.press_key(3)
    
    # ==================== Wait/Polling Utilities ====================
    
    def wait_for_text(self, text: str, timeout: float = 10.0, 
                      poll_interval: float = 0.5, stop_check: Optional[Callable[[], bool]] = None) -> Optional[Element]:
        """Wait until text appears on screen"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_check and stop_check():
                break
            elem = self.find_by_text(text)
            if elem:
                return elem
            time.sleep(poll_interval)
        return None
    
    def wait_for_activity(self, activity_name: str, timeout: float = 10.0,
                         poll_interval: float = 0.5, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        """Wait until specific activity is in foreground"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_check and stop_check():
                break
            state = self.get_phone_state()
            if activity_name.lower() in state.get("activityName", "").lower():
                return True
            time.sleep(poll_interval)
        return False
    
    def wait_for_keyboard(self, visible: bool = True, timeout: float = 5.0,
                         poll_interval: float = 0.3, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        """Wait for keyboard to appear or disappear"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_check and stop_check():
                break
            state = self.get_phone_state()
            if state.get("keyboardVisible", False) == visible:
                return True
            time.sleep(poll_interval)
        return False
    
    # ==================== App Control ====================
    
    def launch_app(self, package_name: str) -> None:
        """Launch app by package name"""
        self._run_adb("shell", "monkey", "-p", package_name, 
                     "-c", "android.intent.category.LAUNCHER", "1")
    
    def force_stop_app(self, package_name: str) -> None:
        """Force stop app"""
        self._run_adb("shell", "am", "force-stop", package_name)
    
    def get_current_package(self) -> str:
        """Get current foreground package name"""
        state = self.get_phone_state()
        return state.get("packageName", "")
    
    def get_current_activity(self) -> str:
        """Get current foreground activity name"""
        state = self.get_phone_state()
        return state.get("activityName", "")
    
    # ==================== Overlay Control (No-op for compatibility) ====================
    
    def set_overlay_visible(self, visible: bool) -> None:
        """No-op: overlay not needed without DroidRun"""
        pass
    
    def show_overlay(self) -> None:
        """No-op"""
        pass
    
    def hide_overlay(self) -> None:
        """No-op"""
        pass
    
    # ==================== Connection Check ====================
    
    def ping(self) -> bool:
        """Test connection to device via ADB"""
        try:
            output = self._run_adb("get-state", timeout=5)
            return "device" in output
        except:
            return False
    
    def get_version(self) -> str:
        """Get Android version (replaces DroidRun Portal version)"""
        try:
            return self._run_adb("shell", "getprop", "ro.build.version.release")
        except:
            return "unknown"
    
    # ==================== Debug/Info ====================
    
    def dump_screen(self) -> None:
        """Print all elements on screen for debugging"""
        elements = self.get_elements()
        all_elements = self._flatten_elements(elements)
        
        print(f"\n{'='*60}")
        print(f"Screen Elements ({len(all_elements)} total)")
        print(f"{'='*60}\n")
        
        for elem in all_elements:
            if elem.text:
                print(f"[{elem.index:2d}] {elem.class_name}: \"{elem.text}\"")
                print(f"     resourceId: {elem.resource_id or '(none)'}")
                print(f"     bounds: {elem.bounds} -> center: {elem.center}")
                print()


# ==================== Device Discovery ====================

def list_devices() -> List[Dict[str, str]]:
    """
    List all connected ADB devices
    
    Returns:
        List of dicts with 'id', 'status', 'model' keys
    """
    try:
        result = subprocess.run(["adb", "devices", "-l"], 
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10)
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:  # Skip header
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                device_id = parts[0]
                status = parts[1]
                
                # Extract model from device info
                model = ""
                for part in parts[2:]:
                    if part.startswith("model:"):
                        model = part.replace("model:", "")
                        break
                
                # Try to get model via getprop if not in device list
                if not model and status == "device":
                    try:
                        model_result = subprocess.run(
                            ["adb", "-s", device_id, "shell", "getprop", "ro.product.model"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5
                        )
                        model = model_result.stdout.strip()
                    except:
                        pass
                
                devices.append({
                    "id": device_id,
                    "status": status,
                    "model": model or device_id
                })
        return devices
    except:
        return []


# ==================== Convenience Functions ====================

def connect(device_id: Optional[str] = None) -> AdbUiPortal:
    """Create and return AdbUiPortal instance"""
    portal = AdbUiPortal(device_id)
    if not portal.ping():
        raise RuntimeError(
            "Cannot connect to ADB device. "
            "Make sure a device/emulator is connected and ADB is running.\n"
            "Try: adb devices"
        )
    return portal


if __name__ == "__main__":
    # Quick test
    print("Scanning for devices...")
    devices = list_devices()
    if devices:
        print(f"Found {len(devices)} device(s):")
        for d in devices:
            print(f"  - {d['id']} ({d['model']}) [{d['status']}]")
    
    portal = connect()
    print(f"\nConnected to device (Android {portal.get_version()})")
    portal.dump_screen()
