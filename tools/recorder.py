#!/usr/bin/env python3
"""
Android Action Recorder
Observes user actions and generates automation scripts
"""

import sys
import time
import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils import connect, DroidrunPortal, Element


@dataclass
class RecordedAction:
    """Represents a recorded user action"""
    timestamp: str
    action_type: str  # "tap", "type", "scroll", "key", "wait"
    
    # For tap actions
    element_text: Optional[str] = None
    element_resource_id: Optional[str] = None
    element_class: Optional[str] = None
    element_index: Optional[int] = None
    element_bounds: Optional[tuple] = None
    
    # For type actions
    text_input: Optional[str] = None
    
    # For key actions
    key_code: Optional[int] = None
    key_name: Optional[str] = None
    
    # For wait actions  
    wait_for_text: Optional[str] = None
    wait_for_activity: Optional[str] = None
    
    # Screen context
    package_name: Optional[str] = None
    activity_name: Optional[str] = None
    
    # Notes
    note: Optional[str] = None


@dataclass
class RecordingSession:
    """A recording session with multiple actions"""
    name: str
    created_at: str
    actions: List[RecordedAction] = field(default_factory=list)
    
    def add_action(self, action: RecordedAction):
        self.actions.append(action)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created_at": self.created_at,
            "actions": [asdict(a) for a in self.actions]
        }
    
    def save(self, filepath: str):
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        print(f"✓ Session saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'RecordingSession':
        with open(filepath) as f:
            data = json.load(f)
        session = cls(name=data["name"], created_at=data["created_at"])
        for action_data in data["actions"]:
            session.actions.append(RecordedAction(**action_data))
        return session


class ActionRecorder:
    """
    Records user actions by observing screen changes
    Supports live execution mode - execute actions while recording
    """
    
    def __init__(self, portal: Optional[DroidrunPortal] = None, execute: bool = True):
        self.portal = portal or connect()
        self.session: Optional[RecordingSession] = None
        self.last_state: Optional[Dict] = None
        self.last_elements: List[Element] = []
        self.running = False
        self.execute_mode = execute  # If True, execute actions on device while recording
    
    def _get_state_hash(self, state: Dict) -> str:
        """Get hash of current state for change detection"""
        key_parts = [
            state.get("packageName", ""),
            state.get("activityName", ""),
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    def _get_elements_hash(self, elements: List[Element]) -> str:
        """Get hash of elements for change detection"""
        texts = sorted([e.text for e in self._flatten(elements) if e.text])
        return hashlib.md5("|".join(texts[:20]).encode()).hexdigest()
    
    def _flatten(self, elements: List[Element]) -> List[Element]:
        """Flatten element tree"""
        result = []
        for elem in elements:
            result.append(elem)
            result.extend(self._flatten(elem.children))
        return result
    
    def start_session(self, name: str = "recording"):
        """Start a new recording session"""
        self.session = RecordingSession(
            name=name,
            created_at=datetime.now().isoformat()
        )
        print(f"\n{'='*60}")
        print(f"🔴 Recording started: {name}")
        print(f"{'='*60}\n")
    
    def get_current_screen_info(self) -> Dict:
        """Get current screen information"""
        state = self.portal.get_phone_state()
        elements = self.portal.get_elements()
        all_elements = self._flatten(elements)
        
        # Get clickable elements
        clickable = [e for e in all_elements 
                    if "Button" in e.class_name or "Clickable" in e.class_name 
                    or e.resource_id]
        
        return {
            "package": state.get("packageName", ""),
            "activity": state.get("activityName", ""),
            "keyboard_visible": state.get("keyboardVisible", False),
            "total_elements": len(all_elements),
            "clickable_elements": len(clickable),
            "elements": all_elements
        }
    
    def show_screen(self):
        """Display current screen elements"""
        info = self.get_current_screen_info()
        
        print(f"\n{'─'*60}")
        print(f"📱 Package: {info['package']}")
        print(f"📋 Activity: {info['activity']}")
        print(f"⌨️  Keyboard: {'visible' if info['keyboard_visible'] else 'hidden'}")
        print(f"📊 Elements: {info['total_elements']} total")
        print(f"{'─'*60}")
        
        # Show important elements
        print("\n🎯 Key Elements:")
        for elem in info['elements']:
            if elem.text and len(elem.text) < 50:
                icon = "🔘" if "Button" in elem.class_name else "📝" if "Edit" in elem.class_name else "📄"
                rid = f" [{elem.resource_id}]" if elem.resource_id else ""
                print(f"  {icon} [{elem.index:2d}] {elem.text}{rid}")
        print()
    
    def record_tap(self, identifier: str, by: str = "auto"):
        """
        Record a tap action
        
        Args:
            identifier: Text, resourceId, or index to identify element
            by: "text", "resource_id", "index", or "auto" (auto-detect)
        """
        if not self.session:
            print("⚠️  No recording session active. Call start_session() first.")
            return
        
        state = self.portal.get_phone_state()
        elements = self.portal.get_elements()
        all_elements = self._flatten(elements)
        
        # Find element
        elem = None
        
        if by == "auto":
            # Try index first
            if identifier.isdigit():
                idx = int(identifier)
                for e in all_elements:
                    if e.index == idx:
                        elem = e
                        by = "index"
                        break
            
            # Try text
            if not elem:
                for e in all_elements:
                    if identifier.lower() in e.text.lower():
                        elem = e
                        by = "text"
                        break
            
            # Try resource_id
            if not elem:
                for e in all_elements:
                    if identifier in e.resource_id:
                        elem = e
                        by = "resource_id"
                        break
        
        elif by == "index":
            idx = int(identifier)
            for e in all_elements:
                if e.index == idx:
                    elem = e
                    break
        
        elif by == "text":
            for e in all_elements:
                if identifier.lower() in e.text.lower():
                    elem = e
                    break
        
        elif by == "resource_id":
            for e in all_elements:
                if identifier in e.resource_id:
                    elem = e
                    break
        
        if not elem:
            print(f"⚠️  Element not found: {identifier}")
            return
        
        # Create action
        action = RecordedAction(
            timestamp=datetime.now().isoformat(),
            action_type="tap",
            element_text=elem.text if elem.text else None,
            element_resource_id=elem.resource_id if elem.resource_id else None,
            element_class=elem.class_name,
            element_index=elem.index,
            element_bounds=elem.bounds,
            package_name=state.get("packageName"),
            activity_name=state.get("activityName"),
        )
        
        self.session.add_action(action)
        
        print(f"✓ Recorded TAP: [{elem.index}] \"{elem.text}\" (by {by})")
        print(f"  Class: {elem.class_name}")
        print(f"  ResourceId: {elem.resource_id or '(none)'}")
        print(f"  Center: {elem.center}")
        
        # Execute on device if enabled
        if self.execute_mode:
            self.portal.tap_element(elem)
            print(f"  ▶ Executed TAP at {elem.center}")
    
    def record_type(self, text: str):
        """Record a text input action"""
        if not self.session:
            print("⚠️  No recording session active.")
            return
        
        state = self.portal.get_phone_state()
        
        action = RecordedAction(
            timestamp=datetime.now().isoformat(),
            action_type="type",
            text_input=text,
            package_name=state.get("packageName"),
            activity_name=state.get("activityName"),
        )
        
        self.session.add_action(action)
        print(f"✓ Recorded TYPE: \"{text}\"")
        
        # Execute on device if enabled
        if self.execute_mode:
            self.portal.type_text(text)
            print(f"  ▶ Executed TYPE")
    
    def record_key(self, key: str):
        """Record a key press action"""
        if not self.session:
            print("⚠️  No recording session active.")
            return
        
        key_codes = {
            "enter": 66, "back": 4, "home": 3, "recent": 187,
            "backspace": 67, "tab": 61, "escape": 111,
            "up": 19, "down": 20, "left": 21, "right": 22,
        }
        
        key_code = key_codes.get(key.lower(), int(key) if key.isdigit() else 0)
        
        action = RecordedAction(
            timestamp=datetime.now().isoformat(),
            action_type="key",
            key_code=key_code,
            key_name=key,
        )
        
        self.session.add_action(action)
        print(f"✓ Recorded KEY: {key} (code: {key_code})")
        
        # Execute on device if enabled
        if self.execute_mode:
            self.portal.press_key(key_code)
            print(f"  ▶ Executed KEY")
    
    def record_wait(self, wait_for: str, wait_type: str = "text"):
        """Record a wait action"""
        if not self.session:
            print("⚠️  No recording session active.")
            return
        
        action = RecordedAction(
            timestamp=datetime.now().isoformat(),
            action_type="wait",
            wait_for_text=wait_for if wait_type == "text" else None,
            wait_for_activity=wait_for if wait_type == "activity" else None,
        )
        
        self.session.add_action(action)
        print(f"✓ Recorded WAIT: {wait_type} = \"{wait_for}\"")
    
    def record_scroll(self, direction: str = "up"):
        """Record a scroll action"""
        if not self.session:
            print("⚠️  No recording session active.")
            return
        
        action = RecordedAction(
            timestamp=datetime.now().isoformat(),
            action_type="scroll",
            note=f"scroll_{direction}",
        )
        
        self.session.add_action(action)
        print(f"✓ Recorded SCROLL: {direction}")
        
        # Execute on device if enabled
        if self.execute_mode:
            if direction == "up":
                self.portal.swipe_up()
            else:
                self.portal.swipe_down()
            print(f"  ▶ Executed SCROLL {direction}")
    
    def show_recording(self):
        """Show all recorded actions"""
        if not self.session:
            print("⚠️  No recording session active.")
            return
        
        print(f"\n{'='*60}")
        print(f"📼 Recording: {self.session.name}")
        print(f"   Created: {self.session.created_at}")
        print(f"   Actions: {len(self.session.actions)}")
        print(f"{'='*60}\n")
        
        for i, action in enumerate(self.session.actions, 1):
            if action.action_type == "tap":
                print(f"{i:2d}. TAP \"{action.element_text}\"")
                print(f"    → resource_id: {action.element_resource_id or '(none)'}")
            elif action.action_type == "type":
                print(f"{i:2d}. TYPE \"{action.text_input}\"")
            elif action.action_type == "key":
                print(f"{i:2d}. KEY {action.key_name}")
            elif action.action_type == "wait":
                print(f"{i:2d}. WAIT for text \"{action.wait_for_text}\"")
            elif action.action_type == "scroll":
                print(f"{i:2d}. SCROLL {action.note}")
        print()
    
    def generate_script(self, output_path: Optional[str] = None) -> str:
        """Generate Python automation script from recording"""
        if not self.session:
            print("⚠️  No recording session active.")
            return ""
        
        lines = [
            '#!/usr/bin/env python3',
            '"""',
            f'Auto-generated automation script: {self.session.name}',
            f'Generated at: {datetime.now().isoformat()}',
            '"""',
            '',
            'import sys',
            'import time',
            "sys.path.insert(0, '/home/zeroserver/Project/auto_register')",
            '',
            'from utils import connect',
            '',
            '',
            f'def run_{self.session.name.replace("-", "_").replace(" ", "_")}():',
            '    """Execute the recorded automation"""',
            '    portal = connect()',
            '    print("Starting automation...")',
            '    ',
        ]
        
        for i, action in enumerate(self.session.actions, 1):
            lines.append(f'    # Step {i}')
            
            if action.action_type == "tap":
                # Prefer resource_id, then text
                if action.element_resource_id:
                    lines.append(f'    portal.tap_resource_id("{action.element_resource_id}")')
                    lines.append(f'    print("Tapped: {action.element_text}")')
                elif action.element_text:
                    # Escape quotes in text
                    safe_text = action.element_text.replace('"', '\\"')
                    lines.append(f'    portal.tap_text("{safe_text}")')
                    lines.append(f'    print("Tapped: {safe_text}")')
                else:
                    lines.append(f'    portal.tap_index({action.element_index})')
                    lines.append(f'    print("Tapped index: {action.element_index}")')
                lines.append('    time.sleep(0.5)')
            
            elif action.action_type == "type":
                safe_text = action.text_input.replace('"', '\\"')
                lines.append(f'    portal.type_text("{safe_text}")')
                lines.append(f'    print("Typed: {safe_text}")')
                lines.append('    time.sleep(0.3)')
            
            elif action.action_type == "key":
                if action.key_name == "enter":
                    lines.append('    portal.press_enter()')
                elif action.key_name == "back":
                    lines.append('    portal.press_back()')
                else:
                    lines.append(f'    portal.press_key({action.key_code})')
                lines.append(f'    print("Pressed: {action.key_name}")')
                lines.append('    time.sleep(0.3)')
            
            elif action.action_type == "wait":
                if action.wait_for_text:
                    safe_text = action.wait_for_text.replace('"', '\\"')
                    lines.append(f'    portal.wait_for_text("{safe_text}", timeout=10)')
                    lines.append(f'    print("Found: {safe_text}")')
                elif action.wait_for_activity:
                    lines.append(f'    portal.wait_for_activity("{action.wait_for_activity}", timeout=10)')
            
            elif action.action_type == "scroll":
                if "up" in action.note:
                    lines.append('    portal.swipe_up()')
                else:
                    lines.append('    portal.swipe_down()')
                lines.append('    time.sleep(0.5)')
            
            lines.append('    ')
        
        lines.extend([
            '    print("Automation complete!")',
            '',
            '',
            'if __name__ == "__main__":',
            f'    run_{self.session.name.replace("-", "_").replace(" ", "_")}()',
        ])
        
        script = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(script)
            print(f"✓ Script saved to {output_path}")
        
        return script
    
    def generate_flow(self, output_path: Optional[str] = None) -> dict:
        """Generate Flow Runner JSON from recording"""
        if not self.session:
            print("⚠️  No recording session active.")
            return {}
        
        steps = []
        
        for i, action in enumerate(self.session.actions, 1):
            step = {"name": f"Step {i}"}
            
            if action.action_type == "tap":
                step["action"] = "tap"
                # Check for coordinate tap
                if action.note and action.note.startswith("tap_xy:"):
                    coords = action.note.split(":")[1].split(",")
                    step["params"] = {"x": int(coords[0]), "y": int(coords[1])}
                    step["name"] = f"Tap at ({coords[0]}, {coords[1]})"
                elif action.element_resource_id:
                    step["params"] = {"resource_id": action.element_resource_id}
                    step["name"] = f"Tap {action.element_text or action.element_resource_id}"
                elif action.element_text:
                    step["params"] = {"text": action.element_text}
                    step["name"] = f"Tap {action.element_text}"
                else:
                    step["params"] = {"index": action.element_index}
                    step["name"] = f"Tap index {action.element_index}"
            
            elif action.action_type == "type":
                step["action"] = "type"
                step["params"] = {"text": action.text_input}
                step["name"] = f"Type '{action.text_input[:20]}{'...' if len(action.text_input) > 20 else ''}'"
            
            elif action.action_type == "key":
                step["action"] = "key"
                step["params"] = {"key": action.key_name}
                step["name"] = f"Press {action.key_name}"
            
            elif action.action_type == "wait":
                step["action"] = "wait"
                if action.wait_for_text:
                    step["params"] = {"text": action.wait_for_text, "timeout": 10}
                    step["name"] = f"Wait for '{action.wait_for_text}'"
            
            elif action.action_type == "scroll":
                step["action"] = "scroll"
                direction = "up" if "up" in action.note else "down"
                step["params"] = {"direction": direction}
                step["name"] = f"Scroll {direction}"
            
            steps.append(step)
        
        flow = {
            "name": self.session.name,
            "description": f"Auto-generated from recording at {datetime.now().isoformat()}",
            "data": {},
            "steps": steps
        }
        
        if output_path:
            with open(output_path, 'w') as f:
                json.dump(flow, f, indent=2)
            print(f"✓ Flow saved to {output_path}")
        
        return flow
    
    def save_session(self, filepath: str):
        """Save recording session to JSON"""
        if self.session:
            self.session.save(filepath)
    
    def load_session(self, filepath: str):
        """Load recording session from JSON"""
        self.session = RecordingSession.load(filepath)
        print(f"✓ Loaded session: {self.session.name} ({len(self.session.actions)} actions)")


def interactive_recorder():
    """Interactive recording mode"""
    recorder = ActionRecorder(execute=True)  # Execute actions by default
    
    print("\n" + "="*60)
    print("🎬 Android Action Recorder (LIVE MODE)")
    print("="*60)
    print("""
Commands:
  start <name>     - Start new recording session
  show             - Show current screen elements
  tap <id>         - Record & EXECUTE tap on element (text, index, or x,y)
  type <text>      - Record & EXECUTE text input
  key <key>        - Record & EXECUTE key press (enter, backspace, etc)
  wait <text>      - Record wait for text to appear
  scroll <dir>     - Record & EXECUTE scroll (up/down)
  
  # Physical buttons (shortcut):
  back             - Press Back button
  home             - Press Home button  
  recent           - Press Recent Apps button
  
  exec on/off      - Toggle live execution mode
  list             - Show recorded actions
  gen              - Generate Python script
  flow <file>      - Generate Flow JSON for flow_runner
  save <file>      - Save session to JSON
  load <file>      - Load session from JSON
  q                - Quit
""")
    
    while True:
        try:
            cmd = input("recorder> ").strip()
            
            if not cmd:
                continue
            
            parts = cmd.split(maxsplit=1)
            command = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            
            if command == "q" or command == "quit":
                print("Bye!")
                break
            
            elif command == "start":
                recorder.start_session(arg or "recording")
            
            elif command == "show":
                recorder.show_screen()
            
            elif command == "tap":
                if not arg:
                    print("Usage: tap <text|resourceId|index|x,y>")
                elif "," in arg:
                    # Tap by coordinates
                    try:
                        x, y = map(int, arg.split(","))
                        if recorder.session:
                            from datetime import datetime
                            action = RecordedAction(
                                timestamp=datetime.now().isoformat(),
                                action_type="tap",
                                element_bounds=(x, y, x, y),
                                note=f"tap_xy:{x},{y}"
                            )
                            recorder.session.add_action(action)
                            print(f"✓ Recorded TAP at ({x}, {y})")
                            if recorder.execute_mode:
                                recorder.portal.tap(x, y)
                                print(f"  ▶ Executed TAP")
                        else:
                            recorder.portal.tap(x, y)
                            print(f"✓ Tapped at ({x}, {y})")
                    except ValueError:
                        recorder.record_tap(arg)
                else:
                    recorder.record_tap(arg)
            
            elif command == "type":
                if not arg:
                    print("Usage: type <text>")
                else:
                    recorder.record_type(arg)
            
            elif command == "key":
                if not arg:
                    print("Usage: key <enter|back|home|keycode>")
                else:
                    recorder.record_key(arg)
            
            elif command == "wait":
                if not arg:
                    print("Usage: wait <text>")
                else:
                    recorder.record_wait(arg)
            
            elif command == "scroll":
                recorder.record_scroll(arg or "up")
            
            # Physical button shortcuts
            elif command == "back":
                recorder.record_key("back")
            
            elif command == "home":
                recorder.record_key("home")
            
            elif command == "recent":
                # Recent apps = KEYCODE_APP_SWITCH = 187
                if recorder.session:
                    from datetime import datetime
                    action = RecordedAction(
                        timestamp=datetime.now().isoformat(),
                        action_type="key",
                        key_code=187,
                        key_name="recent",
                    )
                    recorder.session.add_action(action)
                    print("✓ Recorded KEY: recent (code: 187)")
                    if recorder.execute_mode:
                        recorder.portal._run_adb("shell", "input", "keyevent", "187")
                        print("  ▶ Executed KEY")
                else:
                    recorder.portal._run_adb("shell", "input", "keyevent", "187")
                    print("✓ Pressed Recent Apps")
            
            elif command == "exec":
                if arg.lower() == "on":
                    recorder.execute_mode = True
                    print("✓ Live execution: ON")
                elif arg.lower() == "off":
                    recorder.execute_mode = False
                    print("✓ Live execution: OFF")
                else:
                    status = "ON" if recorder.execute_mode else "OFF"
                    print(f"Live execution is currently: {status}")
                    print("Usage: exec on/off")
            
            elif command == "list":
                recorder.show_recording()
            
            elif command == "gen":
                script = recorder.generate_script()
                if script:
                    print("\n" + "─"*60)
                    print(script)
                    print("─"*60 + "\n")
            
            elif command == "flow":
                if not arg:
                    # Just print flow JSON
                    flow = recorder.generate_flow()
                    if flow:
                        print("\n" + "─"*60)
                        print(json.dumps(flow, indent=2))
                        print("─"*60 + "\n")
                else:
                    # Save to file
                    recorder.generate_flow(arg)
            
            elif command == "save":
                if not arg:
                    print("Usage: save <filepath.json>")
                else:
                    recorder.save_session(arg)
            
            elif command == "load":
                if not arg:
                    print("Usage: load <filepath.json>")
                else:
                    recorder.load_session(arg)
            
            else:
                print(f"Unknown command: {command}")
        
        except KeyboardInterrupt:
            print("\nUse 'q' to quit")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    interactive_recorder()
