---
description: Create automation flow for Android app registration
---

# Create Flow Workflow

Follow these steps to create a new automation flow:

## 1. Understand Requirements
Ask the user:
- What app to automate? (package name)
- What data fields needed? (email, password, username, etc.)
- What's the registration flow? (screens, buttons, inputs)
- Any OTP/2FA verification needed?
- Where to save results? (webhook URL)

## 2. Create Flow JSON
Create a JSON file in `/home/zeroserver/Project/auto_register/flows/`:

```json
{
  "name": "Flow Name",
  "description": "Description",
  "steps": [
    // Data Source (if batch mode needed)
    {
      "name": "Data Source: ",
      "action": "data_source",
      "params": {
        "columns": ["email", "password"],
        "rows": []
      }
    },
    // Launch app
    {
      "name": "Launch: app",
      "action": "launch",
      "params": {"package": "com.example.app"}
    },
    // Steps...
  ]
}
```

## 3. Available Actions

| Action | Use Case | Key Params |
|--------|----------|------------|
| `data_source` | Batch data input | `columns`, `rows` |
| `launch` | Open app | `package` |
| `tap` | Tap button/element | `text`, `resource_id`, `index`, `x`, `y` |
| `type` | Enter text | `text` or `from_data`, `clear` |
| `wait` | Wait for screen | `text`, `timeout` |
| `key` | Press key | `key` (enter/back/home) |
| `scroll` | Scroll screen | `direction`, `distance` |
| `delay` | Fixed wait | `seconds` |
| `otp` | Wait for SMS code | `timeout`, `save_as` |
| `totp` | Generate 2FA code | `from_data`, `save_as` |
| `capture` | Save element text | `text`, `resource_id`, `index`, `save_as` |
| `clipboard` | Copy via browser | `text`, `save_as` |
| `webhook` | Send HTTP request | `url`, `method`, `include_data` |

## 4. Data Flow Pattern

```
capture/clipboard (save_as: "key") → ... → type (from_data: "key")
```

Data Source columns are automatically available:
```
data_source (columns: ["email"]) → ... → type (from_data: "email")
```

## 5. Save Flow

// turbo
```bash
# Save flow to file
cat > /home/zeroserver/Project/auto_register/flows/NEW_FLOW_NAME.json << 'EOF'
{JSON CONTENT HERE}
EOF
```

## 6. Test Flow

Open http://localhost:8888 and:
1. Select the flow from dropdown
2. Add batch data if using Data Source
3. Click Run

## Example: Gmail Registration Flow

```json
{
  "name": "Gmail Registration",
  "steps": [
    {
      "name": "Data Source",
      "action": "data_source",
      "params": {
        "columns": ["first_name", "last_name", "username", "password"],
        "rows": []
      }
    },
    {"name": "Launch Gmail", "action": "launch", "params": {"package": "com.google.android.gm"}},
    {"name": "Tap Create Account", "action": "tap", "params": {"text": "Create account"}},
    {"name": "Tap Personal", "action": "tap", "params": {"text": "For myself"}},
    {"name": "Type First Name", "action": "type", "params": {"from_data": "first_name"}},
    {"name": "Key Tab", "action": "key", "params": {"key": "tab"}},
    {"name": "Type Last Name", "action": "type", "params": {"from_data": "last_name", "clear": false}},
    {"name": "Tap Next", "action": "tap", "params": {"text": "Next"}},
    {"name": "Type Username", "action": "type", "params": {"from_data": "username"}},
    {"name": "Tap Next", "action": "tap", "params": {"text": "Next"}},
    {"name": "Type Password", "action": "type", "params": {"from_data": "password"}},
    {"name": "Key Tab", "action": "key", "params": {"key": "tab"}},
    {"name": "Type Confirm", "action": "type", "params": {"from_data": "password", "clear": false}},
    {"name": "Tap Next", "action": "tap", "params": {"text": "Next"}},
    {"name": "Wait Success", "action": "wait", "params": {"text": "Welcome", "timeout": 30}},
    {"name": "Report", "action": "webhook", "params": {"url": "https://webhook.site/xxx", "include_data": true}}
  ]
}
```
