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
    
    def save_palette_bmp(self, image, output_path, colors=256):
        """
        Create palette BMP with explicit palette mode for CircuitPython
        This method ensures the BMP has a proper color palette that CircuitPython can read
        """
        print(f"  Converting to {colors}-color palette BMP...")
        
        # Ensure we're in RGB mode first
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to palette mode with specific settings for better LED display
        palette_image = image.quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT,  # Good color selection
            dither=Image.Dither.NONE  # Let CircuitPython handle dithering
        )
        
        # Verify we're in palette mode
        if palette_image.mode != 'P':
            print(f"  Warning: Image mode is {palette_image.mode}, forcing to P mode")
            palette_image = palette_image.convert('P')
        
        # Get palette info for debugging
        palette = palette_image.getpalette()
        palette_colors = len(palette) // 3 if palette else 0
        
        print(f"  Final image mode: {palette_image.mode}")
        print(f"  Palette colors: {palette_colors}")
        
        # Save as BMP with explicit 8-bit palette format
        # This should create a BMP that CircuitPython recognizes as having a palette
        palette_image.save(output_path, 'BMP', bits=8)
        
        # Verify the saved file
        try:
            with Image.open(output_path) as test_img:
                print(f"  Verified saved BMP: mode={test_img.mode}, size={test_img.size}")
                if hasattr(test_img, 'getpalette') and test_img.getpalette():
                    print(f"  ✓ Palette confirmed: {len(test_img.getpalette()) // 3} colors")
                else:
                    print(f"  ✗ Warning: No palette detected in saved file")
        except Exception as e:
            print(f"  Warning: Could not verify saved file: {e}")
        
        print(f"  Saved palette BMP: {output_path}")

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
    
    def create_led_optimized_palette(self, image, colors=256):
        """Create a palette specifically optimized for LED matrices"""
        
        # First, optimize the image for LED display
        led_optimized = self.optimize_for_led(image.copy())
        
        # Create palette using the LED-optimized version
        palette_image = led_optimized.quantize(
            colors=colors,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE  # No dithering - let CircuitPython handle it
        )
        
        return palette_image
    
    def convert_image(self, input_path, output_path, apply_dithering=False, quantize=False, palette_colors=256):
        """Convert a single image to LED-optimized palette BMP"""
        
        try:
            print(f"Processing: {input_path}")
            
            # Open image
            with Image.open(input_path) as image:
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                
                print(f"  Original size: {image.width}x{image.height}")
                
                # Smart crop and resize
                image = self.smart_crop_resize(image, self.matrix_size)
                print(f"  Resized to: {image.width}x{image.height}")
                
                # Optional pre-processing before palette creation
                if quantize:
                    image = self.quantize_colors(image, colors=palette_colors)
                    print(f"  Applied color quantization to {palette_colors} colors")
                
                if apply_dithering:
                    image = self.apply_led_dithering(image)
                    print(f"  Applied LED dithering")
                
                # Always save as palette BMP for CircuitPython compatibility
                self.save_palette_bmp(image, output_path, colors=palette_colors)
                
                return True
                
        except Exception as e:
            print(f"  Error processing {input_path}: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            return False
    
    def batch_convert(self, input_dir, output_dir, apply_dithering=False, quantize=False, palette_colors=256):
        """Convert all supported images in a directory"""
        
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Supported formats
        supported_formats = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.bmp', '.tiff', '.webp'}
        
        # Find all supported images
        image_files = []
        for ext in supported_formats:
            image_files.extend(input_path.glob(f'*{ext}'))
            image_files.extend(input_path.glob(f'*{ext.upper()}'))
        
        if not image_files:
            print(f"No supported image files found in {input_dir}")
            return
        
        print(f"Found {len(image_files)} images to convert")
        print(f"Output directory: {output_path}")
        print(f"Palette colors: {palette_colors}")
        print(f"Dithering: {apply_dithering}")
        print(f"Quantize: {quantize}")
        print("-" * 50)
        
        success_count = 0
        for img_file in image_files:
            output_file = output_path / f"{img_file.stem}.bmp"
            if self.convert_image(img_file, output_file, apply_dithering, quantize, palette_colors):
                success_count += 1
            print()  # Add spacing between files
        
        print("-" * 50)
        print(f"Conversion complete: {success_count}/{len(image_files)} images successful")
        
        # Show some example URLs for testing
        if success_count > 0:
            print(f"\nExample URLs for CircuitPython (update your IMAGE_URLS list):")
            for img_file in sorted(image_files)[:4]:  # Show first 4
                bmp_name = f"{img_file.stem}.bmp"
                print(f'    "https://your-github-repo/path/to/{bmp_name}",')

def main():
    parser = argparse.ArgumentParser(description='Convert images to LED matrix optimized palette BMPs')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('output', help='Output file or directory')
    parser.add_argument('--dither', action='store_true', help='Apply LED-optimized dithering')
    parser.add_argument('--quantize', action='store_true', help='Reduce color palette before final conversion')
    parser.add_argument('--colors', type=int, default=256, help='Number of colors in final palette (default: 256)')
    parser.add_argument('--brightness', type=float, default=0.7, help='Brightness factor (0.1-1.0)')
    parser.add_argument('--contrast', type=float, default=1.2, help='Contrast factor (0.5-2.0)')
    parser.add_argument('--size', type=int, nargs=2, default=[64, 64], help='Matrix size (width height)')
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.colors < 2 or args.colors > 256:
        print("Error: --colors must be between 2 and 256")
        sys.exit(1)
    
    if args.brightness < 0.1 or args.brightness > 1.0:
        print("Error: --brightness must be between 0.1 and 1.0")
        sys.exit(1)
        
    if args.contrast < 0.5 or args.contrast > 2.0:
        print("Error: --contrast must be between 0.5 and 2.0")
        sys.exit(1)
    
    # Create converter with custom settings
    converter = LEDMatrixConverter(
        matrix_size=tuple(args.size),
        brightness_factor=args.brightness,
        contrast_factor=args.contrast
    )
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if input_path.is_file():
        # Single file conversion
        converter.convert_image(input_path, output_path, args.dither, args.quantize, args.colors)
    elif input_path.is_dir():
        # Batch conversion
        converter.batch_convert(input_path, output_path, args.dither, args.quantize, args.colors)
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()