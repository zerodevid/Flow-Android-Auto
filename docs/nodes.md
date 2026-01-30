# Node Types Reference

Referensi lengkap semua jenis node dan parameternya.

---

## 📊 Data Source

Batch data input untuk looping flow dengan multiple data rows.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `columns` | array | ✓ | `["email", "password"]` | Nama kolom data |
| `rows` | array | ✓ | `[]` | Array of objects dengan data |

**Contoh:**
```json
{
  "action": "data_source",
  "params": {
    "columns": ["email", "password", "username"],
    "rows": [
      {"email": "user1@mail.com", "password": "pass1", "username": "user1"},
      {"email": "user2@mail.com", "password": "pass2", "username": "user2"}
    ]
  }
}
```

**Import CSV:**
Header baris pertama jadi column names.

---

## 🚀 Launch

Membuka aplikasi Android by package name.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `package` | string | ✓ | - | Package name aplikasi |

**Contoh:**
```json
{"action": "launch", "params": {"package": "com.twitter.android"}}
```

---

## 👆 Tap

Tap element di screen. Bisa by text, resource_id, index, atau coordinates.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | - | - | Text content element |
| `resource_id` | string | - | - | Android resource ID |
| `index` | int | - | - | Element index dari list |
| `x` | int | - | - | X coordinate |
| `y` | int | - | - | Y coordinate |
| `timeout` | float | - | 10 | Wait timeout (seconds) |
| `wait_for` | bool | - | true | Wait for element first |
| `delay` | float | - | 0 | Delay before tap |

**Prioritas:** `x,y` > `resource_id` > `text` > `index`

**Contoh:**
```json
// By text
{"action": "tap", "params": {"text": "Sign Up", "timeout": 5}}

// By resource_id
{"action": "tap", "params": {"resource_id": "com.app:id/btn_login"}}

// By coordinates
{"action": "tap", "params": {"x": 540, "y": 1200}}

// By index
{"action": "tap", "params": {"index": 5}}
```

---

## ⌨️ Type

Input text ke focused field.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | - | - | Text statis untuk input |
| `from_data` | string | - | - | Ambil dari captured data |
| `clear` | bool | - | true | Clear field sebelum type |
| `delay` | float | - | 0 | Delay before typing |

**Contoh:**
```json
// Static text
{"action": "type", "params": {"text": "hello@email.com", "clear": true}}

// From captured/data source
{"action": "type", "params": {"from_data": "email"}}
```

---

## ⏳ Wait

Wait until element muncul di screen.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | ✓ | - | Text element yang ditunggu |
| `timeout` | float | - | 10 | Maximum wait time |

**Contoh:**
```json
{"action": "wait", "params": {"text": "Welcome", "timeout": 30}}
```

---

## 🔑 Key

Press hardware key.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `key` | string | ✓ | - | Key name |

**Available keys:**
- `enter` - Enter/OK
- `back` - Back button
- `home` - Home button
- `backspace` - Delete char
- `tab` - Tab key

**Contoh:**
```json
{"action": "key", "params": {"key": "enter"}}
```

---

## 📜 Scroll

Scroll the screen.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `direction` | string | - | "down" | `up` atau `down` |
| `distance` | int | - | 500 | Scroll distance in pixels |

**Contoh:**
```json
{"action": "scroll", "params": {"direction": "down", "distance": 800}}
```

---

## ⏱️ Delay

Fixed time delay.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `seconds` | float | ✓ | - | Delay duration |

**Contoh:**
```json
{"action": "delay", "params": {"seconds": 2.5}}
```

---

## 🔀 Condition

Branch flow berdasarkan kondisi screen.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `check_text` | string | ✓ | - | Text untuk dicek |
| `timeout` | float | - | 5 | Check timeout |

**Output ports:**
- `yes` - Text ditemukan
- `no` - Text tidak ditemukan

**Contoh:**
```json
{"action": "condition", "params": {"check_text": "Success"}}
```

---

## 📬 OTP

Wait for SMS OTP dari server.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `timeout` | float | - | 120 | Wait timeout (seconds) |
| `save_as` | string | - | "otp" | Variable name untuk save |

**Contoh:**
```json
{"action": "otp", "params": {"timeout": 120, "save_as": "sms_code"}}
```

**Note:** OTP diterima via `POST /otp` ke server port 5000.

---

## 🔐 TOTP

Generate TOTP 2FA code.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `secret` | string | - | - | TOTP secret (statis) |
| `from_data` | string | - | - | Ambil secret dari data |
| `save_as` | string | - | "totp" | Variable name untuk save |
| `wait_fresh` | bool | - | false | Wait for fresh code |
| `min_remaining` | int | - | 5 | Min seconds remaining |

**Contoh:**
```json
// Static secret
{"action": "totp", "params": {"secret": "JBSWY3DPEHPK3PXP", "save_as": "code"}}

// From captured data (e.g., dari clipboard)
{"action": "totp", "params": {"from_data": "totp_secret", "save_as": "code"}}
```

---

## 📝 Capture

Capture text dari element dan save ke variable.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | - | - | Find by text content |
| `resource_id` | string | - | - | Find by resource ID |
| `index` | int | - | - | Find by element index |
| `save_as` | string | ✓ | - | Variable name |
| `timeout` | float | - | 10 | Find timeout |

**Contoh:**
```json
{"action": "capture", "params": {"resource_id": "com.app:id/account_id", "save_as": "account"}}
```

---

## 📋 Clipboard

Copy content via browser bridge (untuk Android 10+).

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `text` | string | - | - | Text of copy button |
| `resource_id` | string | - | - | Resource ID of copy button |
| `index` | int | - | - | Index of copy button |
| `save_as` | string | ✓ | - | Variable name |
| `timeout` | float | - | 15 | Capture timeout |

**Contoh:**
```json
{"action": "clipboard", "params": {"text": "Copy", "save_as": "secret_key"}}
```

---

## 🌐 Webhook

Send HTTP request dengan captured data.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `url` | string | ✓ | - | Webhook URL |
| `method` | string | - | "POST" | HTTP method |
| `include_data` | bool | - | true | Include captured data |

**Contoh:**
```json
{
  "action": "webhook",
  "params": {
    "url": "https://webhook.site/xxx",
    "method": "POST",
    "include_data": true
  }
}
```

Request body akan berisi semua captured data dari flow.

---

## 🛑 Close

Force-stop application dan hapus dari RAM.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `package` | string | ✓ | - | Package name aplikasi |

**Contoh:**
```json
{"action": "close", "params": {"package": "com.google.android.calculator"}}
```

---

## 📟 Shell

Jalankan ADB shell command.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `command` | string | ✓ | - | Shell command (tanpa 'adb shell' prefix) |

**Contoh:**
```json
{"action": "shell", "params": {"command": "input keyevent 26"}}
```

