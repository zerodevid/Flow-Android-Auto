from PIL import Image
import subprocess
import time

s = time.time()
print("Capturing screen...")
subprocess.run(["adb", "shell", "screencap", "-p", "/sdcard/screen.png"], check=True)
subprocess.run(["adb", "pull", "/sdcard/screen.png", "screen.png"], check=True)

img = Image.open("screen.png")
pixels = img.load()
width, height = img.size

print(f"Screen size is {width}x{height}")

# Warna biru Google sekitar rgb(26,115,232)
def is_google_blue(r, g, b):
    # Hue ~214deg, Sat ~89%, Val ~91%
    return 10 < r < 70 and 100 < g < 160 and 200 <= b <= 255

xs = []
ys = []

# Hanya scan dari tengah ke bawah untuk menghindari header biru
start_y = height // 2

for y in range(start_y, height):
    for x in range(width):
        r, g, b, *a = pixels[x, y]
        if is_google_blue(r, g, b):
            xs.append(x)
            ys.append(y)

if xs and ys:
    cx = sum(xs) // len(xs)
    cy = sum(ys) // len(ys)
    print(f"Tombol 'I agree' ditemukan!")
    print(f"Koordinat sentuh (X, Y) yang disarankan: {cx}, {cy}")
else:
    print("Tombol biru tidak ditemukan. Coba tekan Tab (61) dan Enter (66) saja.")
