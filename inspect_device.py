
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils import connect

portal = connect()
print("Connected to device")

# Get list of install packages that match "Base" or "Gmail"
# capturing stdout/stderr might be tricky with portal, so let's just grep
# assuming portal has a method to run shell commands

# Actually, let's just get the current screen elements. Maybe the user is on the home screen.
elements = portal.get_elements()
for e in elements:
    if e.text:
        print(f"Element: {e.text} | ResourceID: {e.resource_id} | Class: {e.class_name}")

# Also try to list packages
print("\nSearching for packages...")
# We can use adb shell pm list packages
output = portal._run_adb("shell", "pm", "list", "packages", "-f")
for line in output.splitlines():
    if "base" in line.lower() or "gmail" in line.lower():
        print(line)
