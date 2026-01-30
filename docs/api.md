# API Reference

REST API endpoints untuk Flow Editor server.

Base URL: `http://localhost:8888`

---

## Flows API

### List All Flows

```http
GET /api/flows
```

**Response:**
```json
[
  {
    "id": "my_flow",
    "name": "My Flow",
    "description": "Flow description",
    "updated_at": "2026-01-30T12:00:00"
  }
]
```

### Get Flow

```http
GET /api/flows/<flow_id>
```

**Response:**
```json
{
  "id": "my_flow",
  "name": "My Flow",
  "steps": [...],
  "_editor": {...}
}
```

### Save Flow

```http
PUT /api/flows/<flow_id>
Content-Type: application/json

{
  "name": "My Flow",
  "steps": [...],
  "_editor": {...}
}
```

**Response:**
```json
{
  "status": "saved",
  "id": "my_flow"
}
```

### Delete Flow

```http
DELETE /api/flows/<flow_id>
```

**Response:**
```json
{
  "status": "deleted"
}
```

### Run Flow

```http
POST /api/flows/<flow_id>/run
Content-Type: application/json

{
  "session_id": "optional_session_name"
}
```

**Response:** Server-Sent Events (NDJSON stream)

```json
{"type": "step_start", "index": 0, "step": "Launch App"}
{"type": "step_end", "index": 0, "step": "Launch App", "result": "success"}
{"type": "batch_row_start", "row_index": 0, "total_rows": 3, "row_data": {...}}
{"type": "batch_row_end", "row_index": 0, "success": true}
{"type": "batch_completed", "total_rows": 3, "successful_rows": 3}
```

### Stop Flow

```http
POST /api/flows/<flow_id>/stop
```

**Response:**
```json
{
  "status": "stopping"
}
```

---

## Device API

### Get Elements

```http
GET /api/device/elements
```

**Response:**
```json
{
  "package": "com.example.app",
  "elements": [
    {
      "index": 1,
      "text": "Login",
      "resource_id": "com.example:id/btn_login",
      "class": "android.widget.Button",
      "bounds": "[100,200][300,250]",
      "clickable": true
    }
  ]
}
```

### Get Screenshot

```http
GET /api/device/screenshot
```

**Response:** JPEG image

### Tap

```http
POST /api/device/tap
Content-Type: application/json

// By text
{"text": "Login"}

// By resource_id
{"resource_id": "com.example:id/btn"}

// By index
{"index": 5}

// By coordinates
{"x": 540, "y": 1200}
```

**Response:**
```json
{"status": "ok"}
```

### Type Text

```http
POST /api/device/type
Content-Type: application/json

{
  "text": "hello@email.com",
  "clear": true
}
```

**Response:**
```json
{"status": "ok"}
```

### Press Key

```http
POST /api/device/key
Content-Type: application/json

{
  "key": "enter"
}
```

Available keys: `enter`, `back`, `home`, `backspace`, `tab`

### Scroll

```http
POST /api/device/scroll
Content-Type: application/json

{
  "direction": "down",
  "distance": 500
}
```

---

## OTP Server API

Base URL: `http://localhost:5000`

### Receive OTP

```http
POST /otp
Content-Type: application/json

{
  "code": "123456",
  "phone": "+62812xxx"
}
```

### Get Clipboard (Internal)

```http
GET /clipboard?data=<base64_encoded>
```

Used by browser bridge for clipboard capture.

### Paste Page

```http
GET /paste
```

Returns HTML page for clipboard capture.

---

## Stream Event Types

Events from `/api/flows/<id>/run`:

| Type | Description |
|------|-------------|
| `step_start` | Step mulai execute |
| `step_end` | Step selesai (success/failed) |
| `batch_row_start` | Batch row mulai |
| `batch_row_end` | Batch row selesai |
| `batch_completed` | Semua batch selesai |
| `batch_stopped` | Batch di-stop user |
| `error` | Error occurred |

---

## Usage Examples

### cURL

```bash
# List flows
curl http://localhost:8888/api/flows

# Run flow
curl -X POST http://localhost:8888/api/flows/my_flow/run

# Tap by text
curl -X POST http://localhost:8888/api/device/tap \
  -H "Content-Type: application/json" \
  -d '{"text": "Login"}'
```

### Python

```python
import requests

# Run flow and stream results
with requests.post(
    'http://localhost:8888/api/flows/my_flow/run',
    stream=True
) as r:
    for line in r.iter_lines():
        if line:
            event = json.loads(line)
            print(event)
```

### JavaScript

```javascript
// Run flow with streaming
const response = await fetch('/api/flows/my_flow/run', {method: 'POST'});
const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
    const {value, done} = await reader.read();
    if (done) break;
    
    const lines = decoder.decode(value).split('\n');
    for (const line of lines) {
        if (line.trim()) {
            const event = JSON.parse(line);
            console.log(event);
        }
    }
}
```
