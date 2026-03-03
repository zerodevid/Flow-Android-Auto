"""
Droidrun Portal Utility Module
Android automation menggunakan Droidrun Portal ContentProvider API
"""

import subprocess
import json
import base64
import time
import re
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


class DroidrunPortal:
    """
    Droidrun Portal API Wrapper
    Menggunakan ADB ContentProvider untuk berkomunikasi dengan Droidrun Portal
    """
    
    AUTHORITY = "content://com.droidrun.portal"
    
    def __init__(self, device_id: Optional[str] = None):
        """
        Initialize DroidrunPortal
        
        Args:
            device_id: Optional ADB device ID (untuk multi-device)
        """
        self.device_id = device_id
        self._adb_prefix = ["adb"]
        if device_id:
            self._adb_prefix = ["adb", "-s", device_id]
    
    def _run_adb(self, *args) -> str:
        """Run ADB command and return output"""
        cmd = self._adb_prefix + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ADB command failed: {result.stderr}")
        return result.stdout.strip()
    
    def _query(self, endpoint: str) -> Dict[str, Any]:
        """Query ContentProvider endpoint"""
        uri = f"{self.AUTHORITY}/{endpoint}"
        output = self._run_adb("shell", "content", "query", "--uri", uri)
        
        # Parse response: "Row: 0 result={...}"
        match = re.search(r'result=(.+)$', output)
        if not match:
            raise RuntimeError(f"Invalid response format: {output}")
        
        response = json.loads(match.group(1))
        if response.get("status") == "error":
            raise RuntimeError(f"API error: {response.get('error')}")
        
        return response
    
    def _insert(self, endpoint: str, bindings: Dict[str, str]) -> Dict[str, Any]:
        """Insert to ContentProvider endpoint with bindings"""
        uri = f"{self.AUTHORITY}/{endpoint}"
        cmd = ["shell", "content", "insert", "--uri", uri]
        
        for key, value in bindings.items():
            cmd.extend(["--bind", value])
        
        output = self._run_adb(*cmd)
        return {"status": "success", "output": output}
    
    # ==================== Query Commands ====================
    
    def ping(self) -> bool:
        """Test connection to Droidrun Portal"""
        try:
            response = self._query("ping")
            return response.get("result") == "pong"
        except:
            return False
    
    def get_version(self) -> str:
        """Get Droidrun Portal version"""
        response = self._query("version")
        return response.get("result", "")
    
    def get_auth_token(self) -> str:
        """Get auth token for HTTP/WebSocket access"""
        response = self._query("auth_token")
        return response.get("result", "")
    
    def get_phone_state(self) -> Dict[str, Any]:
        """
        Get current phone state
        Returns: packageName, activityName, keyboardVisible, isEditable, focusedElement
        """
        response = self._query("phone_state")
        result = response.get("result", "{}")
        if isinstance(result, str):
            return json.loads(result)
        return result
    
    def get_packages(self) -> List[Dict[str, Any]]:
        """Get list of installed launchable apps"""
        response = self._query("packages")
        result = response.get("result", [])
        if isinstance(result, str):
            return json.loads(result)
        return result
    
    def get_a11y_tree(self, full: bool = False, filter_small: bool = True) -> List[Dict]:
        """
        Get accessibility tree
        
        Args:
            full: If True, get full tree with all properties
            filter_small: If True, filter elements < 1% visibility
        
        Returns:
            List of element dictionaries (nested tree structure)
        """
        endpoint = "a11y_tree_full" if full else "a11y_tree"
        if not filter_small:
            endpoint += "?filter=false"
        
        response = self._query(endpoint)
        result = response.get("result", "[]")
        if isinstance(result, str):
            return json.loads(result)
        return result
    
    def get_state(self, full: bool = False) -> Dict[str, Any]:
        """Get combined state (phone_state + a11y_tree)"""
        endpoint = "state_full" if full else "state"
        response = self._query(endpoint)
        result = response.get("result", "{}")
        if isinstance(result, str):
            return json.loads(result)
        return result
    
    # ==================== Element Parsing ====================
    
    def _parse_bounds(self, bounds_str: str) -> Tuple[int, int, int, int]:
        """Parse bounds string to tuple (left, top, right, bottom)"""
        parts = [int(x.strip()) for x in bounds_str.split(",")]
        return tuple(parts)
    
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
    
    def get_elements(self, full: bool = False) -> List[Element]:
        """Get accessibility tree as Element objects"""
        tree = self.get_a11y_tree(full=full)
        return [self._parse_element(elem) for elem in tree]
    
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
        """
        Find element by text content
        
        Args:
            text: Text to search for
            exact: If True, require exact match. If False, use contains.
            elements: Optional pre-fetched elements list
        """
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
        """
        Find element by text and tap it
        
        Returns:
            True if element found and tapped
        """
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
    
    def swipe_up(self, distance: int = 500, duration_ms: int = 300) -> None:
        """Swipe up from center of screen"""
        # Assume 1080x2400 screen, adjust as needed
        self.swipe(540, 1400, 540, 1400 - distance, duration_ms)
    
    def swipe_down(self, distance: int = 500, duration_ms: int = 300) -> None:
        """Swipe down from center of screen"""
        self.swipe(540, 1000, 540, 1000 + distance, duration_ms)
    
    def scroll_to_text(self, text: str, max_swipes: int = 5, 
                       direction: str = "up") -> Optional[Element]:
        """
        Scroll until text is visible
        
        Args:
            text: Text to find
            max_swipes: Maximum number of swipes
            direction: "up" or "down"
        
        Returns:
            Element if found, None otherwise
        """
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
        Type text using Droidrun Portal keyboard input
        
        Args:
            text: Text to type
            clear_first: Clear existing text before typing
            delay_between_keys: Delay between keystrokes
        """
        if delay_between_keys > 0:
            if clear_first:
                encoded = base64.b64encode("".encode()).decode()
                uri = f"{self.AUTHORITY}/keyboard/input"
                self._run_adb("shell", "content", "insert", "--uri", uri, "--bind", f"base64_text:s:{encoded}", "--bind", "clear:b:true")
                time.sleep(0.2)
            for char in text:
                encoded = base64.b64encode(char.encode()).decode()
                uri = f"{self.AUTHORITY}/keyboard/input"
                self._run_adb("shell", "content", "insert", "--uri", uri, "--bind", f"base64_text:s:{encoded}", "--bind", "clear:b:false")
                time.sleep(delay_between_keys)
            return

        encoded = base64.b64encode(text.encode()).decode()
        
        bindings = {
            "base64_text": f"base64_text:s:{encoded}"
        }
        if not clear_first:
            bindings["clear"] = "clear:b:false"
        
        uri = f"{self.AUTHORITY}/keyboard/input"
        cmd = ["shell", "content", "insert", "--uri", uri]
        for value in bindings.values():
            cmd.extend(["--bind", value])
        
        self._run_adb(*cmd)
    
    def clear_text(self) -> None:
        """Clear text in focused input field"""
        uri = f"{self.AUTHORITY}/keyboard/clear"
        self._run_adb("shell", "content", "insert", "--uri", uri)
    
    def press_key(self, key_code: int) -> None:
        """
        Send key event
        
        Common key codes:
            Enter=66, Backspace=67, Tab=61, Escape=111
            Home=3, Back=4, Up=19, Down=20, Left=21, Right=22
        """
        uri = f"{self.AUTHORITY}/keyboard/key"
        self._run_adb("shell", "content", "insert", "--uri", uri,
                     "--bind", f"key_code:i:{key_code}")
    
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
        """
        Wait until text appears on screen
        
        Args:
            text: Text to wait for
            timeout: Maximum wait time in seconds
            poll_interval: Time between polls in seconds
            stop_check: Optional callback that returns True to stop waiting
        
        Returns:
            Element if found, None if timeout or stopped
        """
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
        """
        Wait until specific activity is in foreground
        
        Args:
            activity_name: Activity name to wait for (partial match)
        """
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
    
    # ==================== Overlay Control ====================
    
    def set_overlay_visible(self, visible: bool) -> None:
        """Show or hide overlay"""
        uri = f"{self.AUTHORITY}/overlay_visible"
        self._run_adb("shell", "content", "insert", "--uri", uri,
                     "--bind", f"visible:b:{str(visible).lower()}")
    
    def show_overlay(self) -> None:
        """Show overlay"""
        self.set_overlay_visible(True)
    
    def hide_overlay(self) -> None:
        """Hide overlay"""
        self.set_overlay_visible(False)
    
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


# Convenience function
def connect(device_id: Optional[str] = None) -> DroidrunPortal:
    """Create and return DroidrunPortal instance"""
    portal = DroidrunPortal(device_id)
    if not portal.ping():
        raise RuntimeError("Cannot connect to Droidrun Portal. Is the app running?")
    return portal


if __name__ == "__main__":
    # Quick test
    portal = connect()
    print(f"Connected to Droidrun Portal v{portal.get_version()}")
    portal.dump_screen()
