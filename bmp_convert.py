import os
from PIL import Image
import pillow_heif

SOURCE_DIR = "source"  # Directory containing source images
BMP_DIR = "bmp"       # Directory for output BMP files
GITHUB_RAW_URL = "https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/bmp/"

# Create output directory if it doesn't exist
os.makedirs(BMP_DIR, exist_ok=True)

def convert_and_save(img, out_path):
    # Crop to square, centered
    w, h = img.size
    min_side = min(w, h)
    left = (w - min_side) // 2
    top = (h - min_side) // 2
    img = img.crop((left, top, left + min_side, top + min_side))
    
    # Resize to 64x64
    img = img.resize((64, 64), Image.LANCZOS)
    
    # Convert to RGB mode
    img = img.convert("RGB")
    
    # Quantize to 16 colors (4-bit) with Floyd-Steinberg dithering
    img = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    
    # Convert back to RGB to ensure proper BMP format
    img = img.convert("RGB")
    
    # Save as BMP
    img.save(out_path, format="BMP")

# Process all images in source directory
for fname in os.listdir(SOURCE_DIR):
    fpath = os.path.join(SOURCE_DIR, fname)
    name, ext = os.path.splitext(fname)
    ext = ext.lower()
    
    if ext in [".jpg", ".jpeg", ".png", ".heic"]:
        try:
            if ext == ".heic":
                heif_file = pillow_heif.read_heif(fpath)
                img = Image.frombytes(
                    heif_file.mode, 
                    heif_file.size, 
                    heif_file.data, 
                    "raw", 
                    heif_file.mode
                )
            else:
                img = Image.open(fpath)
            
            out_name = name + ".bmp"
            out_path = os.path.join(BMP_DIR, out_name)
            convert_and_save(img, out_path)
            print(f"Converted: {fname} -> {out_name}")
            
        except Exception as e:
            print(f"Failed to convert {fname}: {e}")

# Print all BMP URLs in Python list format
print("\nBMP URL List:")
print("[")
for bmp_file in sorted(os.listdir(BMP_DIR)):
    if bmp_file.lower().endswith(".bmp"):
        print(f'    "{GITHUB_RAW_URL}{bmp_file}",')
print("]") 