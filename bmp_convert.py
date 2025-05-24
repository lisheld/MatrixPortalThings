#!/usr/bin/env python3
"""
Enhanced image converter for LED Matrix displays
Converts HEIC/JPEG images to optimized palette BMPs for 64x64 LED matrices
"""

import os
import sys
from PIL import Image, ImageEnhance, ImageFilter
import pillow_heif
from pathlib import Path
import argparse

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()

class LEDMatrixConverter:
    def __init__(self, matrix_size=(64, 64), brightness_factor=0.7, contrast_factor=1.2):
        self.matrix_size = matrix_size
        self.brightness_factor = brightness_factor
        self.contrast_factor = contrast_factor
        
    def optimize_for_led(self, image):
        """Optimize image colors and brightness for LED matrix display"""
        
        # Enhance contrast slightly to compensate for LED limitations
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(self.contrast_factor)
        
        # Reduce brightness to prevent overwhelming LEDs
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(self.brightness_factor)
        
        # Boost saturation slightly for more vivid colors on LEDs
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.1)
        
        return image

    def smart_crop_resize(self, image, target_size):
        """Smart crop and resize to maintain aspect ratio and focus on center"""
        
        # Calculate aspect ratios
        img_ratio = image.width / image.height
        target_ratio = target_size[0] / target_size[1]
        
        if img_ratio > target_ratio:
            # Image is wider than target - crop width
            new_height = image.height
            new_width = int(new_height * target_ratio)
            left = (image.width - new_width) // 2
            image = image.crop((left, 0, left + new_width, new_height))
        elif img_ratio < target_ratio:
            # Image is taller than target - crop height
            new_width = image.width
            new_height = int(new_width / target_ratio)
            top = (image.height - new_height) // 2
            image = image.crop((0, top, new_width, top + new_height))
        
        # Resize to target size with high quality resampling
        return image.resize(target_size, Image.Resampling.LANCZOS)
    
    def quantize_colors(self, image, colors=256):
        """Reduce color palette for better LED display (returns RGB for further processing)"""
        # Convert to palette mode with optimized colors, then back to RGB
        quantized = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        return quantized.convert('RGB')
    
    def apply_led_dithering(self, image):
        """Apply dithering optimized for LED displays (returns RGB for further processing)"""
        # Convert to palette mode with dithering, then back to RGB
        dithered = image.quantize(colors=64, dither=Image.Dither.FLOYDSTEINBERG)
        return dithered.convert('RGB')
    
    def save_palette_bmp(self, image, output_path, colors=256, use_spatial_dithering=False):
        """Create palette BMP with explicit palette mode for CircuitPython"""
        print(f"  Converting to {colors}-color palette BMP...")
        
        # Ensure we're in RGB mode first
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Choose dithering method based on parameter
        if use_spatial_dithering:
            dither_method = Image.Dither.FLOYDSTEINBERG
            print(f"  Using Floyd-Steinberg spatial dithering for better color accuracy")
        else:
            dither_method = Image.Dither.NONE
        
        # Convert to palette mode
        palette_image = image.quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT,
            dither=dither_method
        )
        
        # Verify we're in palette mode
        if palette_image.mode != 'P':
            print(f"  Warning: Image mode is {palette_image.mode}, forcing to P mode")
            palette_image = palette_image.convert('P')
        
        # Save as BMP with explicit 8-bit palette format
        palette_image.save(output_path, 'BMP', bits=8)
        
        # Verify the saved file
        try:
            with Image.open(output_path) as test_img:
                print(f"  ✓ Saved: {test_img.mode} {test_img.size}")
                if hasattr(test_img, 'getpalette') and test_img.getpalette():
                    palette_colors = len(test_img.getpalette()) // 3
                    print(f"  ✓ Palette: {palette_colors} colors")
        except Exception as e:
            print(f"  Warning: Could not verify saved file: {e}")

    def generate_github_url(self, filename, use_spatial_dithering):
        """Generate the correct GitHub URL for a BMP file"""
        folder_name = "bmp_dither" if use_spatial_dithering else "bmp"
        return f"https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/{folder_name}/{filename}"

    def process_single_image(self, input_path, output_path, apply_dithering=False, quantize=False, palette_colors=256, spatial_dither=False):
        """Process a single image file"""
        try:
            print(f"Processing: {input_path}")
            
            # Open and convert image
            with Image.open(input_path) as image:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                print(f"  Original size: {image.width}x{image.height}")
                
                # Smart crop and resize
                image = self.smart_crop_resize(image, self.matrix_size)
                print(f"  Resized to: {image.width}x{image.height}")
                
                # Apply LED optimizations
                image = self.optimize_for_led(image)
                print(f"  Applied LED optimizations")
                
                # Optional pre-processing
                if quantize:
                    image = self.quantize_colors(image, colors=palette_colors)
                    print(f"  Applied color quantization to {palette_colors} colors")
                
                if apply_dithering:
                    image = self.apply_led_dithering(image)
                    print(f"  Applied LED dithering")
                
                # Save as palette BMP
                self.save_palette_bmp(image, output_path, colors=palette_colors, use_spatial_dithering=spatial_dither)
                
                # Show GitHub URL
                github_url = self.generate_github_url(output_path.name, spatial_dither)
                print(f"  GitHub URL: \"{github_url}\"")
                
                return True
                
        except Exception as e:
            print(f"  ERROR: {e}")
            return False

    def convert_images(self, input_path, output_path, apply_dithering=False, quantize=False, palette_colors=256, spatial_dither=False):
        """Convert single file or batch of files"""
        
        input_path = Path(input_path)
        output_path = Path(output_path)
        
        if input_path.is_file():
            # Single file conversion
            if output_path.is_dir() or not output_path.suffix:
                output_file = output_path / f"{input_path.stem}.bmp"
            else:
                output_file = output_path
            
            success = self.process_single_image(
                input_path, output_file, apply_dithering, quantize, palette_colors, spatial_dither
            )
            
            if success:
                print(f"\n✓ Conversion successful!")
            else:
                print(f"\n✗ Conversion failed!")
            
            return
        
        elif input_path.is_dir():
            # Batch conversion
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Find all supported images
            supported_formats = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.bmp', '.tiff', '.webp'}
            image_files = []
            for ext in supported_formats:
                image_files.extend(input_path.glob(f'*{ext}'))
                image_files.extend(input_path.glob(f'*{ext.upper()}'))
            
            if not image_files:
                print(f"No supported image files found in {input_path}")
                return
            
            print(f"Found {len(image_files)} images to convert")
            print(f"Output directory: {output_path}")
            print(f"Settings: colors={palette_colors}, spatial_dither={spatial_dither}")
            print("-" * 60)
            
            # Process all images
            success_count = 0
            successful_files = []
            
            for img_file in image_files:
                output_file = output_path / f"{img_file.stem}.bmp"
                if self.process_single_image(img_file, output_file, apply_dithering, quantize, palette_colors, spatial_dither):
                    success_count += 1
                    successful_files.append(img_file)
                print()  # Add spacing between files
            
            # Show results and URLs
            print("-" * 60)
            print(f"Conversion complete: {success_count}/{len(image_files)} images successful")
            
            if successful_files:
                folder_name = "bmp_dither" if spatial_dither else "bmp"
                print(f"\nExample URLs for CircuitPython (update your IMAGE_URLS list):")
                
                for img_file in sorted(successful_files)[:4]:  # Show first 4
                    bmp_name = f"{img_file.stem}.bmp"
                    github_url = self.generate_github_url(bmp_name, spatial_dither)
                    print(f'    "{github_url}",')
                
                if len(successful_files) > 4:
                    print(f"    ... and {len(successful_files) - 4} more files")
                
                print(f"\nAll files are in the '{folder_name}' folder on GitHub")
        
        else:
            print(f"Error: {input_path} is not a valid file or directory")

def main():
    parser = argparse.ArgumentParser(description='Convert images to LED matrix optimized palette BMPs')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('--output', help='Output directory (optional - will auto-create /bmp or /bmp_dither)')
    parser.add_argument('--dither', action='store_true', help='Apply LED-optimized dithering')
    parser.add_argument('--quantize', action='store_true', help='Reduce color palette before final conversion')
    parser.add_argument('--spatial-dither', action='store_true', help='Use Floyd-Steinberg spatial dithering')
    parser.add_argument('--colors', type=int, default=256, help='Number of colors in final palette (default: 256)')
    parser.add_argument('--brightness', type=float, default=0.7, help='Brightness factor (0.1-1.0)')
    parser.add_argument('--contrast', type=float, default=1.2, help='Contrast factor (0.5-2.0)')
    parser.add_argument('--size', type=int, nargs=2, default=[64, 64], help='Matrix size (width height)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.colors < 2 or args.colors > 256:
        print("Error: --colors must be between 2 and 256")
        sys.exit(1)
    
    if not (0.1 <= args.brightness <= 1.0):
        print("Error: --brightness must be between 0.1 and 1.0")
        sys.exit(1)
        
    if not (0.5 <= args.contrast <= 2.0):
        print("Error: --contrast must be between 0.5 and 2.0")
        sys.exit(1)
    
    # Auto-determine output path if not specified
    if args.output:
        output_path = args.output
    else:
        if args.spatial_dither:
            output_path = "bmp_dither"
            print("Auto-selected output: bmp_dither/ (for spatially dithered images)")
        else:
            output_path = "bmp"
            print("Auto-selected output: bmp/ (for clean, undithered images)")
    
    # Create converter
    converter = LEDMatrixConverter(
        matrix_size=tuple(args.size),
        brightness_factor=args.brightness,
        contrast_factor=args.contrast
    )
    
    # Convert images
    converter.convert_images(
        args.input, 
        output_path, 
        args.dither, 
        args.quantize, 
        args.colors, 
        args.spatial_dither
    )

if __name__ == "__main__":
    main()