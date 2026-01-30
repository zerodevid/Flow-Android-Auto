# AI Agent Prompts Guide

Panduan cara menggunakan AI assistant untuk membuat automation flows.

## Konsep

AI agent dapat:
1. **Control Android** langsung via DroidrunPortal API
2. **Record actions** yang dilakukan
3. **Generate flow JSON** dari recording

## Prompt Examples

### Basic Recording

```
"Buatkan flow untuk buka kalkulator dan hitung 134 * 421 / 3221"
```

AI akan:
- Launch calculator app
- Tap digit buttons satu-satu
- Record semua actions
- Save sebagai flow JSON

### Registration Flow

```
"Buatkan flow registrasi untuk aplikasi Twitter dengan 
data email, password, dan username"
```

AI akan:
- Tanya package name app
- Launch app
- Navigate ke registration
- Map input fields
- Create Data Source dengan columns yang diminta

### Batch Processing

```
"Buatkan flow untuk login Facebook dengan batch data.
Columns: email, password
Langkah: buka app → tap Login → isi email → isi password → tap Submit"
```

### TOTP Flow

```
"Record flow untuk setup 2FA di aplikasi XYZ:
1. Buka app
2. Tap Settings
3. Tap Security
4. Copy TOTP secret
5. Generate code
6. Input code ke field"
```

### Dengan Webhook

```
"Buatkan flow registrasi dengan webhook.
Setelah registrasi berhasil, capture user_id dan kirim ke:
https://webhook.site/xxxxx"
```

## Interactive Mode

Untuk control step-by-step:

```
User: "Buka aplikasi Gmail"
AI: [Launch com.google.android.gm] ✓ Done

User: "Tap Create Account"
AI: [Tap "Create account"] ✓ Done

User: "Isi first name dengan data dari kolom 'first_name'"
AI: [Tap first name field → Type from_data: first_name] ✓ Done

User: "Selesai, simpan flow"
AI: [Generate flow JSON] → Saved to flows/gmail_register.json
```

## Tips untuk Prompt yang Baik

### ✓ Good Prompts

```
"Buatkan flow untuk buka app com.example.app, 
tap tombol 'Login', 
isi email dari data source,
isi password dari data source,
tap 'Submit'"
```

- Specific app package atau nama
- Step-by-step yang jelas
- Mention data source jika perlu batch

### ✗ Bad Prompts

```
"Automate registrasi"  // Terlalu vague
```

- Tidak jelas app apa
- Tidak ada step detail
- Tidak mention data yang dibutuhkan

## Data Source Prompts

Untuk include batch data:

```
"Buat flow dengan Data Source.
Columns: email, password, phone
Flow: launch → tap register → type email → type password → type phone → submit"
```

## Error Handling

```
"Buatkan flow dengan condition:
- Jika muncul 'Success' → selesai
- Jika muncul 'Error' → screenshot dan stop"
```

## Complex Flows

```
"Buatkan flow registrasi lengkap:
1. Data Source: email, password
2. Launch app
3. Wait for splash screen (5s)
4. Tap 'Sign Up'
5. Wait for form
6. Tap email field
7. Type email from data
8. Tap password field  
9. Type password from data
10. Tap 'Create Account'
11. Wait for OTP (120s)
12. Type OTP
13. Tap 'Verify'
14. Wait for 'Welcome'
15. Capture user_id
16. Webhook ke https://..."
```

## Slash Command

Gunakan workflow shortcut:

```
/create-flow untuk registrasi Gmail dengan email dan password
```

Ini akan trigger workflow template di `.agent/workflows/create-flow.md`.
