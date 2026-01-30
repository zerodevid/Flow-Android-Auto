# Droidrun Portal - Knowledge Reference

> **Source**: https://github.com/droidrun/droidrun-portal

## Overview

**Droidrun Portal** adalah Android Accessibility Service yang menyediakan:
- Real-time visual feedback dan data collection untuk UI elements
- Interactive overlay yang menandai elemen: clickable, checkable, editable, scrollable, focusable
- Berguna untuk **UI testing**, **automation development**, dan **accessibility assessment**

## Fitur Utama

| Fitur | Deskripsi |
|-------|-----------|
| Interactive Overlay | Highlight elemen UI interaktif di layar |
| Local Control APIs | HTTP socket server, WebSocket JSON-RPC, ContentProvider |
| Reverse WebSocket | Koneksi ke cloud untuk remote control |
| WebRTC Streaming | Screen streaming dengan auto-accept |
| APK Install | Install APK dari URL (termasuk split APKs) |
| Notification Events | Streaming event notifikasi |

## API yang Tersedia

1. **HTTP Socket Server** - Port default `8080`
2. **WebSocket Server** - Port default `8081`
3. **ContentProvider** - Via ADB commands dengan authority `content://com.droidrun.portal/`

## ADB Commands Reference

### Query Commands (Membaca Data)

```bash
# Test koneksi
adb shell content query --uri content://com.droidrun.portal/ping

# Versi app
adb shell content query --uri content://com.droidrun.portal/version

# Accessibility tree sebagai JSON (visible elements dengan overlay indices)
adb shell content query --uri content://com.droidrun.portal/a11y_tree

# Full accessibility tree dengan SEMUA properties
adb shell content query --uri content://com.droidrun.portal/a11y_tree_full

# Phone state (current app, focused element, keyboard visibility)
adb shell content query --uri content://com.droidrun.portal/phone_state

# Combined state (a11y tree + phone state)
adb shell content query --uri content://com.droidrun.portal/state

# Full combined state (full tree + phone state + device context)
adb shell content query --uri content://com.droidrun.portal/state_full

# List installed launchable apps
adb shell content query --uri content://com.droidrun.portal/packages

# Auth token untuk HTTP/WS access
adb shell content query --uri content://com.droidrun.portal/auth_token
```

### Insert Commands (Actions & Configuration)

```bash
# Input teks via keyboard (base64 encoded, clear field dulu by default)
adb shell content insert --uri content://com.droidrun.portal/keyboard/input --bind base64_text:s:"SGVsbG8gV29ybGQ="

# Input teks tanpa clear field
adb shell content insert --uri content://com.droidrun.portal/keyboard/input --bind base64_text:s:"SGVsbG8=" --bind clear:b:false

# Clear text di focused input field
adb shell content insert --uri content://com.droidrun.portal/keyboard/clear

# Send key event (Enter=66, Backspace=67, dll)
adb shell content insert --uri content://com.droidrun.portal/keyboard/key --bind key_code:i:66

# Toggle overlay visibility
adb shell content insert --uri content://com.droidrun.portal/overlay_visible --bind visible:b:true

# Set socket port
adb shell content insert --uri content://com.droidrun.portal/socket_port --bind port:i:8090

# Enable WebSocket server
adb shell content insert --uri content://com.droidrun.portal/toggle_websocket_server --bind enabled:b:true --bind port:i:8081
```

### Common Key Codes

| Key | Code | Key | Code |
|-----|------|-----|------|
| Enter | 66 | Backspace | 67 |
| Tab | 61 | Escape | 111 |
| Home | 3 | Back | 4 |
| Up | 19 | Down | 20 |
| Left | 21 | Right | 22 |

## Response Format

Semua response ContentProvider mengikuti format:

```json
// Success
{
  "status": "success",
  "result": "..."
}

// Error
{
  "status": "error",
  "error": "Error message"
}
```

## Technical Details

- **Minimum Android**: API 30 (Android 11.0)
- **Bahasa**: Kotlin
- **API**: Android Accessibility Service API
- **Overlay**: Custom drawing via Window Manager
- **Support**: Multi-window environments

## Setup

1. Install APK di Android device
2. Enable accessibility service: Settings → Accessibility → Droidrun Portal
3. Grant overlay permission
4. (Optional) Buka Settings di app untuk enable local servers atau reverse connection

## Kegunaan untuk Automation

Droidrun Portal sangat berguna untuk:
- **Auto-register/login automation** - Baca UI elements dan trigger actions
- **UI Testing** - Get accessibility tree untuk validasi
- **Bot automation** - Kontrol device via API
- **Remote control** - Via WebSocket/reverse connection

---

## Detailed Response Structure (from testing)

### `/phone_state` Response
```json
{
  "status": "success",
  "result": {
    "packageName": "org.toshi",
    "activityName": "org.toshi.MainActivity",
    "keyboardVisible": false,
    "isEditable": false,
    "focusedElement": {
      "resourceId": ""
    }
  }
}
```

### `/packages` Response
Array of installed apps:
```json
{
  "packageName": "com.android.chrome",
  "label": "Chrome",
  "versionName": "113.0.5672.136",
  "versionCode": 567263637,
  "isSystemApp": true
}
```

### `/a11y_tree` Response (Basic)
Hierarchical tree of UI elements:
```json
{
  "index": 8,
  "resourceId": "nav-back-arrow",
  "className": "Button",
  "text": "Back",
  "bounds": "58, 105, 121, 168",
  "children": [...]
}
```
- **index**: Overlay index untuk referensi elemen
- **resourceId**: ID dari elemen (berguna untuk targeting)
- **className**: Tipe widget (Button, TextView, EditText, etc)
- **text**: Text content atau contentDescription
- **bounds**: Posisi layar "left, top, right, bottom"
- **children**: Nested child elements

### `/a11y_tree_full` Response (Complete)
Full metadata per element:
```json
{
  "resourceId": "mfa-setup-key-input",
  "className": "android.widget.Button",
  "packageName": "org.toshi",
  "text": "",
  "contentDescription": "5VTC...63D6",
  "boundsInScreen": {"left": 63, "top": 960, "right": 1017, "bottom": 1112},
  "isClickable": true,
  "isLongClickable": false,
  "isFocusable": true,
  "isEditable": false,
  "isScrollable": false,
  "isEnabled": true,
  "isVisibleToUser": true,
  "actionList": [
    {"id": 16, "name": "CLICK"},
    {"id": 1, "name": "FOCUS"},
    ...
  ],
  "children": [...]
}
```

### Action IDs Reference
| ID | Action Name |
|----|-------------|
| 1 | FOCUS |
| 4 | SELECT |
| 8 | CLEAR_SELECTION |
| 16 | CLICK |
| 32 | LONG_CLICK |
| 64 | UNKNOWN_64 (Accessibility focus) |
| 256 | UNKNOWN_256 (Next/Previous) |
| 512 | UNKNOWN_512 (Scroll) |

### `/state` dan `/state_full`
Kombinasi dari phone_state + accessibility tree dalam satu response.

---

## Tips Automation

1. **Cari element by resourceId**: Scan a11y_tree untuk menemukan element dengan `resourceId` spesifik
2. **Cari element by text**: Match `text` field untuk button labels, input hints
3. **Check isClickable/isEditable**: Validasi apakah element bisa di-click atau di-edit
4. **Use bounds for tap**: Koordinat bounds bisa digunakan untuk tap via ADB input
5. **Monitor keyboardVisible**: Untuk tahu kapan keyboard muncul setelah focus EditText
