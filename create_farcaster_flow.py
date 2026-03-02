
import sys
import time
import re
import random
import string
import json
from datetime import datetime

import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tools.recorder import ActionRecorder, RecordedAction
from utils import connect

def run_farcaster_flow():
    recorder = ActionRecorder(execute=True)
    recorder.start_session("register_farcaster")

    print("=== Starting Farcaster Flow Creation ===")
    
    # Ensure fresh start
    print("Clearing app data...")
    recorder.portal._run_adb("shell", "pm", "clear", "com.farcaster.mobile")
    time.sleep(2)

    # 1. Launch Com.Farcaster.Mobile
    package_name = "com.farcaster.mobile"
    print(f"Launching {package_name}...")
    recorder.portal.launch_app(package_name)
    
    # Manually record launch since recorder doesn't auto-record launch
    action = RecordedAction(
        timestamp=datetime.now().isoformat(),
        action_type="launch",
        package_name=package_name,
        note="Launch App"
    )
    recorder.session.add_action(action)
    time.sleep(5)

    # 2. Find "Create account" or similar
    # We poll for the button
    print("Looking for Create/Sign up button...")
    button_texts = ["Create account", "Sign up", "Get started", "Log in", "Sign in"]
    
    # Wait for screen to load
    print("Waiting for Create account text...")
    recorder.portal.wait_for_text("Create account", timeout=10, poll_interval=1)
    
    found_button = False
    
    # Retry loop to find button
    for attempt in range(3):
        elements = recorder.portal.get_elements()
        
        # Try to find button by text
        for btn_text in button_texts:
            for e in elements:
                if e.text and btn_text.lower() in e.text.lower():
                    print(f"Found button: {e.text} (index {e.index})")
                    recorder.record_tap(e.text, by="text") # This executes tap too
                    found_button = True
                    break
            if found_button: break
        
        # Fallback: specific index for Farcaster 'Create Account' (usually 5 or 6)
        if not found_button:
             # Check if element 5 or 6 has text 'Create account'
             cand = [e for e in elements if e.index in [5, 6] and "Create" in (e.text or "")]
             if cand:
                 print(f"Found button via index fallback: {cand[0].text}")
                 recorder.record_tap(cand[0].text, by="text")
                 found_button = True
                 break
        
        if found_button: break
        time.sleep(2)
    
    if not found_button:
        print("Could not find obvious button. Tapping by index 1 (screen centerish fallback?) or dumping.")
        # Sometimes key buttons are index 0 or 1
        # Let's check for ANY button
        buttons = [e for e in elements if e.class_name.endswith("Button") or e.resource_id]
        if buttons:
            print(f"Tapping first button found: {buttons[0].text or buttons[0].class_name}")
            recorder.record_tap(buttons[0].text or str(buttons[0].index), by="auto")
        else:
            print("No buttons found. Dumping screen.")
            recorder.show_screen()
            # Try tapping center?
            # recorder.record_tap("540,1000") # Coordinate tap
    
    time.sleep(3)

    # 3. Email Input
    # Look for EditText or "Email"
    print("Looking for email input...")
    # Assume focus is on email or we need to tap it.
    # We can try typing directly?
    
    email = "ak.barabdul80@gmail.com"
    print(f"Typing email: {email}")
    recorder.record_type(email)
    time.sleep(1)
    
    # Identify "Continue" button
    print("Looking for Continue button...")
    recorder.record_key("enter") # Often submits
    time.sleep(2)
    
    # Check if we advanced. If "Email" is still there, we might need to tap a button.
    elements = recorder.portal.get_elements()
    if any("email" in (e.text or "").lower() for e in elements):
        print("Still on email screen, trying to tap Continue/Next")
        for txt in ["Continue", "Next", "Submit", "Send"]:
             if recorder.portal.tap_text(txt, exact=False):
                 # We tapped it, but recorder didn't record it unless we called record_tap.
                 # To act+record properly:
                 # But since we just did it via portal directly (to check if it exists), we should use record_tap if we are sure.
                 # But tap_text returns bool. If true, it TAPPED.
                 # So we should record it manually or use record_tap which does both.
                 # But record_tap uses "identifier" to find it again.
                 
                 # Let's just use record_tap without checking first, it prints error if not found.
                 recorder.record_tap(txt, by="text")
                 break

    # 4. OTP Handling
    print("Switching to Gmail for OTP...")
    gmail_pkg = "com.google.android.gm"
    
    # Manual context switch record? Flow runner doesn't support "switch app" explicitly inside a flow usually,
    # unless we use another "launch" action.
    recorder.portal.launch_app(gmail_pkg)
    # Record this as launch
    action = RecordedAction(
        timestamp=datetime.now().isoformat(),
        action_type="launch",
        package_name=gmail_pkg,
        note="Switch to Gmail"
    )
    recorder.session.add_action(action)
    
    time.sleep(5)
    
    otp_code = None
    max_retries = 10
    
    # We might need to refresh inbox
    
    for i in range(max_retries):
        print(f"Searching for OTP email... Attempt {i+1}/{max_retries}")
        
        # Pull to refresh?
        recorder.portal.swipe_down()
        time.sleep(2)
        
        elements = recorder.portal.get_elements()
        
        # Regex to find Warpcast or Farcaster in list
        # Usually in Gmail list: Sender, Subject, Snippet
        # We look for "Warpcast" or "Farcaster" and maybe "Verify" or "Code"
        
        candidates = [e for e in elements if e.text and ("warpcast" in e.text.lower() or "farcaster" in e.text.lower())]
        
        if candidates:
            print(f"Found email candidate: {candidates[0].text}")
            recorder.record_tap(candidates[0].text, by="text")
            time.sleep(3)
            
            # Read email content
            content_elements = recorder.portal.get_elements()
            full_text = " ".join([e.text for e in content_elements if e.text])
            
            # Look for 6 digit code? Or specific pattern
            # "verification code is 123456"
            print(f"Email content length: {len(full_text)}")
            
            # Try to find 6 digit number
            # Farcaster/Warpcast OTP
            matches = re.findall(r'\b\d{6}\b', full_text)
            if matches:
                 otp_code = matches[0] # Take first one?
                 print(f"EXTRACTED OTP: {otp_code}")
                 break
            else:
                print("No OTP found in email text. Going back.")
                recorder.record_key("back")
                time.sleep(1)
        
        time.sleep(5)
    
    if not otp_code:
        print("❌ Failed to retrieve OTP. Aborting.")
        # Save whatever we have
        recorder.save_session("failed_session.json")
        return

    # Switch back to Farcaster
    print("Switching back to Farcaster...")
    recorder.portal.launch_app(package_name)
    action = RecordedAction(
        timestamp=datetime.now().isoformat(),
        action_type="launch",
        package_name=package_name,
        note="Switch back"
    )
    recorder.session.add_action(action)
    time.sleep(2)
    
    # Enter OTP
    print(f"Entering OTP: {otp_code}")
    recorder.record_type(otp_code)
    time.sleep(2)
    
    # 5. Username
    # Handle duplicates
    base_user = "akbarabdul80"
    
    # Check if we are on username screen
    # Look for "Username" text
    recorder.portal.wait_for_text("username", timeout=10)
    
    attempt = 0
    while attempt < 5:
        current_username = base_user if attempt == 0 else f"{base_user}{random.randint(10,99)}"
        print(f"Trying username: {current_username}")
        
        recorder.record_type(current_username)
        time.sleep(1)
        recorder.record_key("enter") # Submit
        time.sleep(3)
        
        # Check for error or success
        # Success = moved to next screen (Photo?) or "Skip" button appears
        elements = recorder.portal.get_elements()
        success = any("skip" in (e.text or "").lower() for e in elements)
        
        if success:
            print("Username Accepted!")
            break
            
        # Check for error text
        error = any(kw in " ".join([e.text or "" for e in elements]).lower() for kw in ["taken", "exists", "unavailable"])
        if error:
            print("Username taken. Retrying...")
            # Need to clear text?
            # Or just type new one? Type usually appends.
            # We should clear.
            # recorder portal clear_text?
            recorder.portal.clear_text() 
            # But we need to record the clear action? Recorder doesn't have record_clear.
            # We can simulate backspaces.
            for _ in range(len(current_username) + 2):
                 recorder.record_key("backspace")
        else:
             # Maybe it worked?
             print("Unknown state. Assuming success or proceeding.")
             break
        
        attempt += 1

    # 6. Skip Photo
    print("Looking for Skip button...")
    # Wait for "Skip"
    recorder.portal.wait_for_text("Skip", timeout=5)
    recorder.record_tap("Skip", by="text")
    
    # Save Flow
    output_flow = "flows/register_farcaster.json"
    recorder.generate_flow(output_flow)
    print(f"✅ Flow saved to {output_flow}")

if __name__ == "__main__":
    run_farcaster_flow()
