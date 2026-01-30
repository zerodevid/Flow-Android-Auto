#!/usr/bin/env python3
"""
Example: Auto Register Automation Script
Demonstrasi penggunaan utils untuk automation
"""

import sys
import time
sys.path.insert(0, '/home/zeroserver/Project/auto_register')

from utils import connect, get_device


def example_basic_usage():
    """Contoh penggunaan dasar"""
    
    # Connect ke Droidrun Portal
    portal = connect()
    print(f"✓ Connected to Droidrun Portal v{portal.get_version()}")
    
    # Cek phone state
    state = portal.get_phone_state()
    print(f"✓ Current app: {state['packageName']}")
    print(f"  Activity: {state['activityName']}")
    print(f"  Keyboard visible: {state['keyboardVisible']}")
    
    # Dump semua elements di layar
    portal.dump_screen()


def example_find_and_tap():
    """Contoh find element dan tap"""
    
    portal = connect()
    
    # Method 1: Tap by text
    if portal.tap_text("Continue"):
        print("✓ Tapped 'Continue' button")
    else:
        print("✗ 'Continue' button not found")
    
    # Method 2: Tap by resourceId
    if portal.tap_resource_id("submit-button"):
        print("✓ Tapped submit button")
    
    # Method 3: Tap by index (overlay number)
    if portal.tap_index(24):
        print("✓ Tapped element #24")
    
    # Method 4: Find element first, then use it
    elem = portal.find_by_text("Sign In")
    if elem:
        print(f"Found element at {elem.center}")
        portal.tap_element(elem)


def example_input_text():
    """Contoh input text"""
    
    portal = connect()
    
    # Tap pada input field dulu (by text hint atau resourceId)
    portal.tap_text("Email")
    time.sleep(0.5)
    
    # Wait keyboard muncul
    if portal.wait_for_keyboard(visible=True, timeout=3):
        print("✓ Keyboard visible")
    
    # Type text (clear dulu by default)
    portal.type_text("user@example.com")
    print("✓ Typed email")
    
    # Press Enter untuk next field
    portal.press_enter()
    time.sleep(0.3)
    
    # Type password
    portal.type_text("password123")
    print("✓ Typed password")


def example_scroll_and_wait():
    """Contoh scroll dan wait"""
    
    portal = connect()
    
    # Scroll sampai ketemu element
    elem = portal.scroll_to_text("Terms and Conditions", max_swipes=5)
    if elem:
        print("✓ Found 'Terms and Conditions'")
        portal.tap_element(elem)
    
    # Wait for activity change
    if portal.wait_for_activity("MainActivity", timeout=10):
        print("✓ Entered MainActivity")
    
    # Wait for specific text to appear
    elem = portal.wait_for_text("Welcome", timeout=5)
    if elem:
        print("✓ Welcome screen loaded")


def example_full_flow():
    """Contoh flow lengkap: buka app, register, dsb"""
    
    portal = connect()
    device = get_device()
    
    # Step 1: Launch app
    print("\n[1] Launching app...")
    portal.launch_app("com.example.myapp")
    time.sleep(2)
    
    # Step 2: Wait for app loaded
    print("[2] Waiting for app...")
    portal.wait_for_text("Sign Up", timeout=10)
    
    # Step 3: Tap Sign Up
    print("[3] Tapping Sign Up...")
    portal.tap_text("Sign Up")
    time.sleep(1)
    
    # Step 4: Fill form
    print("[4] Filling registration form...")
    
    # Email field
    portal.tap_text("Email", exact=False)
    portal.wait_for_keyboard()
    portal.type_text("test@example.com")
    portal.press_enter()
    time.sleep(0.3)
    
    # Password field
    portal.type_text("SecurePassword123!")
    portal.press_enter()
    time.sleep(0.3)
    
    # Step 5: Submit
    print("[5] Submitting...")
    portal.tap_text("Create Account")
    
    # Step 6: Wait for success
    print("[6] Waiting for confirmation...")
    if portal.wait_for_text("Success", timeout=10):
        print("\n✓ Registration complete!")
    else:
        print("\n✗ Registration might have failed")
    
    # Take screenshot for verification
    device.screenshot("/tmp/registration_result.png")
    print("Screenshot saved to /tmp/registration_result.png")


def main():
    """Run example"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Automation Examples")
    parser.add_argument("example", nargs="?", default="basic",
                       choices=["basic", "tap", "input", "scroll", "flow"],
                       help="Which example to run")
    
    args = parser.parse_args()
    
    examples = {
        "basic": example_basic_usage,
        "tap": example_find_and_tap,
        "input": example_input_text,
        "scroll": example_scroll_and_wait,
        "flow": example_full_flow,
    }
    
    print(f"\n{'='*50}")
    print(f"Running example: {args.example}")
    print(f"{'='*50}\n")
    
    try:
        examples[args.example]()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
