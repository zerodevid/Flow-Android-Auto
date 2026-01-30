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

# Disable proxy for localhost to avoid timeouts
os.environ["no_proxy"] = "127.0.0.1,localhost"

# Load environment variables from .env file
def load_dotenv():
    """Load .env file from project root"""
    env_paths = [
        '/home/zeroserver/Project/auto_register/.env',
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

sys.path.insert(0, '/home/zeroserver/Project/auto_register')
from utils import connect, DroidrunPortal
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
                time.sleep(delay)
            
            # Tap by coordinates (no validation needed)
            if x is not None and y is not None:
                self.portal.tap(x, y)
                return StepResult.SUCCESS
            
            # Wait for element to appear first if wait_for is True
            # Only wait for text, not resource_id (resource_id tapping handles its own lookup)
            if wait_for and timeout > 0 and text:
                elem = self.portal.wait_for_text(text, timeout=timeout)
                if not elem:
                    print(f"  ✗ Element not found: {text}")
                    return StepResult.FAILED
            
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
                        delay: float = 0, **kwargs) -> StepResult:
            # Delay before action
            if delay > 0:
                time.sleep(delay)
            
            value = text
            if from_data:
                value = ctx.get(from_data)
            if value:
                self.portal.type_text(value, clear_first=clear)
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Wait for text
        def action_wait(ctx: StepContext, text: str = None, 
                        timeout: float = 10, **kwargs) -> StepResult:
            if text:
                elem = self.portal.wait_for_text(text, timeout=timeout)
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
                
                time.sleep(poll_interval)
            
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
            otp = wait_otp(session, timeout=timeout)
            if otp:
                ctx.set(save_as, otp)
                print(f"  ✓ OTP received: {otp}")
                return StepResult.SUCCESS
            print("  ✗ OTP timeout")
            return StepResult.FAILED
        
        # Generate and input TOTP
        def action_totp(ctx: StepContext, secret: str = None,
                        from_data: str = None, save_as: str = "totp",
                        min_remaining: int = 5, **kwargs) -> StepResult:
            key = secret
            if from_data:
                key = ctx.get(from_data)
            if key:
                code = wait_for_fresh_totp(key, min_remaining=min_remaining)
                ctx.set(save_as, code)
                print(f"  ✓ TOTP generated: {code}")
                return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Press key
        def action_key(ctx: StepContext, key: str = None, **kwargs) -> StepResult:
            key_codes = {
                "enter": 66, "back": 4, "home": 3, "recent": 187,
                "backspace": 67, "tab": 61, "escape": 111,
            }
            code = key_codes.get(key.lower(), int(key) if key.isdigit() else 0)
            if code:
                self.portal.press_key(code)
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
                ["adb", "shell", "dumpsys", "window", "windows"],
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
            
            subprocess.run([
                "adb", "shell", "am", "start", "-a", "android.intent.action.VIEW",
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
                    subprocess.run(["adb", "shell", "input", "keyevent", "279"], timeout=2)
                    print("  📋 Sent PASTE keycode")
                    time.sleep(0.5)
                    
                    # Tap Send
                    if self.portal.tap_text("Send Manual"):
                        print("  ✓ Tapped Send Manual button")
                    else:
                        # Try generic enter
                        subprocess.run(["adb", "shell", "input", "keyevent", "66"], timeout=2)
                    
                    time.sleep(1)
                    clipboard_data = check_data()

            # Step 5: Close browser and return to original app

            # Step 5: Close browser and return to original app
            print("  🔙 Returning to app...")
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"], timeout=3)
            time.sleep(0.3)
            subprocess.run(["adb", "shell", "input", "keyevent", "KEYCODE_BACK"], timeout=3)
            time.sleep(0.3)
            
            # Force return to original app if we know it
            if current_package:
                subprocess.run([
                    "adb", "shell", "am", "start", "-n",
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
            time.sleep(seconds)
            return StepResult.SUCCESS
        
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
            print(f"  📡 HTTP Request: {method} {url}")
            
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
                        print(f"  ✓ Response saved to '{save_response}'")
                    
                    print(f"  ✓ HTTP Request success: {status}")
                    return StepResult.SUCCESS
                    
            except urllib.error.HTTPError as e:
                print(f"  ✗ HTTP Request error: {e.code} {e.reason}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ HTTP Request error: {e}")
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
                    ["adb", "shell"] + command.split(),
                    capture_output=True, text=True, timeout=10
                )
                print(f"  📟 Shell: {command}")
                if result.returncode == 0:
                    return StepResult.SUCCESS
            return StepResult.FAILED
        
        # Close/Force-stop app (remove from RAM)
        def action_close(ctx: StepContext, package: str = None, **kwargs) -> StepResult:
            if package:
                result = subprocess.run(
                    ["adb", "shell", "am", "force-stop", package],
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
                    ["adb", "shell", "rm", "-rf", f"/data/data/{package}/cache/*"],
                    capture_output=True, text=True, timeout=10
                )
                print(f"  🧹 Cache cleared: {package}")
            else:
                # Clear all app data (requires root or run-as for some apps)
                result = subprocess.run(
                    ["adb", "shell", "pm", "clear", package],
                    capture_output=True, text=True, timeout=15
                )
                if "Success" in result.stdout:
                    print(f"  🗑️ Data cleared: {package}")
                    return StepResult.SUCCESS
                else:
                    print(f"  ⚠️ Clear result: {result.stdout.strip()}")
                    # Try alternative method
                    subprocess.run(
                        ["adb", "shell", "am", "force-stop", package],
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
                print("  ✗ No prompt provided")
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
            
            print(f"  🤖 Asking AI ({provider})...")
            print(f"     Prompt: {final_prompt[:100]}...")
            
            try:
                response_text = None
                
                if provider == "gemini":
                    # Use Gemini API
                    api_key = os.environ.get("GEMINI_API_KEY", "")
                    if not api_key:
                        print("  ✗ GEMINI_API_KEY not set")
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
                        print("  ✗ OPENAI_API_KEY not set")
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
                    print(f"  ✗ Unknown provider: {provider}")
                    return StepResult.FAILED
                
                if response_text:
                    # Clean up response (remove extra whitespace)
                    response_text = response_text.strip()
                    ctx.set(save_as, response_text)
                    print(f"  ✓ AI Response saved to '{save_as}'")
                    print(f"     Response: {response_text[:100]}...")
                    return StepResult.SUCCESS
                
                print("  ✗ Empty response from AI")
                return StepResult.FAILED
                
            except urllib.error.HTTPError as e:
                print(f"  ✗ AI HTTP Error: {e.code} {e.reason}")
                return StepResult.FAILED
            except Exception as e:
                print(f"  ✗ AI Error: {e}")
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
            if index is None:
                index = int(start_index)
            
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
                    ["adb", "emu", "finger", "touch", str(finger_id)],
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
                        ["adb", "shell", "input", "keyevent", "KEYCODE_FINGERPRINT"],
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

        self._actions["shell"] = action_shell
        self._actions["close"] = action_close
        self._actions["clear_data"] = action_clear_data
        self._actions["ask_ai"] = action_ask_ai
        self._actions["condition"] = action_condition
        self._actions["data_source"] = action_data_source
        self._actions["fingerprint"] = action_fingerprint
    
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
        
    def stop(self):
        """Signal the runner to stop"""
        print("🛑 Stop signal received")
        self._stop_flag = True
    
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
            data=initial_data or {}
        )
        
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
            data=initial_data or {}
        )
        
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
            
            # Wait before
            time.sleep(0.3)
            
            # Execute the action
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
            
            if node_type == "condition":
                # Condition node: follow yes/no based on result
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
