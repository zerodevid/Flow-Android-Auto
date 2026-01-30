---
description: How to create and manage automation flows for Android app registration
---

# Flow Editor Knowledge

This project is an **Android automation framework** using a visual flow editor. Flows are step-based automations that interact with Android devices via DroidrunPortal.

## Architecture

```
web/app.py           - Flask API server (port 8888)
web/static/          - Frontend (HTML/JS/CSS)
core/flow_runner.py  - Execution engine
flows/               - Saved flow JSON files
```

## Node Types

All available nodes for building flows:

| Node | Action | Key Params | Description |
|------|--------|------------|-------------|
| 📊 Data Source | `data_source` | `columns`, `rows` | Batch data for looping. Put at start of flow. |
| 👆 Tap | `tap` | `text`, `resource_id`, `index`, `x`, `y`, `timeout` | Tap element or coordinates |
| ⌨️ Type | `type` | `text`, `from_data`, `clear` | Type text. Use `from_data` for dynamic data |
| ⏳ Wait | `wait` | `text`, `timeout` | Wait for element to appear |
| 🔑 Key | `key` | `key` (enter/back/home/backspace) | Press hardware key |
| 📜 Scroll | `scroll` | `direction` (up/down), `distance` | Scroll screen |
| ⏱️ Delay | `delay` | `seconds` | Wait fixed time |
| 🔀 Condition | `condition` | `check_text` | Branch flow (yes/no outputs) |
| 📬 OTP | `otp` | `timeout`, `save_as` | Wait for SMS OTP from server |
| 🔐 TOTP | `totp` | `secret`, `from_data`, `save_as` | Generate 2FA code |
| 📝 Capture | `capture` | `resource_id`, `text`, `index`, `save_as` | Capture element text to variable |
| 📋 Clipboard | `clipboard` | `index`, `text`, `resource_id`, `save_as` | Copy via browser paste page |
| 🚀 Launch | `launch` | `package` | Launch app by package name |
| 🌐 Webhook | `webhook` | `url`, `method`, `include_data` | Send HTTP request with captured data |

## Data Flow

### Using `from_data`
Any node can read captured data using the `from_data` parameter:
- `capture` node saves to `save_as` key
- `type` node reads from `from_data` key
- Data persists throughout flow execution

Example:
```
Capture (save_as: "secret")  →  TOTP (from_data: "secret")  →  Type (from_data: "totp")
```

### Data Source Node (Batch Mode)
When a flow contains a Data Source node:
1. Columns define the data fields (e.g., `email`, `password`)
2. Rows contain data values
3. Flow loops automatically for each row
4. All column values are available via `from_data`

## Flow JSON Structure

Flows are saved as JSON in `/home/zeroserver/Project/auto_register/flows/`:

```json
{
  "name": "My Registration Flow",
  "description": "Created with Flow Editor",
  "steps": [
    {
      "name": "Data Source: ",
      "action": "data_source",
      "params": {
        "columns": ["email", "password"],
        "rows": [
          {"email": "user1@example.com", "password": "pass123"},
          {"email": "user2@example.com", "password": "pass456"}
        ]
      }
    },
    {
      "name": "Launch: com.app",
      "action": "launch",
      "params": {"package": "com.example.app"}
    },
    {
      "name": "Tap: Email",
      "action": "tap",
      "params": {"text": "Email", "timeout": 10}
    },
    {
      "name": "Type: email",
      "action": "type",
      "params": {"from_data": "email", "clear": true}
    },
    {
      "name": "Tap: Password",
      "action": "tap",
      "params": {"text": "Password"}
    },
    {
      "name": "Type: password",
      "action": "type",
      "params": {"from_data": "password", "clear": true}
    },
    {
      "name": "Tap: Sign Up",
      "action": "tap",
      "params": {"text": "Sign Up"}
    },
    {
      "name": "Wait: OTP",
      "action": "otp",
      "params": {"timeout": 120, "save_as": "otp"}
    },
    {
      "name": "Type: otp",
      "action": "type",
      "params": {"from_data": "otp"}
    },
    {
      "name": "Webhook: report",
      "action": "webhook",
      "params": {
        "url": "https://example.com/webhook",
        "method": "POST",
        "include_data": true
      }
    }
  ],
  "_editor": {
    "nodes": [...],
    "connections": [...]
  }
}
```

## Creating Flows Programmatically

To create a flow via API:

```bash
# Create/Update flow
curl -X PUT http://localhost:8888/api/flows/my_flow \
  -H "Content-Type: application/json" \
  -d @flow.json

# Run flow
curl -X POST http://localhost:8888/api/flows/my_flow/run

# List flows
curl http://localhost:8888/api/flows

# Get flow
curl http://localhost:8888/api/flows/my_flow

# Delete flow
curl -X DELETE http://localhost:8888/api/flows/my_flow
```

## Common Patterns

### Registration with Email/Password
```
Data Source → Launch App → Tap "Sign Up" → Tap "Email" → Type (from_data: email) → 
Tap "Password" → Type (from_data: password) → Tap "Submit" → Wait "Success"
```

### OTP Verification
```
... → Wait "Enter OTP" → OTP (save_as: otp, timeout: 120) → Type (from_data: otp) → Tap "Verify"
```

### TOTP 2FA Setup
```
... → Clipboard (text: "Copy", save_as: totp_secret) → 
TOTP (from_data: totp_secret, save_as: totp_code) → 
Type (from_data: totp_code) → Tap "Verify"
```

### Save Results to Webhook
```
... → Capture (resource_id: "account_id", save_as: account) → 
Webhook (url: "https://...", include_data: true)
```

## Web Server

The flow editor runs on port 8888:
- Main editor: http://localhost:8888
- OTP receiver: http://localhost:5000

Start server:
```bash
python3 web/app.py -p 8888
```

## Tips

1. **Use `timeout`** on tap/wait nodes to handle slow screens
2. **Use `wait_for: true`** (default) to wait for element before tap
3. **Data Source must be first** in the flow (after Start)
4. **Webhook at end** to save results externally
5. **Check element index** in Device Preview for reliable taps
