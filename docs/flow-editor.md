# Flow Editor Guide

Panduan lengkap cara menggunakan Visual Flow Editor.

## Membuka Flow Editor

1. Jalankan server:
   ```bash
   python3 web/app.py -p 8888
   ```

2. Buka browser ke `http://localhost:8888`

## Interface Overview

```
┌─────────────────────────────────────────────────────────────┐
│  🎨 Flow Editor                    [New] [Save] [▶ Run]     │
├──────────┬────────────────────────────────┬─────────────────┤
│  NODES   │                                │   PROPERTIES    │
│          │                                │                 │
│ 📊 Data  │       ┌─────┐   ┌─────┐       │   Node: Tap     │
│ 🚀 Launch│       │Start├──►│ Tap │       │   ─────────     │
│ 👆 Tap   │       └─────┘   └─────┘       │   Text: Login   │
│ ⌨️ Type  │                                │   Timeout: 10   │
│ ⏳ Wait  │                                │                 │
│ ...      │                                │   [📷 Preview]  │
│          │                                │                 │
│  DEVICE  │        CANVAS                  │                 │
│ [📷]     │                                │                 │
│ [img]    │                                │                 │
└──────────┴────────────────────────────────┴─────────────────┘
```

### Kolom Kiri - Node Palette & Device Preview
- **Node Palette**: Drag node ke canvas
- **Device Preview**: Screenshot Android device
- **Refresh**: Update screenshot

### Tengah - Canvas
- Area untuk menyusun flow
- Klik + drag untuk panning
- Scroll untuk zoom

### Kolom Kanan - Properties Panel
- Konfigurasi node yang dipilih
- Preview button untuk tap by coordinates

## Membuat Flow Baru

### Step 1: Tambah Node
1. Drag node dari palette ke canvas
2. Atau double-click node di palette

### Step 2: Hubungkan Node
1. Klik bulatan output (kanan node)
2. Drag ke bulatan input (kiri node lain)
3. Lepas untuk create connection

### Step 3: Konfigurasi Parameter
1. Klik node untuk select
2. Edit parameter di Properties Panel
3. Gunakan Device Preview untuk lihat element

### Step 4: Save Flow
1. Klik tombol **Save**
2. Masukkan nama flow
3. Flow tersimpan di `flows/` folder

### Step 5: Run Flow
1. Klik tombol **▶ Run**
2. Flow akan auto-save dulu
3. Lihat progress di Run Log

## Tips & Tricks

### Menggunakan Device Preview
1. Klik **📷 Refresh** untuk update screenshot
2. Klik **📋 Elements** untuk lihat semua UI elements
3. Klik element di list untuk auto-fill parameter

### Tap by Coordinates
1. Pilih node Tap
2. Klik **📷 Preview** di Properties
3. Klik lokasi di screenshot
4. Koordinat auto-fill ke X, Y

### Data Source untuk Batch
1. Tambahkan Data Source node di awal
2. Define columns (misal: email, password)
3. Tambah rows atau Import CSV
4. Di node lain, gunakan `from_data: email`

### Debugging
- Lihat **Run Log** untuk error
- Node akan highlight saat running
- Merah = error, Hijau = success

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Delete | Hapus node selected |
| Ctrl+S | Save flow |
| Ctrl+R | Run flow |
| Escape | Deselect node |

## Flow JSON Format

Flow disimpan sebagai JSON:

```json
{
  "name": "Flow Name",
  "steps": [
    {"action": "launch", "params": {...}},
    {"action": "tap", "params": {...}}
  ],
  "_editor": {
    "nodes": [...],
    "connections": [...]
  }
}
```

`_editor` section menyimpan posisi visual node.
