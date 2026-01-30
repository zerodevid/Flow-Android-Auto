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
            if wait_for and timeout > 0:
                target_text = text or resource_id
                if target_text:
                    elem = self.portal.wait_for_text(target_text, timeout=timeout)
                    if not elem:
                        print(f"  ✗ Element not found: {target_text}")
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
        
        # Wait for OTP from server
        def action_otp(ctx: StepContext, timeout: float = 120, 
                       save_as: str = "otp", clear_first: bool = True, **kwargs) -> StepResult:
            # Clear old OTP before waiting
            if clear_first:
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"http://127.0.0.1:5000/clear",
                        data=json.dumps({"session_id": ctx.session_id}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=5)
                    print(f"  🗑️ Cleared old OTP for session: {ctx.session_id}")
                except Exception:
                    pass
            
            print(f"  ⏳ Waiting for OTP (session: {ctx.session_id})...")
            otp = wait_otp(ctx.session_id, timeout=timeout)
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
                print("  🖱️ Performing browser interaction...")
                # New Strategy: Tap "PASTE CLIPBOARD" button first (User Gesture)
                
                # 1. Try tapping the big green button (fuzzy match)
                if self.portal.tap_text("PASTE CLIPBOARD") or self.portal.tap_text("PASTE"):
                    print("  ✓ Tapped 'PASTE CLIPBOARD' button")
                    time.sleep(1)
                    
                    # 2. Handle Permission Popup (if any)
                    # Chrome might ask "Allow Chrome to paste from your clipboard?"
                    if self.portal.tap_text("Allow"):
                        print("  ✓ Tapped 'Allow' permission")
                        time.sleep(1)
                    
                    # Check if data arrived
                    clipboard_data = check_data()
                
                # 3. Fallback to Manual Paste if still no data
                if not clipboard_data:
                    print("  ⚠ JS Paste failed, trying manual input...")
                    
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
        
        # Register all
        self._actions = {
            "tap": action_tap,
            "type": action_type,
            "wait": action_wait,
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
        }
    
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
    
    def run(self, steps: List[Dict], session_id: str = "default",
            initial_data: Optional[Dict] = None) -> StepContext:
        """
        Run a flow
        
        Args:
            steps: List of step configurations
            session_id: Session ID for OTP
            initial_data: Initial data to set in context
        
        Returns:
            StepContext with results
        """
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
            ctx.step_results.append({
                "step": step.name,
                "action": step.action,
                "result": result.value,
                "timestamp": datetime.now().isoformat()
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
    
    def run_file(self, filepath: str, session_id: str = "default",
                 initial_data: Optional[Dict] = None) -> StepContext:
        """Run flow from JSON file"""
        with open(filepath) as f:
            flow = json.load(f)
        
        steps = flow.get("steps", flow) if isinstance(flow, dict) else flow
        data = {**(flow.get("data", {}) if isinstance(flow, dict) else {}), 
                **(initial_data or {})}
        
        return self.run(steps, session_id, data)


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
