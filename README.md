# Auto Register - Android Automation Framework

🤖 **Visual flow-based automation framework** untuk Android menggunakan DroidrunPortal dan Flow Editor.

![Flow Editor](docs/flow-editor-screenshot.png)

## ✨ Fitur Utama

- **🎨 Visual Flow Editor** - Drag & drop interface untuk membuat automation flows
- **📊 Data Source Node** - Batch processing dengan data dari CSV atau manual input
- **📬 OTP/TOTP Support** - Automatic OTP capture dan TOTP code generation
- **🌐 Webhook Integration** - Send hasil automation ke external services
- **🤖 AI Agent Support** - Bisa disuruh bikin flow via chat dengan AI assistant

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install flask pyotp
```

### 2. Setup Android Device

Pastikan device Android terhubung via ADB dan Droidrun Portal sudah terinstall:

```bash
adb devices  # Harus muncul device
```

### 3. Jalankan Server

```bash
python3 web/app.py -p 8888
```

Buka browser ke `http://localhost:8888`

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Flow Editor Guide](docs/flow-editor.md) | Cara pakai visual flow editor |
| [Node Types Reference](docs/nodes.md) | Semua jenis node dan parameternya |
| [AI Agent Prompts](docs/ai-agent.md) | Contoh prompt untuk AI assistant |
| [API Reference](docs/api.md) | REST API endpoints |

## 🎯 Cara Membuat Flow

### Method 1: Visual Editor

1. Buka `http://localhost:8888`
2. Drag node dari palette ke canvas
3. Hubungkan node dengan klik output → input
4. Konfigurasi parameter di panel kanan
5. Klik **▶ Run** untuk jalankan

### Method 2: AI Agent (Chat)

Bisa minta AI assistant untuk control Android langsung dan generate flow:

```
"Buatkan flow untuk buka aplikasi Calculator dan hitung 134 * 421 / 3221"
```

AI akan:
1. Control Android step-by-step
2. Record semua action
3. Generate flow JSON yang bisa di-replay

**Contoh prompt lainnya:**
- *"Buka Twitter, tap Sign Up, isi email dengan data dari kolom email"*
- *"Record flow registrasi Gmail dengan batch data"*
- *"Automate login Facebook dengan TOTP"*

### Method 3: Manual JSON

Buat file `.json` di folder `flows/`:

```json
{
  "name": "My Flow",
  "steps": [
    {"action": "launch", "params": {"package": "com.example.app"}},
    {"action": "tap", "params": {"text": "Login"}},
    {"action": "type", "params": {"text": "username"}}
  ]
}
```

## 📊 Batch Processing

Gunakan **Data Source** node untuk run flow dengan multiple data:

1. Tambahkan Data Source node di awal flow
2. Define columns: `email, password, username`
3. Tambah rows manual atau import CSV
4. Di node Type, gunakan `from_data: email` untuk ambil value
5. Flow akan loop otomatis untuk setiap row

## 🔧 Node Types

| Icon | Node | Description |
|------|------|-------------|
| 📊 | Data Source | Batch data input (CSV/manual) |
| 🚀 | Launch | Buka aplikasi |
| 👆 | Tap | Tap element by text/resource_id/index |
| ⌨️ | Type | Input text |
| ⏳ | Wait | Wait for element appear |
| 🔑 | Key | Press hardware key |
| 📜 | Scroll | Scroll screen |
| ⏱️ | Delay | Fixed time delay |
| 📬 | OTP | Wait for SMS OTP |
| 🔐 | TOTP | Generate 2FA code |
| 📝 | Capture | Save element text |
| 🌐 | Webhook | Send HTTP request |

Lihat [docs/nodes.md](docs/nodes.md) untuk parameter lengkap.

## 📂 Project Structure

```
auto_register/
├── web/                    # Flow Editor web server
│   ├── app.py              # Flask API server
│   └── static/             # Frontend assets
├── core/                   # Automation engine
│   ├── flow_runner.py      # Step executor
│   └── droidrun_portal.py  # Android connection
├── server/                 # OTP/Clipboard server
├── flows/                  # Saved flow files
├── docs/                   # Documentation
└── .agent/                 # AI agent configs
    ├── knowledge/          # Agent knowledge base
    └── workflows/          # Automated workflows
```

## 🔌 API Endpoints

```bash
# List flows
GET /api/flows

# Get/Save flow
GET/PUT /api/flows/<id>

# Run flow
POST /api/flows/<id>/run

# Stop flow
POST /api/flows/<id>/stop

# Device info
GET /api/device/elements
POST /api/device/tap
POST /api/device/type
```

## 📄 License

Internal Project - All Rights Reserved
