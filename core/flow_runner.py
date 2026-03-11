#!/usr/bin/env python3
"""
Flow Runner - Step-based automation framework
Executes steps in sequence with error handling and dynamic input
"""

import sys
import time
import json
import os
import subprocess
import re
import threading

# Global registry of devices currently in use by a FlowRunner
CLAIMED_DEVICES = set()
DEVICE_LOCK = threading.Lock()

def claim_device(device_id: str):
    with DEVICE_LOCK:
        if device_id:
            CLAIMED_DEVICES.add(device_id)

def release_device(device_id: str):
    with DEVICE_LOCK:
        if device_id in CLAIMED_DEVICES:
            CLAIMED_DEVICES.remove(device_id)

# Fix Windows console encoding: don't crash on emoji, just replace with '?'
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(errors='replace')
        sys.stderr.reconfigure(errors='replace')
    except Exception:
        pass

# Disable proxy for localhost to avoid timeouts
os.environ["no_proxy"] = "127.0.0.1,localhost"

# Load environment variables from .env file
def load_dotenv():
    """Load .env file from project root"""
    env_paths = [
        os.path.join(os.path.dirname(__file__), '..', '.env'),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if value and key not in os.environ:
                            os.environ[key] = value
            break

load_dotenv()

from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from utils import connect, DroidrunPortal, list_devices
from utils.totp import generate_totp, get_totp_with_remaining, wait_for_fresh_totp
from server.otp_server import start_server, wait_otp, otp_store


class StepResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRY = "retry"


@dataclass
class StepContext:
    """Context passed between steps"""
    portal: DroidrunPortal
    session_id: str
    data: Dict[str, Any] = field(default_factory=dict)  # Shared data between steps
    step_results: List[Dict] = field(default_factory=list)
    _is_stopped_cb: Optional[Callable[[], bool]] = None
    _log_cb: Optional[Callable[[str, str], None]] = None
    _timer_cb: Optional[Callable[[str, float, float], None]] = None  # (node_id, remaining, total)
    _current_node_id: Optional[str] = None
    
    def is_stopped(self) -> bool:
        """Check if flow execution is stopped"""
        return self._is_stopped_cb() if self._is_stopped_cb else False
        
    def log(self, message: str, level: str = "info"):
        """Log a message that will show up in the UI console"""
        print(message)
        if self._log_cb:
            self._log_cb(message, level)
    
    def emit_timer(self, remaining: float, total: float):
        """Emit a timer event to show countdown on the current node"""
        if self._timer_cb and self._current_node_id:
            self._timer_cb(self._current_node_id, remaining, total)
    
    def set(self, key: str, value: Any):
        """Set a value in shared data"""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from shared data"""
        return self.data.get(key, default)


@dataclass
class StepConfig:
    """Configuration for a single step"""
    name: str
    action: str  # Action type: tap, type, wait, otp, totp, custom
    params: Dict[str, Any] = field(default_factory=dict)
    wait_before: float = 0.5  # Seconds to wait before step
    wait_after: float = 0.3  # Seconds to wait after step
    retry_count: int = 3
    retry_delay: float = 1.0
    optional: bool = False  # If True, continue even if step fails


def interruptible_sleep(ctx: StepContext, duration: float):
    """Sleep that can be interrupted by the stop flag, emits timer events"""
    if duration <= 0:
        return
    start_time = time.time()
    last_emit = 0
    while time.time() - start_time < duration:
        if ctx.is_stopped():
            break
        elapsed = time.time() - start_time
        remaining = duration - elapsed
        # Emit timer every ~1 second
        if int(elapsed) > last_emit:
            last_emit = int(elapsed)
            ctx.emit_timer(remaining, duration)
        sleep_time = min(0.2, remaining)
        if sleep_time > 0:
            time.sleep(sleep_time)
    # Final emit: 0 remaining
    ctx.emit_timer(0, duration)


class StepRegistry:
    """Registry of step actions"""
    
    def __init__(self, portal: DroidrunPortal):
        self.portal = portal
        self._actions: Dict[str, Callable] = {}
        self._register_default_actions()
    
    def _register_default_actions(self):
        """Register built-in actions"""
        
        # Tap action with optional wait validation
        def action_tap(ctx: StepContext, text: str = None, resource_id: str = None, 
                       index: int = None, x: int = None, y: int = None,
                       wait_for: bool = True, timeout: float = 10, 
                       delay: float = 0, **kwargs) -> StepResult:
            
            # Delay before action
            if delay > 0:
                interruptible_sleep(ctx, delay)
            
            if ctx.is_stopped(): return StepResult.FAILED

            # Tap by coordinates (no validation needed)
            if x is not None and y is not None:
                self.portal.tap(x, y)
                return StepResult.SUCCESS
            
            # Wait for element to appear first if wait_for is True
            # Only wait for text, not resource_id (resource_id tapping handles its own lookup)
            if wait_for and timeout > 0 and text:
                elem = self.portal.wait_for_text(text, timeout=timeout, stop_check=ctx.is_stopped)
                if not elem:
                    print(f"  ✗ Element not found: {text}")
                    return StepResult.FAILED
            
            if ctx.is_stopped(): return StepResult.FAILED
            
            # Now tap
            if resource_id:
                if self.portal.tap_resource_id(resource_id):
                    return StepResult.SUCCESS
            elif text:
                if self.portal.tap_text(text):
                    return StepResult.SUCCESS
            elif index is not None:
                if self.portal.tap_index(index):
                    return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Type action
        def action_type(ctx: StepContext, text: str = None, 
                        from_data: str = None, clear: bool = True, 
                        delay: float = 0, speed: float = 0, **kwargs) -> StepResult:
            # Delay before action
            if delay > 0:
                interruptible_sleep(ctx, delay)
            
            if ctx.is_stopped(): return StepResult.FAILED
            
            value = text
            if from_data:
                value = ctx.get(from_data)
            if value:
                self.portal.type_text(value, clear_first=clear, delay_between_keys=speed)
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Wait for text
        def action_wait(ctx: StepContext, text: str = None, 
                        timeout: float = 10, **kwargs) -> StepResult:
            if text:
                elem = self.portal.wait_for_text(text, timeout=timeout, stop_check=ctx.is_stopped)
                if elem:
                    return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Wait until text/element disappears from screen
        def action_wait_gone(ctx: StepContext, text: str = None,
                             timeout: float = 30, **kwargs) -> StepResult:
            """Wait until the specified text disappears from screen"""
            if not text:
                return StepResult.FAILED
            
            print(f"  👻 Waiting for '{text}' to disappear...")
            start_time = time.time()
            poll_interval = 0.5
            
            while time.time() - start_time < timeout:
                if ctx.is_stopped():
                    break
                # Refresh screen and check if text still exists
                try:
                    elem = self.portal.find_by_text(text)
                    if not elem:
                        elapsed = time.time() - start_time
                        print(f"  ✓ Element gone after {elapsed:.1f}s")
                        return StepResult.SUCCESS
                except:
                    # Error finding element = probably gone
                    return StepResult.SUCCESS
                
                interruptible_sleep(ctx, poll_interval)
            
            print(f"  ✗ Timeout - '{text}' still visible after {timeout}s")
            return StepResult.FAILED
        
        # Wait for OTP from server
        def action_otp(ctx: StepContext, timeout: float = 120, 
                       save_as: str = "otp", clear_first: bool = True, **kwargs) -> StepResult:
            # Use fixed session "default" - any OTP that comes in will be used
            session = "default"
            
            # Clear old OTP before waiting
            if clear_first:
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"http://127.0.0.1:5000/clear",
                        data=json.dumps({"session_id": session}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=5)
                    print(f"  🗑️ Cleared old OTP")
                except Exception:
                    pass
            
            print(f"  ⏳ Waiting for OTP...")
            otp = wait_otp(session, timeout=timeout, stop_check=ctx.is_stopped)
            if otp:
                ctx.set(save_as, otp)
                print(f"  ✓ OTP received: {otp}")
                return StepResult.SUCCESS
            print("  ✗ OTP timeout or stopped")
            return StepResult.FAILED
        
        # Generate and input TOTP
        def action_totp(ctx: StepContext, secret: str = None,
                        from_data: str = None, save_as: str = "totp",
                        min_remaining: int = 5, **kwargs) -> StepResult:
            key = secret
            if from_data:
                key = ctx.get(from_data)
            if key:
                code = wait_for_fresh_totp(key, min_remaining=min_remaining, stop_check=ctx.is_stopped)
                if code:
                    ctx.set(save_as, code)
                    print(f"  ✓ TOTP generated: {code}")
                    return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Press key
        def action_key(ctx: StepContext, key: str = None, repeat: int = 1, delay: float = 0.5, **kwargs) -> StepResult:
            key_codes = {
                "enter": 66, "back": 4, "home": 3, "recent": 187,
                "backspace": 67, "tab": 61, "escape": 111,
                "up": 19, "down": 20, "left": 21, "right": 22,
                "ctrl+c": 278, "ctrl+v": 279
            }
            code = key_codes.get(key.lower(), int(key) if key.isdigit() else 0)
            if code:
                repeat_count = max(1, int(repeat))
                for i in range(repeat_count):
                    if ctx.is_stopped(): return StepResult.FAILED
                    self.portal.press_key(code)
                    if repeat_count > 1 and i < repeat_count - 1 and delay > 0:
                        interruptible_sleep(ctx, delay)
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Scroll
        def action_scroll(ctx: StepContext, direction: str = "up", 
                          distance: int = 500, **kwargs) -> StepResult:
            if direction == "up":
                self.portal.swipe_up(distance=distance)
            else:
                self.portal.swipe_down(distance=distance)
            return StepResult.SUCCESS
        
        # Capture text from element
        def action_capture(ctx: StepContext, text: str = None, 
                           resource_id: str = None, index: int = None,
                           save_as: str = None, **kwargs) -> StepResult:
            elements = self.portal.get_elements()
            flat = self.portal._flatten_elements(elements)
            
            target = None
            # Capture by index (most reliable for dynamic text)
            if index is not None:
                for e in flat:
                    if e.index == index:
                        target = e
                        break
            elif resource_id:
                for e in flat:
                    if e.resource_id == resource_id:
                        target = e
                        break
            elif text:
                for e in flat:
                    if text.lower() in e.text.lower():
                        target = e
                        break
            
            if target and save_as:
                ctx.set(save_as, target.text)
                print(f"  ✓ Captured: {target.text}")
                return StepResult.SUCCESS
            print(f"  ✗ Capture failed - element not found")
            return StepResult.FAILED
        
        # Copy - tap copy button, open browser to capture clipboard, return to app
        def action_clipboard(ctx: StepContext, text: str = None, index: int = None,
                             resource_id: str = None, save_as: str = "clipboard",
                             delay: float = 0.5, server_url: str = "http://10.0.2.2:5000",
                             timeout: float = 15, **kwargs) -> StepResult:
            import subprocess
            import re
            
            # Get the current app package to return to later
            result = subprocess.run(
                self.portal._adb_prefix + ["shell", "dumpsys", "window", "windows"],
                capture_output=True, text=True, timeout=5
            )
            current_package = None
            for line in result.stdout.split('\n'):
                if 'mCurrentFocus' in line or 'mFocusedApp' in line:
                    match = re.search(r'(\w+\.\w+[\w.]*)/[^\s]+', line)
                    if match:
                        current_package = match.group(1)
                        break
            
            print(f"  📦 Current app: {current_package}")
            
            # Step 1: Tap the copy button
            tapped = False
            if index is not None:
                if self.portal.tap_index(index):
                    tapped = True
                    print(f"  ✓ Tapped element index: {index}")
            elif resource_id:
                if self.portal.tap_resource_id(resource_id):
                    tapped = True
                    print(f"  ✓ Tapped resource_id: {resource_id}")
            elif text:
                if self.portal.tap_text(text):
                    tapped = True
                    print(f"  ✓ Tapped text: {text}")
            
            if not tapped:
                print("  ✗ Failed to tap copy button")
                return StepResult.FAILED
            
            time.sleep(delay)  # Wait for copy action
            
            # Step 2: Clear old clipboard data from server
            session_id = f"clip_{ctx.session_id}"
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://127.0.0.1:5000/clear",
                    data=json.dumps({"session_id": session_id}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                urllib.request.urlopen(req, timeout=3)
            except:
                pass
            
            # Step 3: Open browser to paste page
            # 10.0.2.2 is the host IP from Android emulator's perspective
            paste_url = f"{server_url}/paste?session={session_id}"
            print(f"  🌐 Opening browser: {paste_url}")
            
            subprocess.run(self.portal._adb_prefix + [
                "shell", "am", "start", "-a", "android.intent.action.VIEW",
                "-d", paste_url
            ], capture_output=True, timeout=5)
            
            time.sleep(3)  # Wait for browser to load
            
            def check_data():
                try:
                    import urllib.request
                    url = f"http://127.0.0.1:5000/otp/{session_id}"
                    print(f"    🔍 Polling: {url}") 
                    with urllib.request.urlopen(url, timeout=2) as response:
                        body = response.read().decode()
                        data = json.loads(body)
                        # print(f"    🔍 Resp: {data}") # Too noisy if looped?
                        if data.get("status") == "ok" and data.get("otp"):
                             print(f"    ✅ Data found!")
                             return data["otp"]
                        else:
                             print(f"    ⚠ Not found: {data} (Session: {session_id})")
                except Exception as e:
                    print(f"    ⚠ Poll error: {e}")
                return None
            
            clipboard_data = check_data()
            
            if not clipboard_data:
                print("  ⚠ Auto-check failed. Using manual input directly...")
                
                clicked_input = False
                # Tap input field
                if self.portal.tap_text("Paste here manually"):
                    clicked_input = True
                elif self.portal.tap_text("OR MANUAL PASTE:"):
                        # The label is h3, might focus input
                        clicked_input = True
                
                if clicked_input:
                    print("  ✓ Tapped manual input field")
                    time.sleep(0.5)
                    # Send PASTE keycode
                    subprocess.run(self.portal._adb_prefix + ["shell", "input", "keyevent", "279"], timeout=2)
                    print("  📋 Sent PASTE keycode")
                    time.sleep(0.5)
                    
                    # Tap Send
                    if self.portal.tap_text("Send Manual"):
                        print("  ✓ Tapped Send Manual button")
                    else:
                        # Try generic enter
                        subprocess.run(self.portal._adb_prefix + ["shell", "input", "keyevent", "66"], timeout=2)
                    
                    time.sleep(1)
                    clipboard_data = check_data()

            # Step 5: Close browser and return to original app

            # Step 5: Close browser and return to original app
            print("  🔙 Returning to app...")
            subprocess.run(self.portal._adb_prefix + ["shell", "input", "keyevent", "KEYCODE_BACK"], timeout=3)
            time.sleep(0.3)
            subprocess.run(self.portal._adb_prefix + ["shell", "input", "keyevent", "KEYCODE_BACK"], timeout=3)
            time.sleep(0.3)
            
            # Force return to original app if we know it
            if current_package:
                subprocess.run(self.portal._adb_prefix + [
                    "shell", "am", "start", "-n",
                    f"{current_package}/.MainActivity"
                ], capture_output=True, timeout=3)
            
            time.sleep(0.5)
            
            # Final check with polling
            if not clipboard_data:
                print("  ⏳ Checking server for data (final poll)...")
                for _ in range(5):
                    clipboard_data = check_data()
                    if clipboard_data:
                        break
                    time.sleep(1)
            
            # Step 6: Process and save clipboard data
            if clipboard_data:
                # Clean and validate
                clean = re.sub(r'[\s\-]+', '', clipboard_data)
                if re.match(r'^[A-Z2-7]{16,}$', clean):
                    print(f"  ✓ Clipboard (browser): {clean[:8]}...{clean[-4:]}")
                    ctx.set(save_as, clean)
                    return StepResult.SUCCESS
                elif len(clipboard_data) > 3:
                    print(f"  ✓ Clipboard (browser): {clipboard_data[:20]}...")
                    ctx.set(save_as, clipboard_data)
                    return StepResult.SUCCESS
            
            print(f"  ✗ Failed to capture clipboard via browser")
            return StepResult.FAILED
        
        # Set data
        def action_set(ctx: StepContext, key: str = None, 
                       value: Any = None, **kwargs) -> StepResult:
            if key:
                ctx.set(key, value)
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Delay/sleep
        def action_delay(ctx: StepContext, seconds: float = 1, **kwargs) -> StepResult:
            interruptible_sleep(ctx, seconds)
            return StepResult.SUCCESS if not ctx.is_stopped() else StepResult.FAILED
        
        # Launch app
        def action_launch(ctx: StepContext, package: str = None, **kwargs) -> StepResult:
            if package:
                self.portal.launch_app(package)
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Check if text exists
        def action_check(ctx: StepContext, text: str = None, 
                         exists: bool = True, **kwargs) -> StepResult:
            elem = self.portal.find_by_text(text)
            if exists and elem:
                return StepResult.SUCCESS
            elif not exists and not elem:
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # HTTP Request action for API calls
        def action_http_request(ctx: StepContext, url: str, method: str = "POST", 
                          headers: Dict = None, include_data: bool = True,
                          payload: Dict = None, timeout: float = 10,
                          save_response: str = None, **kwargs) -> StepResult:
            ctx.log(f"  📡 HTTP Request: {method} {url}")
            
            try:
                import urllib.request
                import urllib.error
                
                # Prepare data
                data_to_send = {}
                if include_data:
                    data_to_send.update(ctx.data)
                
                if payload:
                    data_to_send.update(payload)
                
                # Prepare body
                json_data = json.dumps(data_to_send).encode('utf-8')
                
                # Prepare headers
                req_headers = {
                    "Content-Type": "application/json",
                    "User-Agent": "AutoRegister/1.0"
                }
                if headers:
                    req_headers.update(headers)
                
                # Create request
                req = urllib.request.Request(
                    url, 
                    data=json_data if method in ["POST", "PUT"] else None,
                    headers=req_headers,
                    method=method
                )
                
                # Execute
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = response.status
                    response_body = response.read().decode('utf-8')
                    
                    # Save response if requested
                    if save_response:
                        try:
                            response_data = json.loads(response_body)
                        except:
                            response_data = response_body
                        ctx.set(save_response, response_data)
                        ctx.log(f"  ✓ Response saved to '{save_response}'", "success")
                    
                    ctx.log(f"  ✓ HTTP Request success: {status}", "success")
                    return StepResult.SUCCESS
                    
            except urllib.error.HTTPError as e:
                ctx.log(f"  ✗ HTTP Request error: {e.code} {e.reason}", "error")
                return StepResult.FAILED
            except Exception as e:
                ctx.log(f"  ✗ HTTP Request error: {e}", "error")
                return StepResult.FAILED

        # Register all
        self._actions = {
            "tap": action_tap,
            "type": action_type,
            "wait": action_wait,
            "wait_gone": action_wait_gone,
            "otp": action_otp,
            "totp": action_totp,
            "key": action_key,
            "scroll": action_scroll,
            "capture": action_capture,
            "clipboard": action_clipboard,
            "set": action_set,
            "delay": action_delay,
            "launch": action_launch,
            "check": action_check,
            "http_request": action_http_request,
            "webhook": action_http_request,  # Backward compatibility
        }
        
        # Shell command (for adb operations)
        def action_shell(ctx: StepContext, command: str = None, **kwargs) -> StepResult:
            if command:
                result = subprocess.run(
                    self.portal._adb_prefix + ["shell"] + command.split(),
                    capture_output=True, text=True, timeout=10
                )
                ctx.log(f"  📟 Shell: {command}")
                if result.returncode == 0:
                    return StepResult.SUCCESS
                else:
                    ctx.log(f"  ✗ Shell failed: {result.stderr or result.stdout}", "error")
            return StepResult.FAILED
        
        # Close/Force-stop app (remove from RAM)
        def action_close(ctx: StepContext, package: str = None, **kwargs) -> StepResult:
            if package:
                result = subprocess.run(
                    self.portal._adb_prefix + ["shell", "am", "force-stop", package],
                    capture_output=True, text=True, timeout=10
                )
                print(f"  🛑 Force-stopped: {package}")
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Clear app data/cache
        def action_clear_data(ctx: StepContext, package: str = None, 
                              cache_only: bool = False, **kwargs) -> StepResult:
            if not package:
                return StepResult.FAILED
            
            if cache_only:
                # Clear only cache directory
                result = subprocess.run(
                    self.portal._adb_prefix + ["shell", "rm", "-rf", f"/data/data/{package}/cache/*"],
                    capture_output=True, text=True, timeout=10
                )
                print(f"  🧹 Cache cleared: {package}")
            else:
                # Clear all app data (requires root or run-as for some apps)
                result = subprocess.run(
                    self.portal._adb_prefix + ["shell", "pm", "clear", package],
                    capture_output=True, text=True, timeout=15
                )
                if "Success" in result.stdout:
                    print(f"  🗑️ Data cleared: {package}")
                    return StepResult.SUCCESS
                else:
                    print(f"  ⚠️ Clear result: {result.stdout.strip()}")
                    # Try alternative method
                    subprocess.run(
                        self.portal._adb_prefix + ["shell", "am", "force-stop", package],
                        capture_output=True, text=True, timeout=5
                    )
                    return StepResult.SUCCESS
            
            return StepResult.SUCCESS
        
        # Ask AI - query AI and save response
        def action_ask_ai(ctx: StepContext, prompt: str = None, 
                          provider: str = "gemini", model: str = None,
                          include_screen: bool = False, save_as: str = "ai_response",
                          **kwargs) -> StepResult:
            import urllib.request
            import urllib.error
            
            if not prompt:
                ctx.log("  ✗ No prompt provided", "error")
                return StepResult.FAILED
            
            # Replace placeholders in prompt with context data
            final_prompt = prompt
            for key, value in ctx.data.items():
                final_prompt = final_prompt.replace(f"{{{key}}}", str(value))
            
            # Optionally include screen context
            if include_screen:
                try:
                    elements = self.portal.get_elements()
                    flat = self.portal._flatten_elements(elements)
                    screen_text = "\n".join([f"[{e.index}] {e.text}" for e in flat if e.text])
                    final_prompt += f"\n\nCurrent screen elements:\n{screen_text}"
                except:
                    pass
            
            ctx.log(f"  🤖 Asking AI ({provider})...", "info")
            ctx.log(f"     Prompt: {final_prompt[:100]}...", "info")
            
            try:
                response_text = None
                
                if provider == "gemini":
                    # Use Gemini API
                    api_key = os.environ.get("GEMINI_API_KEY", "")
                    if not api_key:
                        ctx.log("  ✗ GEMINI_API_KEY not set", "error")
                        return StepResult.FAILED
                    
                    model_name = model or "gemini-2.0-flash"
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                    
                    payload = {
                        "contents": [{"parts": [{"text": final_prompt}]}],
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
                    }
                    
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = json.loads(resp.read().decode())
                        response_text = data["candidates"][0]["content"]["parts"][0]["text"]
                
                elif provider == "openai":
                    # Use OpenAI API
                    api_key = os.environ.get("OPENAI_API_KEY", "")
                    if not api_key:
                        ctx.log("  ✗ OPENAI_API_KEY not set", "error")
                        return StepResult.FAILED
                    
                    model_name = model or "gpt-4o-mini"
                    url = "https://api.openai.com/v1/chat/completions"
                    
                    payload = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": final_prompt}],
                        "temperature": 0.7,
                        "max_tokens": 1024
                    }
                    
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode(),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {api_key}"
                        },
                        method="POST"
                    )
                    
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        data = json.loads(resp.read().decode())
                        response_text = data["choices"][0]["message"]["content"]
                
                elif provider == "ollama":
                    # Use local Ollama
                    model_name = model or "llama3.2"
                    url = "http://localhost:11434/api/generate"
                    
                    payload = {
                        "model": model_name,
                        "prompt": final_prompt,
                        "stream": False
                    }
                    
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode())
                        response_text = data.get("response", "")
                
                else:
                    ctx.log(f"  ✗ Unknown provider: {provider}", "error")
                    return StepResult.FAILED
                
                if response_text:
                    # Clean up response (remove extra whitespace)
                    response_text = response_text.strip()
                    ctx.set(save_as, response_text)
                    ctx.log(f"  ✓ AI Response saved to '{save_as}'", "success")
                    ctx.log(f"     Response: {response_text[:100]}...", "info")
                    return StepResult.SUCCESS
                
                ctx.log("  ✗ Empty response from AI", "error")
                return StepResult.FAILED
                
            except urllib.error.HTTPError as e:
                ctx.log(f"  ✗ AI HTTP Error: {e.code} {e.reason}", "error")
                return StepResult.FAILED
            except Exception as e:
                ctx.log(f"  ✗ AI Error: {e}", "error")
                return StepResult.FAILED
        
        # Condition - check if text exists on screen or in data
        def action_condition(ctx: StepContext, check_text: str = None,
                            check_data: str = None, check_value: str = None,
                            operator: str = "exists", **kwargs) -> StepResult:
            """
            Check a condition and return result.
            - check_text: Check if this text exists on current screen
            - check_data: Check a key in context data
            - check_value: Value to compare against (for check_data)
            - operator: 'exists', 'not_exists', 'equals', 'contains', 'not_contains'
            
            Returns SUCCESS if condition is TRUE, SKIPPED if FALSE
            """
            result = False
            
            if check_text:
                # Check if text exists on screen
                try:
                    elements = self.portal.get_elements()
                    flat = self.portal._flatten_elements(elements)
                    screen_texts = [e.text.lower() for e in flat if e.text]
                    check_lower = check_text.lower()
                    
                    text_found = any(check_lower in txt for txt in screen_texts)
                    
                    if operator == "exists":
                        result = text_found
                    elif operator == "not_exists":
                        result = not text_found
                    else:
                        result = text_found if operator == "exists" else not text_found
                    
                    print(f"  🔀 Condition: '{check_text}' {operator} on screen = {result}")
                except Exception as e:
                    print(f"  ⚠️ Condition check error: {e}")
                    result = False
            
            elif check_data:
                # Check a value in context data
                data_value = ctx.get(check_data, "")
                
                if operator == "exists":
                    result = bool(data_value)
                elif operator == "not_exists":
                    result = not bool(data_value)
                elif operator == "equals" and check_value:
                    result = str(data_value) == str(check_value)
                elif operator == "contains" and check_value:
                    result = str(check_value) in str(data_value)
                elif operator == "not_contains" and check_value:
                    result = str(check_value) not in str(data_value)
                else:
                    result = bool(data_value)
                
                print(f"  🔀 Condition: data[{check_data}] {operator} = {result}")
            
            # Store result in context for potential use
            ctx.set("_condition_result", result)
            
            if result:
                print(f"  ✓ Condition: TRUE")
                return StepResult.SUCCESS
            else:
                print(f"  ✗ Condition: FALSE")
                return StepResult.SKIPPED  # SKIPPED means condition not met
        
        # Data Source Iterator
        def action_data_source(ctx: StepContext, rows: List[Dict] = None, 
                               columns: List[str] = None, start_index: int = 0, **kwargs) -> StepResult:
            if not rows:
                print("  ⚠️ No data rows provided")
                return StepResult.FAILED

            # Get current index (stateful iteration)
            # Check context first, then param default (which allows resuming from a specific index)
            index = ctx.get("_data_source_index")
            try:
                index = int(index) if index is not None else int(start_index)
            except (ValueError, TypeError):
                index = 0
            
            if index < len(rows):
                # Load current row data
                row_data = rows[index]
                for k, v in row_data.items():
                    ctx.set(k, v)
                
                print(f"  📊 Data Source: Loaded row {index + 1}/{len(rows)}")
                print(f"     Data: {row_data}")
                
                # Increment for next visit
                ctx.set("_data_source_index", index + 1)
                return StepResult.SUCCESS
            else:
                # End of data
                print(f"  🏁 Data Source: No more rows (finished {len(rows)})")
                return StepResult.FAILED

        # Fingerprint - simulate fingerprint touch on emulator
        def action_fingerprint(ctx: StepContext, finger_id: str = "1", 
                               delay: float = 0.5, **kwargs) -> StepResult:
            """
            Simulate fingerprint touch sensor on Android Emulator.
            Uses: adb emu finger touch <finger_id>
            Finger IDs: 1-10 (same as Android Studio Extended Controls)
            """
            import subprocess
            
            if delay > 0:
                time.sleep(delay)
            
            try:
                # adb emu finger touch <finger_id>
                result = subprocess.run(
                    self.portal._adb_prefix + ["emu", "finger", "touch", str(finger_id)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0 and "OK" in result.stdout:
                    print(f"  👆 Fingerprint: Touch sensor (Finger {finger_id})")
                    return StepResult.SUCCESS
                else:
                    # Try alternative method via telnet if direct adb fails
                    print(f"  ⚠️ Fingerprint via ADB failed, trying alternative...")
                    # Some emulators need a different approach
                    result2 = subprocess.run(
                        self.portal._adb_prefix + ["shell", "input", "keyevent", "KEYCODE_FINGERPRINT"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result2.returncode == 0:
                        print(f"  👆 Fingerprint: Keyevent sent")
                        return StepResult.SUCCESS
                    
                    print(f"  ✗ Fingerprint failed: {result.stderr or result.stdout}")
                    return StepResult.FAILED
                    
            except subprocess.TimeoutExpired:
                print(f"  ✗ Fingerprint: Timeout")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ Fingerprint error: {e}")
                return StepResult.FAILED

        # ==================== SMSBower API Actions ====================
        
        SMSBOWER_API = "https://smsbower.app/stubs/handler_api.php"
        
        def _sms_api_call(action: str, api_key: str, extra_params: Dict = None) -> str:
            """Helper: make SMSBower API GET request and return response text"""
            import urllib.request
            import urllib.parse
            
            params = {"api_key": api_key, "action": action}
            if extra_params:
                params.update(extra_params)
            
            url = f"{SMSBOWER_API}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "FlowRunner/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8').strip()
        
        def _get_sms_api_key(ctx: StepContext) -> str:
            """Helper: get API key from context"""
            key = ctx.get("sms_api_key")
            if not key:
                print("  ✗ SMSBower API key not found! Add SMS Config node first.")
                return None
            return key
        
        # SMS Config - save API key to context
        def action_sms_config(ctx: StepContext, api_key: str = None, 
                              save_as: str = "sms_api_key", **kwargs) -> StepResult:
            if not api_key:
                print("  ✗ API key is required")
                return StepResult.FAILED
            
            ctx.set(save_as, api_key)
            print(f"  🔑 SMSBower API key configured")
            return StepResult.SUCCESS
        
        # SMS Get Number - buy a virtual phone number
        def action_sms_get_number(ctx: StepContext, service: str = None,
                                   country: str = "0", max_price: str = None,
                                   save_as: str = "sms_phone", **kwargs) -> StepResult:
            api_key = _get_sms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            if not service:
                print("  ✗ Service code is required (e.g. 'go' for Google)")
                return StepResult.FAILED
            
            print(f"  📱 Getting number for service: {service}, country: {country}")
            
            try:
                params = {"service": service, "country": str(country)}
                if max_price:
                    params["maxPrice"] = str(max_price)
                
                result = _sms_api_call("getNumber", api_key, params)
                
                if result.startswith("ACCESS_NUMBER:"):
                    parts = result.split(":")
                    activation_id = parts[1]
                    phone_number = parts[2]
                    
                    ctx.set("sms_activation_id", activation_id)
                    ctx.set(save_as, phone_number)
                    print(f"  ✓ Number: {phone_number} (ID: {activation_id})")
                    return StepResult.SUCCESS
                
                elif "NO_NUMBERS" in result:
                    print(f"  ✗ No numbers available for service={service}, country={country}")
                elif "NO_BALANCE" in result:
                    print(f"  ✗ Insufficient balance")
                elif "BAD_SERVICE" in result:
                    print(f"  ✗ Invalid service code: {service}")
                elif "BAD_KEY" in result:
                    print(f"  ✗ Invalid API key")
                else:
                    print(f"  ✗ Error: {result}")
                
                return StepResult.FAILED
                
            except Exception as e:
                print(f"  ✗ SMS API error: {e}")
                return StepResult.FAILED
        
        # SMS Get Code - poll for incoming SMS
        def action_sms_get_code(ctx: StepContext, from_data: str = "sms_activation_id",
                                 timeout: float = 120, save_as: str = "sms_code",
                                 **kwargs) -> StepResult:
            api_key = _get_sms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            activation_id = ctx.get(from_data)
            if not activation_id:
                print(f"  ✗ Activation ID not found in context key: {from_data}")
                return StepResult.FAILED
            
            print(f"  ⏳ Waiting for SMS code (ID: {activation_id}, timeout: {timeout}s)...")
            
            start_time = time.time()
            poll_interval = 3
            last_code = None
            
            while time.time() - start_time < timeout:
                if ctx.is_stopped():
                    break
                
                remaining = timeout - (time.time() - start_time)
                ctx.emit_timer(remaining, timeout)
                
                try:
                    result = _sms_api_call("getStatus", api_key, {"id": str(activation_id)})
                    
                    if result.startswith("STATUS_OK:"):
                        code = result.split(":", 1)[1]
                        ctx.set(save_as, code)
                        elapsed = time.time() - start_time
                        print(f"  ✓ SMS code received: {code} ({elapsed:.0f}s)")
                        return StepResult.SUCCESS
                    
                    elif result.startswith("STATUS_WAIT_RETRY:"):
                        last_code = result.split(":", 1)[1]
                        print(f"  🔄 Waiting for new SMS (last: {last_code})...")
                    
                    elif result == "STATUS_WAIT_CODE":
                        elapsed = time.time() - start_time
                        print(f"  ⏳ Waiting... ({elapsed:.0f}s)")
                    
                    elif result == "STATUS_CANCEL":
                        print(f"  ✗ Activation was cancelled")
                        return StepResult.FAILED
                    
                    elif "NO_ACTIVATION" in result:
                        print(f"  ✗ Invalid activation ID: {activation_id}")
                        return StepResult.FAILED
                    
                    else:
                        print(f"  ⚠️ Unknown status: {result}")
                    
                except Exception as e:
                    print(f"  ⚠️ Poll error: {e}")
                
                interruptible_sleep(ctx, poll_interval)
            
            print(f"  ✗ SMS timeout after {timeout}s (or stopped)")
            return StepResult.FAILED
        
        # SMS Set Status - change activation status
        def action_sms_set_status(ctx: StepContext, from_data: str = "sms_activation_id",
                                   status: str = "6", **kwargs) -> StepResult:
            api_key = _get_sms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            activation_id = ctx.get(from_data)
            if not activation_id:
                print(f"  ✗ Activation ID not found in context key: {from_data}")
                return StepResult.FAILED
            
            status_labels = {"6": "Confirm", "8": "Cancel", "3": "Request another SMS"}
            label = status_labels.get(str(status), str(status))
            print(f"  📋 Setting status: {label} (ID: {activation_id})")
            
            try:
                result = _sms_api_call("setStatus", api_key, {
                    "id": str(activation_id), 
                    "status": str(status)
                })
                
                if "ACCESS_READY" in result:
                    print(f"  ✓ Phone ready for SMS")
                    return StepResult.SUCCESS
                elif "ACCESS_RETRY_GET" in result:
                    print(f"  ✓ Waiting for new SMS")
                    return StepResult.SUCCESS
                elif "ACCESS_ACTIVATION" in result:
                    print(f"  ✓ Activation confirmed")
                    return StepResult.SUCCESS
                elif "ACCESS_CANCEL" in result:
                    print(f"  ✓ Activation cancelled")
                    return StepResult.SUCCESS
                elif "EARLY_CANCEL_DENIED" in result:
                    print(f"  ✗ Cannot cancel yet (wait 2 min after purchase)")
                    return StepResult.FAILED
                elif "BAD_STATUS" in result:
                    print(f"  ✗ Invalid status: {status}")
                    return StepResult.FAILED
                else:
                    print(f"  ⚠️ Response: {result}")
                    return StepResult.SUCCESS
                    
            except Exception as e:
                print(f"  ✗ SMS API error: {e}")
                return StepResult.FAILED
        
        # SMS Get Balance - check account balance
        def action_sms_get_balance(ctx: StepContext, save_as: str = "sms_balance",
                                    **kwargs) -> StepResult:
            api_key = _get_sms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            try:
                result = _sms_api_call("getBalance", api_key)
                
                if result.startswith("ACCESS_BALANCE:"):
                    balance = result.split(":")[1]
                    ctx.set(save_as, balance)
                    print(f"  💰 SMSBower Balance: {balance}")
                    return StepResult.SUCCESS
                elif "BAD_KEY" in result:
                    print(f"  ✗ Invalid API key")
                    return StepResult.FAILED
                else:
                    print(f"  ✗ Error: {result}")
                    return StepResult.FAILED
                    
            except Exception as e:
                print(f"  ✗ SMS API error: {e}")
                return StepResult.FAILED

        # ==================== HeroSMS API Actions ====================
        
        HEROSMS_API = "https://hero-sms.com/stubs/handler_api.php"
        
        def _herosms_api_call(action: str, api_key: str, extra_params: Dict = None) -> str:
            """Helper: make HeroSMS API GET request and return response text"""
            import urllib.request
            import urllib.parse
            
            params = {"api_key": api_key, "action": action}
            if extra_params:
                params.update(extra_params)
            
            url = f"{HEROSMS_API}?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(url, headers={"User-Agent": "FlowRunner/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.read().decode('utf-8').strip()
        
        def _get_herosms_api_key(ctx: StepContext) -> str:
            """Helper: get API key from context"""
            key = ctx.get("herosms_api_key")
            if not key:
                print("  ✗ HeroSMS API key not found! Add HeroSMS Config node first.")
                return None
            return key
            
        def action_herosms_config(ctx: StepContext, api_key: str = None, 
                              save_as: str = "herosms_api_key", **kwargs) -> StepResult:
            if not api_key:
                print("  ✗ API key is required")
                return StepResult.FAILED
            
            ctx.set(save_as, api_key)
            print(f"  🔑 HeroSMS API key configured")
            return StepResult.SUCCESS
            
        def action_herosms_get_number(ctx: StepContext, service: str = None,
                                   country: str = "0", max_price: str = None,
                                   save_as: str = "herosms_phone", **kwargs) -> StepResult:
            api_key = _get_herosms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            if not service:
                print("  ✗ Service code is required (e.g. 'go' for Google)")
                return StepResult.FAILED
            
            print(f"  📱 Getting HeroSMS number for service: {service}, country: {country}")
            
            try:
                params = {"service": service, "country": str(country)}
                if max_price:
                    params["maxPrice"] = str(max_price)
                
                result = _herosms_api_call("getNumber", api_key, params)
                
                if result.startswith("ACCESS_NUMBER:"):
                    parts = result.split(":")
                    activation_id = parts[1]
                    phone_number = parts[2]
                    
                    ctx.set("herosms_activation_id", activation_id)
                    ctx.set(save_as, phone_number)
                    print(f"  ✓ HeroSMS Number: {phone_number} (ID: {activation_id})")
                    return StepResult.SUCCESS
                
                elif "NO_NUMBERS" in result:
                    print(f"  ✗ No numbers available for service={service}, country={country}")
                elif "NO_BALANCE" in result:
                    print(f"  ✗ Insufficient balance")
                elif "BAD_SERVICE" in result:
                    print(f"  ✗ Invalid service code: {service}")
                elif "BAD_KEY" in result:
                    print(f"  ✗ Invalid API key")
                else:
                    print(f"  ✗ Error: {result}")
                
                return StepResult.FAILED
                
            except Exception as e:
                print(f"  ✗ HeroSMS API error: {e}")
                return StepResult.FAILED
                
        def action_herosms_get_code(ctx: StepContext, from_data: str = "herosms_activation_id",
                                 timeout: float = 120, save_as: str = "herosms_code",
                                 **kwargs) -> StepResult:
            api_key = _get_herosms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            activation_id = ctx.get(from_data)
            if not activation_id:
                print(f"  ✗ Activation ID not found in context key: {from_data}")
                return StepResult.FAILED
            
            print(f"  ⏳ Waiting for HeroSMS code (ID: {activation_id}, timeout: {timeout}s)...")
            
            start_time = time.time()
            poll_interval = 3
            last_code = None
            
            while time.time() - start_time < timeout:
                if ctx.is_stopped():
                    break
                
                remaining = timeout - (time.time() - start_time)
                ctx.emit_timer(remaining, timeout)
                
                try:
                    result = _herosms_api_call("getStatus", api_key, {"id": str(activation_id)})
                    
                    if result.startswith("STATUS_OK:"):
                        code = result.split(":", 1)[1]
                        ctx.set(save_as, code)
                        elapsed = time.time() - start_time
                        print(f"  ✓ HeroSMS code received: {code} ({elapsed:.0f}s)")
                        return StepResult.SUCCESS
                    
                    elif result.startswith("STATUS_WAIT_RETRY:"):
                        last_code = result.split(":", 1)[1]
                        print(f"  🔄 Waiting for new SMS (last: {last_code})...")
                    
                    elif result == "STATUS_WAIT_CODE":
                        elapsed = time.time() - start_time
                        print(f"  ⏳ Waiting... ({elapsed:.0f}s)")
                    
                    elif result == "STATUS_CANCEL":
                        print(f"  ✗ Activation was cancelled")
                        return StepResult.FAILED
                    
                    elif "NO_ACTIVATION" in result:
                        print(f"  ✗ Invalid activation ID: {activation_id}")
                        return StepResult.FAILED
                    
                    else:
                        print(f"  ⚠️ Unknown status: {result}")
                    
                except Exception as e:
                    print(f"  ⚠️ Poll error: {e}")
                
                interruptible_sleep(ctx, poll_interval)
            
            print(f"  ✗ HeroSMS timeout after {timeout}s (or stopped)")
            return StepResult.FAILED
            
        def action_herosms_set_status(ctx: StepContext, from_data: str = "herosms_activation_id",
                                   status: str = "6", **kwargs) -> StepResult:
            api_key = _get_herosms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            activation_id = ctx.get(from_data)
            if not activation_id:
                print(f"  ✗ Activation ID not found in context key: {from_data}")
                return StepResult.FAILED
            
            status_labels = {"6": "Confirm", "8": "Cancel", "3": "Request another SMS"}
            label = status_labels.get(str(status), str(status))
            print(f"  📋 Setting HeroSMS status: {label} (ID: {activation_id})")
            
            try:
                result = _herosms_api_call("setStatus", api_key, {
                    "id": str(activation_id), 
                    "status": str(status)
                })
                
                if "ACCESS_READY" in result:
                    print(f"  ✓ Phone ready for SMS")
                    return StepResult.SUCCESS
                elif "ACCESS_RETRY_GET" in result:
                    print(f"  ✓ Waiting for new SMS")
                    return StepResult.SUCCESS
                elif "ACCESS_ACTIVATION" in result:
                    print(f"  ✓ Activation confirmed")
                    return StepResult.SUCCESS
                elif "ACCESS_CANCEL" in result:
                    print(f"  ✓ Activation cancelled")
                    return StepResult.SUCCESS
                elif "EARLY_CANCEL_DENIED" in result:
                    print(f"  ✗ Cannot cancel yet (wait 2 min after purchase)")
                    return StepResult.FAILED
                elif "BAD_STATUS" in result:
                    print(f"  ✗ Invalid status: {status}")
                    return StepResult.FAILED
                else:
                    print(f"  ⚠️ Response: {result}")
                    return StepResult.SUCCESS
                    
            except Exception as e:
                print(f"  ✗ HeroSMS API error: {e}")
                return StepResult.FAILED
                
        def action_herosms_get_balance(ctx: StepContext, save_as: str = "herosms_balance",
                                    **kwargs) -> StepResult:
            api_key = _get_herosms_api_key(ctx)
            if not api_key:
                return StepResult.FAILED
            
            try:
                result = _herosms_api_call("getBalance", api_key)
                
                if result.startswith("ACCESS_BALANCE:"):
                    balance = result.split(":")[1]
                    ctx.set(save_as, balance)
                    print(f"  💰 HeroSMS Balance: {balance}")
                    return StepResult.SUCCESS
                elif "BAD_KEY" in result:
                    print(f"  ✗ Invalid API key")
                    return StepResult.FAILED
                else:
                    print(f"  ✗ Error: {result}")
                    return StepResult.FAILED
                    
            except Exception as e:
                print(f"  ✗ HeroSMS API error: {e}")
                return StepResult.FAILED

        self._actions["shell"] = action_shell
        self._actions["close"] = action_close
        self._actions["clear_data"] = action_clear_data
        self._actions["ask_ai"] = action_ask_ai
        self._actions["condition"] = action_condition
        self._actions["data_source"] = action_data_source
        self._actions["fingerprint"] = action_fingerprint
        self._actions["sms_config"] = action_sms_config
        self._actions["sms_get_number"] = action_sms_get_number
        self._actions["sms_get_code"] = action_sms_get_code
        self._actions["sms_set_status"] = action_sms_set_status
        self._actions["sms_get_balance"] = action_sms_get_balance
        self._actions["herosms_config"] = action_herosms_config
        self._actions["herosms_get_number"] = action_herosms_get_number
        self._actions["herosms_get_code"] = action_herosms_get_code
        self._actions["herosms_set_status"] = action_herosms_set_status
        self._actions["herosms_get_balance"] = action_herosms_get_balance

        def _resolve_executable_path(exe_name: str) -> str:
            import shutil
            import os
            # If absolute path or exists in PATH
            if os.path.isabs(exe_name) or shutil.which(exe_name):
                return exe_name
            
            # Common LDPlayer installation paths
            drives = ["C:", "D:", "E:"]
            folders = [
                r"\LDPlayer\LDPlayer64",
                r"\XuanZhi\LDPlayer"
            ]
            for drive in drives:
                for folder in folders:
                    full_path = f"{drive}{folder}\\{exe_name}"
                    if os.path.exists(full_path):
                        return full_path
            return exe_name

        # LDPlayer Commands
        def action_ldplayer(ctx: StepContext, ld_action: str = "launch",
                        name_or_id: str = "0", new_name: str = "",
                        console_path: str = "dnconsole.exe", **kwargs) -> StepResult:
            """
            Execute LDPlayer console commands.
            Commands: launch, quit, quitall, add, copy, remove, rename, reboot
            """
            import subprocess
            
            resolved_path = _resolve_executable_path(console_path)
            cmd = [resolved_path, ld_action]
            
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            
            if ld_action in ["launch", "quit", "remove", "reboot"]:
                cmd.extend([flag, str(name_or_id)])
                
            elif ld_action == "add":
                if name_or_id and str(name_or_id) != "0":
                    cmd.extend(["--name", str(name_or_id)])
                    
            elif ld_action == "copy":
                cmd.extend(["--name", str(new_name), "--from", str(name_or_id)])
                
            elif ld_action == "rename":
                cmd.extend([flag, str(name_or_id), "--title", str(new_name)])

            if ld_action == "quitall":
                cmd = [resolved_path, "quitall"]
                
            print(f"  🎮 LDPlayer: {' '.join(cmd)}")
            try:
                timeout = 60 if ld_action in ["copy", "add"] else 30
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=timeout,
                    cwd=os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None
                )
                if result.returncode == 0:
                    print(f"  ✓ LDPlayer '{ld_action}' executed")
                    return StepResult.SUCCESS
                else:
                    print(f"  ✗ LDPlayer error: {result.stderr or result.stdout}")
                    return StepResult.FAILED
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                print(f"    Ensure {console_path} is in PATH or provide full path.")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ldplayer"] = action_ldplayer

        # LDPlayer Device Props
        def action_ld_device_props(ctx: StepContext, name_or_id: str = "0",
                                   imei: str = "auto", manufacturer: str = "auto",
                                   model: str = "auto", pnumber: str = "",
                                   console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            
            resolved_path = _resolve_executable_path(console_path)
            cmd = [resolved_path, "modify", flag, str(name_or_id)]
            
            if imei:
                cmd.extend(["--imei", str(imei).lower() if str(imei).lower() == "auto" else str(imei)])
            if manufacturer:
                cmd.extend(["--manufacturer", str(manufacturer).lower() if str(manufacturer).lower() == "auto" else str(manufacturer)])
            if model:
                cmd.extend(["--model", str(model).lower() if str(model).lower() == "auto" else str(model)])
            if pnumber:
                cmd.extend(["--pnumber", str(pnumber)])
                
            print(f"  📱 LD Device Props: {' '.join(cmd)}")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True, timeout=30,
                    cwd=os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None
                )
                if result.returncode == 0:
                    print(f"  ✓ LDPlayer device properties modified")
                    return StepResult.SUCCESS
                else:
                    print(f"  ✗ LDPlayer error: {result.stderr or result.stdout}")
                    return StepResult.FAILED
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                print(f"    Ensure {console_path} is in PATH or provide full path.")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_device_props"] = action_ld_device_props

        # LD Clone Instance
        def action_ld_clone_instance(ctx: StepContext, from_name_or_id: str = "0",
                                     new_name: str = "", console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            resolved_path = _resolve_executable_path(console_path)
            cmd = [resolved_path, "copy", "--name", str(new_name), "--from", str(from_name_or_id)]
            cwd = os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None
            
            print(f"  👯 LD Clone: {' '.join(cmd)}")
            try:
                # Run clone command (this might return immediately with code 1 depending on LDPlayer version)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=cwd)
                if result.returncode != 0:
                    print(f"  ⚠️ LDPlayer clone returned non-zero ({result.returncode}), output: {result.stderr or result.stdout}")
                    print(f"  ⏳ Waiting to see if clone '{new_name}' appears anyway...")
                else:
                    print(f"  ⏳ Waiting for clone '{new_name}' to appear and stabilize...")
                    
                # Monitor list2 to ensure the new instance has finished creating
                start_time = time.time()
                timeout = 180 # 3 minute timeout for cloning
                
                while time.time() - start_time < timeout:
                    if ctx.is_stopped():
                        return StepResult.FAILED
                        
                    list2_cmd = [resolved_path, "list2"]
                    list_result = subprocess.run(list2_cmd, capture_output=True, text=True, timeout=10, cwd=cwd)
                    if list_result.returncode == 0:
                        lines = list_result.stdout.strip().split('\n')
                        for line in lines:
                            parts = line.split(',')
                            if len(parts) >= 2 and parts[1] == new_name:
                                # Sometimes when it appears, we should wait just a tiny bit longer to be sure
                                # it's completely flushed to disk.
                                time.sleep(2)
                                print(f"  ✓ LDPlayer instance cloned to '{new_name}' ({time.time() - start_time:.1f}s)")
                                return StepResult.SUCCESS
                    
                    interruptible_sleep(ctx, 2.0)
                
                print(f"  ✗ Clone timeout after {timeout} seconds")
                return StepResult.FAILED
                
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_clone_instance"] = action_ld_clone_instance

        # LD Delete Instance
        def action_ld_delete_instance(ctx: StepContext, name_or_id: str = "0",
                                      console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            resolved_path = _resolve_executable_path(console_path)
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            cmd = [resolved_path, "remove", flag, str(name_or_id)]
            
            print(f"  🗑️ LD Delete: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None)
                if result.returncode == 0:
                    print(f"  ✓ LDPlayer instance '{name_or_id}' deleted")
                    return StepResult.SUCCESS
                else:
                    print(f"  ✗ LDPlayer delete error: {result.stderr or result.stdout}")
                    return StepResult.FAILED
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_delete_instance"] = action_ld_delete_instance

        # LD Start Instance
        def action_ld_start_instance(ctx: StepContext, name_or_id: str = "0",
                                     console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            resolved_path = _resolve_executable_path(console_path)
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            cmd = [resolved_path, "launch", flag, str(name_or_id)]
            
            print(f"  ▶️ LD Start: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None)
                if result.returncode == 0:
                    print(f"  ✓ LDPlayer instance '{name_or_id}' started")
                    return StepResult.SUCCESS
                else:
                    print(f"  ✗ LDPlayer start error: {result.stderr or result.stdout}")
                    return StepResult.FAILED
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_start_instance"] = action_ld_start_instance

        # LD Stop Instance
        def action_ld_stop_instance(ctx: StepContext, name_or_id: str = "0",
                                    console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            resolved_path = _resolve_executable_path(console_path)
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            cmd = [resolved_path, "quit", flag, str(name_or_id)]
            
            print(f"  ⏹️ LD Stop: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None)
                if result.returncode == 0:
                    print(f"  ✓ LDPlayer instance '{name_or_id}' stopped")
                    return StepResult.SUCCESS
                else:
                    print(f"  ✗ LDPlayer stop error: {result.stderr or result.stdout}")
                    return StepResult.FAILED
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_stop_instance"] = action_ld_stop_instance

        # LD Wait Boot
        def action_ld_wait_boot(ctx: StepContext, name_or_id: str = "0", timeout: float = 120,
                                console_path: str = "ldconsole.exe", **kwargs) -> StepResult:
            import subprocess
            resolved_path = _resolve_executable_path(console_path)
            is_index = str(name_or_id).isdigit()
            flag = "--index" if is_index else "--name"
            cmd_isrunning = [resolved_path, "isrunning", flag, str(name_or_id)]
            cmd_adb = [resolved_path, "adb", flag, str(name_or_id), "--command", "shell getprop sys.boot_completed"]
            cwd = os.path.dirname(resolved_path) if os.path.dirname(resolved_path) else None
            
            print(f"  ⏳ LD Wait Boot: Waiting up to {timeout}s for instance '{name_or_id}' to boot...")
            start_time = time.time()
            
            try:
                is_running = False
                while time.time() - start_time < timeout:
                    if ctx.is_stopped():
                        return StepResult.FAILED
                        
                    if not is_running:
                        result = subprocess.run(cmd_isrunning, capture_output=True, text=True, timeout=10, cwd=cwd)
                        if result.returncode == 0 and result.stdout.strip() == "running":
                            is_running = True
                            print(f"  ⏳ Process running, waiting for Android OS to finish booting...")
                    
                    if is_running:
                        adb_result = subprocess.run(cmd_adb, capture_output=True, text=True, timeout=10, cwd=cwd)
                        if adb_result.returncode == 0:
                            output = adb_result.stdout.strip()
                            if output == "1":
                                # Wait an extra few seconds to let services start
                                time.sleep(4)
                                print(f"  ✓ LDPlayer instance '{name_or_id}' has booted completely ({time.time() - start_time:.1f}s)")
                                return StepResult.SUCCESS
                    
                    interruptible_sleep(ctx, 3.0)
                
                print(f"  ✗ Boot timeout after {timeout} seconds")
                return StepResult.FAILED
                
            except FileNotFoundError:
                print(f"  ✗ Executable not found: {resolved_path}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ LDPlayer execution failed: {e}")
                return StepResult.FAILED

        self._actions["ld_wait_boot"] = action_ld_wait_boot

        # Wait Device Connects to ADB
        def action_wait_device(ctx: StepContext, timeout: float = 60, **kwargs) -> StepResult:
            from utils import list_devices as _list_devices
            print(f"  ⏳ Wait Device: Scanning for any online device (timeout {timeout}s)...")
            start_time = time.time()
            last_connect_time = 0
            
            while time.time() - start_time < timeout:
                if ctx.is_stopped():
                    return StepResult.FAILED
                
                try:
                    devices = _list_devices()
                    online = [d for d in devices if d['status'] == 'device']
                    
                    # Filter out devices that are already claimed by other runners
                    with DEVICE_LOCK:
                        available = [d for d in online if d['id'] not in CLAIMED_DEVICES]
                    
                    if available:
                        target = available[0]
                        target_id = target['id']
                        model = target.get('model', target_id)
                        
                        # Build adb command for this specific device
                        cmd_base = ["adb", "-s", target_id]
                        
                        elapsed = time.time() - start_time
                        # Check if fully booted
                        is_booted = False
                        try:
                            boot_res = subprocess.run(
                                cmd_base + ["shell", "getprop", "sys.boot_completed"],
                                capture_output=True, text=True, timeout=5
                            )
                            is_booted = boot_res.returncode == 0 and "1" in boot_res.stdout
                        except subprocess.TimeoutExpired:
                            print(f"  ⏳ Device {model} ADB responding slowly (boot check timeout)... ({elapsed:.0f}s)")
                        except Exception as inner_e:
                            print(f"  ⏳ Device {model} ADB check error: {inner_e}")
                        
                        if is_booted:
                            print(f"  ✓ Device found: {model} ({target_id})")
                            
                            # Auto-connect: update portal to this device
                            try:
                                from utils import connect as _connect
                                new_portal = _connect(target_id)
                                
                                # Release old device and claim new one
                                if self.portal and self.portal.device_id:
                                    release_device(self.portal.device_id)
                                claim_device(target_id)
                                
                                self.portal = new_portal
                                ctx.portal = new_portal
                                print(f"  🔄 Portal connected to: {model}")
                                
                                time.sleep(1)
                                return StepResult.SUCCESS
                            except Exception as e:
                                print(f"  ⚠ Connect failed: {e}, retrying...")
                        else:
                            print(f"  ⏳ Device {model} found, waiting for OS boot... ({elapsed:.0f}s)")
                    else:
                        # Attempt to connect to common emulator ports if no device is found
                        # (LDPlayer/Nox/Memu/Bluestacks use 5555, 5557, 5559...)
                        # Trigger this every 5 seconds
                        if time.time() - last_connect_time > 5:
                            for port in range(5555, 5586, 2):
                                subprocess.Popen(
                                    ["adb", "connect", f"127.0.0.1:{port}"],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                            last_connect_time = time.time()
                except Exception as e:
                    print(f"  ⚠️ Wait Device inner loop error: {e}")
                
                interruptible_sleep(ctx, 2.0)
                
            print(f"  ✗ Wait Device timeout after {timeout} seconds")
            return StepResult.FAILED
            
        self._actions["wait_device"] = action_wait_device

        # Write to TXT - append a row of data to a text file each time this node is hit
        def action_write_txt(ctx: StepContext, file_path: str = "output.txt",
                              content: str = "", columns: str = "",
                              separator: str = "\t",
                              include_timestamp: bool = True, **kwargs) -> StepResult:
            """
            Write context data as a new row to a TXT file.
            Supports two modes:
            
            1. Format mode (use 'content' param):
               Use {key} placeholders to reference saved data.
               Example: "{email},{sms_balance},{sms_phone}"
               Each {key} is replaced with the value from context (e.g. from save_as).
               
            2. Columns mode (use 'columns' param):
               Comma-separated list of data keys. E.g. "email,sms_balance,sms_phone"
               Writes as separator-delimited columns with header row.
               If empty, writes ALL context data.
            
            Parameters:
            - file_path: Path to output file (relative to project root or absolute)
            - content: Format template with {key} placeholders (priority over columns)
            - columns: Comma-separated data keys for column mode
            - separator: Column separator for columns mode (default: tab)
            - include_timestamp: Add timestamp column/prefix
            """
            print(f"  📄 DEBUG write_txt: file_path={file_path}, content={repr(content)}, columns={repr(columns)}, separator={repr(separator)}, include_timestamp={include_timestamp}")
            print(f"  📄 DEBUG context data keys: {list(ctx.data.keys())}")
            try:
                # Resolve file path
                if not os.path.isabs(file_path):
                    file_path = os.path.join(str(BASE_DIR), file_path)
                
                # Ensure directory exists
                dir_path = os.path.dirname(file_path)
                if dir_path:
                    os.makedirs(dir_path, exist_ok=True)
                
                file_exists = os.path.exists(file_path)
                
                # Mode 1: Format template with {key} placeholders
                if content:
                    # Replace all {key} placeholders with context data
                    line = content
                    for key, value in ctx.data.items():
                        line = line.replace(f"{{{key}}}", str(value))
                    
                    # Add timestamp prefix if enabled
                    if include_timestamp:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        line = f"{timestamp}{separator}{line}"
                    
                    with open(file_path, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                    
                    print(f"  📄 Written to: {file_path}")
                    preview = line[:80] + ('...' if len(line) > 80 else '')
                    print(f"     Line: {preview}")
                    return StepResult.SUCCESS
                
                # Mode 2: Columns mode
                if columns:
                    col_list = [c.strip() for c in columns.split(",") if c.strip()]
                else:
                    # Auto: all non-internal keys
                    col_list = [k for k in ctx.data.keys() if not k.startswith("_")]
                
                if not col_list:
                    print("  ⚠️ No data to write")
                    return StepResult.SUCCESS
                
                # Build header and row
                header_cols = list(col_list)
                row_vals = [str(ctx.get(c, "")) for c in col_list]
                
                if include_timestamp:
                    header_cols.insert(0, "timestamp")
                    row_vals.insert(0, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                with open(file_path, "a", encoding="utf-8") as f:
                    if not file_exists:
                        f.write(separator.join(header_cols) + "\n")
                    f.write(separator.join(row_vals) + "\n")
                
                print(f"  📄 Written to: {file_path}")
                preview = separator.join(row_vals[:4])
                if len(row_vals) > 4:
                    preview += '...'
                print(f"     Data: {preview}")
                return StepResult.SUCCESS
                
            except Exception as e:
                print(f"  ✗ Write TXT error: {e}")
                return StepResult.FAILED
        
        self._actions["write_txt"] = action_write_txt
    
    def register(self, name: str, action: Callable):
        """Register a custom action"""
        self._actions[name] = action
    
    def execute(self, action: str, ctx: StepContext, params: Dict) -> StepResult:
        """Execute an action"""
        if action not in self._actions:
            print(f"  ✗ Unknown action: {action}")
            return StepResult.FAILED
        return self._actions[action](ctx, **params)


class FlowRunner:
    """
    Executes a flow of steps
    """
    
    def __init__(self, portal: Optional[DroidrunPortal] = None):
        self.portal = portal or connect()
        self.registry = StepRegistry(self.portal)
        self._stop_flag = False
        self._on_device_switched_cb = None  # Callback when device switches
        
    def stop(self):
        """Signal the runner to stop"""
        print("🛑 Stop signal received")
        self._stop_flag = True
    
    def switch_device(self, ctx: StepContext, callback=None) -> bool:
        """
        Try to switch to another connected device when current device disconnects.
        Returns True if successfully switched, False if no other device available.
        """
        current_id = self.portal.device_id
        print(f"🔄 Device disconnected ({current_id or 'auto'}), searching for another device...")
        
        devices = list_devices()
        online_devices = [d for d in devices if d['status'] == 'device']
        
        # Filter out current device
        candidates = [d for d in online_devices if d['id'] != current_id]
        
        if not candidates:
            print("❌ No other connected device found")
            if callback:
                callback({"type": "log", "message": "❌ No other device available to switch to", "level": "error"})
            return False
        
        new_device = candidates[0]
        new_id = new_device['id']
        print(f"✅ Switching to device: {new_id} ({new_device.get('model', '')})")
        
        try:
            new_portal = connect(new_id)
            
            # Update all references
            self.portal = new_portal
            self.registry.portal = new_portal
            ctx.portal = new_portal
            
            msg = f"🔄 Switched to device: {new_device.get('model', new_id)}"
            print(msg)
            if callback:
                callback({"type": "log", "message": msg, "level": "warning"})
                callback({"type": "device_switched", "device_id": new_id, "model": new_device.get('model', '')})
            
            # Notify app.py via callback
            if self._on_device_switched_cb:
                self._on_device_switched_cb(new_id, new_portal)
            
            return True
        except Exception as e:
            print(f"❌ Failed to connect to {new_id}: {e}")
            if callback:
                callback({"type": "log", "message": f"❌ Failed to switch: {e}", "level": "error"})
            return False
    
    def run(self, steps: List[Dict], session_id: str = "default",
            initial_data: Optional[Dict] = None,
            callback: Optional[Callable[[Dict], None]] = None) -> StepContext:
        """
        Run a flow
        
        Args:
            steps: List of step configurations
            session_id: Session ID for OTP
            initial_data: Initial data to set in context
            callback: Function to call with progress updates
        
        Returns:
            StepContext with results
        """
        self._stop_flag = False
        ctx = StepContext(
            portal=self.portal,
            session_id=session_id,
            data=initial_data or {},
            _is_stopped_cb=lambda: self._stop_flag
        )
        
        # Attach log callback that formats a log message to the frontend stream
        if callback:
            ctx._log_cb = lambda msg, lvl: callback({"type": "log", "message": msg, "level": lvl})
        
        print(f"\n{'='*60}")
        print(f"🚀 Running flow: {len(steps)} steps")
        print(f"   Session: {session_id}")
        print(f"{'='*60}\n")
        
        for i, step_dict in enumerate(steps, 1):
            # Check stop flag
            if self._stop_flag:
                print("🛑 Flow stopped by user")
                if callback:
                    callback({"type": "stopped", "step": "Flow stopped"})
                break

            step = StepConfig(
                name=step_dict.get("name", f"Step {i}"),
                action=step_dict.get("action", ""),
                params=step_dict.get("params", {}),
                wait_before=step_dict.get("wait_before", 0.5),
                wait_after=step_dict.get("wait_after", 0.3),
                retry_count=step_dict.get("retry_count", 3),
                retry_delay=step_dict.get("retry_delay", 1.0),
                optional=step_dict.get("optional", False),
            )
            
            print(f"[{i}/{len(steps)}] {step.name}")
            
            # Notify start
            if callback:
                callback({
                    "type": "step_start",
                    "index": i-1, # 0-based for array access in JS
                    "step": step.name,
                    "id": step_dict.get("id") # Pass original ID if available
                })
            
            # Wait before
            if step.wait_before > 0:
                time.sleep(step.wait_before)
            
            # Execute with retry
            result = StepResult.FAILED
            for attempt in range(step.retry_count):
                result = self.registry.execute(step.action, ctx, step.params)
                
                if result == StepResult.SUCCESS:
                    break
                elif result == StepResult.RETRY or result == StepResult.FAILED:
                    # Check if device disconnected
                    if not self.portal.ping():
                        if self.switch_device(ctx, callback):
                            # Retry same step with new device
                            result = self.registry.execute(step.action, ctx, step.params)
                            if result == StepResult.SUCCESS:
                                break
                    
                    if attempt < step.retry_count - 1:
                        print(f"  ↻ Retry {attempt + 2}/{step.retry_count}")
                        time.sleep(step.retry_delay)
            
            # Record result
            result_data = {
                "step": step.name,
                "action": step.action,
                "result": result.value,
                "timestamp": datetime.now().isoformat()
            }
            if step_dict.get("id"):
                result_data["id"] = step_dict.get("id")
            
            ctx.step_results.append(result_data)
            
            # Notify end
            if callback:
                callback({
                    "type": "step_end",
                    "index": i-1,
                    "step": step.name,
                    "result": result.value,
                    "id": step_dict.get("id")
                })
            
            # Handle failure
            if result == StepResult.FAILED:
                if step.optional:
                    print(f"  ⚠ Failed (optional, continuing)")
                else:
                    print(f"  ✗ Failed - stopping flow")
                    break
            else:
                print(f"  ✓ Success")
            
            # Wait after
            if step.wait_after > 0:
                time.sleep(step.wait_after)
        
        print(f"\n{'='*60}")
        success_count = sum(1 for r in ctx.step_results if r["result"] == "success")
        print(f"✓ Flow complete: {success_count}/{len(ctx.step_results)} steps succeeded")
        print(f"{'='*60}\n")
        
        return ctx
    
    def run_graph(self, flow_data: Dict, session_id: str = "default",
                  initial_data: Optional[Dict] = None,
                  callback: Optional[Callable[[Dict], None]] = None,
                  max_iterations: int = 100,
                  start_node_id: str = "start") -> StepContext:
        """
        Run a flow using graph-based execution with branching support.
        
        Args:
            flow_data: Full flow data including _editor with nodes and connections
            session_id: Session ID for OTP
            initial_data: Initial data to set in context
            callback: Function to call with progress updates
            max_iterations: Max iterations to prevent infinite loops
            start_node_id: ID of the node to start execution from (default: "start")
        
        Returns:
            StepContext with results
        """
        self._stop_flag = False
        ctx = StepContext(
            portal=self.portal,
            session_id=session_id,
            data=initial_data or {},
            _is_stopped_cb=lambda: self._stop_flag
        )
        
        # Attach log callback that formats a log message to the frontend stream
        if callback:
            ctx._log_cb = lambda msg, lvl: callback({"type": "log", "message": msg, "level": lvl})
            ctx._timer_cb = lambda node_id, remaining, total: callback({
                "type": "timer",
                "id": node_id,
                "remaining": round(remaining, 1),
                "total": round(total, 1)
            })
        
        # Extract editor data
        editor = flow_data.get("_editor", {})
        nodes = {n["id"]: n for n in editor.get("nodes", [])}
        connections = editor.get("connections", [])
        
        # Build connection map: from_node -> {port: to_node}
        conn_map = {}
        for conn in connections:
            from_id = conn["from"]
            from_port = conn.get("fromPort", "out")
            to_id = conn["to"]
            
            if from_id not in conn_map:
                conn_map[from_id] = {}
            conn_map[from_id][from_port] = to_id
        
        print(f"\n{'='*60}")
        print(f"🚀 Running flow (graph mode): {len(nodes)} nodes")
        print(f"   Session: {session_id}")
        print(f"   Start Node: {start_node_id}")
        print(f"{'='*60}\n")
        
        # Start from 'start' node or specified node
        current_node_id = start_node_id
        step_count = 0
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check stop flag
            if self._stop_flag:
                print("🛑 Flow stopped by user")
                if callback:
                    callback({"type": "stopped", "step": "Flow stopped"})
                break
            
            # For start node, just follow output
            if current_node_id == "start":
                next_id = conn_map.get(current_node_id, {}).get("out")
                if not next_id:
                    print("⚠ No node connected to start")
                    break
                current_node_id = next_id
                continue
            
            # Get current node
            node = nodes.get(current_node_id)
            if not node:
                print(f"⚠ Node {current_node_id} not found")
                break
            
            node_type = node.get("type", "")
            params = node.get("params", {})
            step_count += 1
            
            step_name = f"{node_type}: {params.get('text', params.get('prompt', params.get('package', '')))[:30]}"
            print(f"[Step {step_count}] {node.get('id')} - {node_type}")
            
            # Notify start
            if callback:
                # If this is a data source node starting, signal frontend to reset visual statuses
                # This creates the effect of "clearing the path" for the new loop iteration
                reset_flag = (node_type == 'data_source')
                
                callback({
                    "type": "step_start",
                    "index": step_count - 1,
                    "step": step_name,
                    "id": node.get("id"),
                    "reset_flow": reset_flag
                })
            
            # Set current node id for timer events
            ctx._current_node_id = node.get("id")
            
            # Wait before
            time.sleep(0.3)
            
            # Execute the action
            result = self.registry.execute(node_type, ctx, params)
            
            # Auto-switch device if disconnected
            if result == StepResult.FAILED and not self.portal.ping():
                if self.switch_device(ctx, callback):
                    # Retry same node with new device
                    print(f"  ↻ Retrying node after device switch...")
                    result = self.registry.execute(node_type, ctx, params)
            
            # Record result
            ctx.step_results.append({
                "id": node.get("id"),
                "step": step_name,
                "action": node_type,
                "result": result.value,
                "timestamp": datetime.now().isoformat()
            })
            
            # Notify end
            if callback:
                callback({
                    "type": "step_end",
                    "index": step_count - 1,
                    "step": step_name,
                    "result": result.value,
                    "id": node.get("id")
                })
            
            # Wait after
            time.sleep(0.2)
            
            # Determine next node based on result
            node_conns = conn_map.get(current_node_id, {})
            
            if node_type in ["condition", "sms_get_code", "sms_get_number", "herosms_get_code", "herosms_get_number"]:
                # Condition/SMS node: follow yes/no based on result
                if result == StepResult.SUCCESS:
                    # Condition was TRUE, follow "yes" or "out"
                    next_id = node_conns.get("yes") or node_conns.get("out")
                    print(f"  → Following YES branch")
                else:
                    # Condition was FALSE, follow "no"
                    next_id = node_conns.get("no")
                    print(f"  → Following NO branch")
            else:
                # Regular node: follow "out"
                next_id = node_conns.get("out")
                
                # If failed and not optional, stop
                if result == StepResult.FAILED:
                    print(f"  ✗ Failed - stopping flow")
                    break
            
            if not next_id:
                print(f"🏁 End of branch")
                break
            
            current_node_id = next_id
        
        if iteration >= max_iterations:
            print(f"⚠ Max iterations ({max_iterations}) reached - possible infinite loop")
        
        print(f"\n{'='*60}")
        success_count = sum(1 for r in ctx.step_results if r["result"] == "success")
        print(f"✓ Flow complete: {success_count}/{len(ctx.step_results)} steps executed")
        print(f"{'='*60}\n")
        
        return ctx
    
    def run_batch(self, steps: List[Dict], data_rows: List[Dict],
                  session_prefix: str = "batch",
                  callback: Optional[Callable[[Dict], None]] = None) -> List[StepContext]:
        """
        Run the same flow multiple times with different data rows
        
        Args:
            steps: List of step configurations (without data_source step)
            data_rows: List of data dicts, one per iteration
            session_prefix: Prefix for session IDs
            callback: Progress callback
        
        Returns:
            List of StepContext for each row
        """
        results = []
        total_rows = len(data_rows)
        
        # Check if flow has explicit "next_row" node
        # If yes, we only continue if that node is executed
        has_next_row_control = any(s.get("action") == "next_row" for s in steps)
        if has_next_row_control:
            print(f"⚡ Flow has 'next_row' explicit control enabled")
        
        for row_idx, row_data in enumerate(data_rows):
            if self._stop_flag:
                print("🛑 Batch stopped by user")
                if callback:
                    callback({"type": "batch_stopped", "row": row_idx})
                break
            
            session_id = f"{session_prefix}_{row_idx}"
            
            # Notify batch progress
            if callback:
                callback({
                    "type": "batch_row_start",
                    "row_index": row_idx,
                    "total_rows": total_rows,
                    "row_data": row_data
                })
            
            print(f"\n{'='*60}")
            print(f"🔄 Batch [{row_idx + 1}/{total_rows}]")
            print(f"   Data: {row_data}")
            print(f"{'='*60}")
            
            # Run flow with this row's data
            # Determine if we should use graph mode or linear mode
            # For now, default to run() as steps passed are usually linear
            # TODO: Improve this to support graph execution inside batch
            ctx = self.run(steps, session_id, initial_data=row_data, callback=callback)
            results.append(ctx)
            
            # Notify batch row complete
            if callback:
                success_count = sum(1 for r in ctx.step_results if r["result"] == "success")
                callback({
                    "type": "batch_row_end",
                    "row_index": row_idx,
                    "total_rows": total_rows,
                    "success": success_count == len(ctx.step_results),
                    "results": ctx.step_results
                })
            
            # Check loop condition
            if has_next_row_control:
                should_continue = ctx.get("_batch_continue", False)
                if not should_continue:
                    print(f"🛑 Batch stopped: 'Next Row' node not reached (Row {row_idx + 1})")
                    if callback:
                        callback({"type": "batch_stopped", "row": row_idx, "reason": "no_next_row_trigger"})
                    break
        
        print(f"\n{'='*60}")
        print(f"✅ Batch complete: {len(results)}/{total_rows} rows processed")
        print(f"{'='*60}\n")
        
        return results
    
    def run_file(self, filepath: str, session_id: str = "default",
                 initial_data: Optional[Dict] = None,
                 callback: Optional[Callable[[Dict], None]] = None) -> StepContext:
        """Run flow from JSON file"""
        with open(filepath) as f:
            flow = json.load(f)
        
        steps = flow.get("steps", flow) if isinstance(flow, dict) else flow
        data = {**(flow.get("data", {}) if isinstance(flow, dict) else {}), 
                **(initial_data or {})}
        
        return self.run(steps, session_id, data, callback)
    
    def run_file_batch(self, filepath: str, session_prefix: str = "batch",
                       callback: Optional[Callable[[Dict], None]] = None) -> List[StepContext]:
        """
        Run flow from JSON file with batch data from data_source step
        
        Automatically detects data_source step and loops through rows
        """
        with open(filepath) as f:
            flow = json.load(f)
        
        steps = flow.get("steps", flow) if isinstance(flow, dict) else flow
        
        # Find and extract data_source step
        data_rows = []
        filtered_steps = []
        
        for step in steps:
            if step.get("action") == "data_source":
                # Extract rows from data_source
                params = step.get("params", {})
                rows = params.get("rows", [])
                if rows:
                    data_rows = rows
                    print(f"📊 Found data_source with {len(rows)} rows")
            else:
                filtered_steps.append(step)
        
        if data_rows:
            # Run batch mode
            return self.run_batch(filtered_steps, data_rows, session_prefix, callback)
        else:
            # No data source, run single
            ctx = self.run(filtered_steps, session_prefix, callback=callback)
            return [ctx]


def create_flow_template(filepath: str):
    """Create a sample flow template"""
    template = {
        "name": "Sample Registration Flow",
        "description": "Template for app registration automation",
        "data": {
            "email": "user@example.com",
            "username": "username123"
        },
        "steps": [
            {
                "name": "Launch App",
                "action": "launch",
                "params": {"package": "com.example.app"}
            },
            {
                "name": "Wait for Welcome Screen",
                "action": "wait",
                "params": {"text": "Welcome", "timeout": 10}
            },
            {
                "name": "Tap Sign Up",
                "action": "tap",
                "params": {"text": "Sign Up"}
            },
            {
                "name": "Input Email",
                "action": "tap",
                "params": {"text": "Email"}
            },
            {
                "name": "Type Email",
                "action": "type",
                "params": {"from_data": "email"}
            },
            {
                "name": "Press Enter",
                "action": "key",
                "params": {"key": "enter"}
            },
            {
                "name": "Wait for OTP",
                "action": "otp",
                "params": {"timeout": 120, "save_as": "otp"}
            },
            {
                "name": "Type OTP",
                "action": "type",
                "params": {"from_data": "otp"}
            },
            {
                "name": "Capture TOTP Key",
                "action": "capture",
                "params": {"resource_id": "totp-key", "save_as": "totp_secret"}
            },
            {
                "name": "Generate TOTP",
                "action": "totp",
                "params": {"from_data": "totp_secret", "save_as": "totp_code"}
            },
            {
                "name": "Type TOTP",
                "action": "type",
                "params": {"from_data": "totp_code"}
            },
            {
                "name": "Complete",
                "action": "wait",
                "params": {"text": "Success"}
            }
        ]
    }
    
    with open(filepath, 'w') as f:
        json.dump(template, f, indent=2)
    print(f"✓ Template saved to {filepath}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Flow Runner")
    parser.add_argument("flow", nargs="?", help="Flow JSON file to run")
    parser.add_argument("-t", "--template", help="Create template file")
    parser.add_argument("-s", "--session", default="default", help="Session ID for OTP")
    parser.add_argument("-d", "--data", help="JSON data to pass to flow")
    
    args = parser.parse_args()
    
    if args.template:
        create_flow_template(args.template)
    elif args.flow:
        # Start OTP server
        start_server()
        
        # Parse initial data
        initial_data = {}
        if args.data:
            initial_data = json.loads(args.data)
        
        # Run flow
        runner = FlowRunner()
        ctx = runner.run_file(args.flow, args.session, initial_data)
        
        # Print captured data
        if ctx.data:
            print("Captured data:")
            for k, v in ctx.data.items():
                print(f"  {k}: {v}")
    else:
        parser.print_help()
