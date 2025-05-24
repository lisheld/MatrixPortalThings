#!/usr/bin/env python3
"""
Enhanced image converter for LED Matrix displays
Converts HEIC/JPEG images to optimized 24-bit BMPs for 64x64 LED matrices
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
        
        # Resize to target size
        return image.resize(target_size, Image.Resampling.LANCZOS)
    
    def quantize_colors(self, image, colors=256):
        """Reduce color palette for better LED display"""
        # Convert to palette mode with optimized colors
        return image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert('RGB')
    
    def apply_led_dithering(self, image):
        """Apply dithering optimized for LED displays"""
        # Convert to palette mode with dithering
        return image.quantize(colors=64, dither=Image.Dither.FLOYDSTEINBERG).convert('RGB')
    
    def convert_image(self, input_path, output_path, apply_dithering=False, quantize=False):
        """Convert a single image to LED-optimized BMP"""
        
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
                
                # Optimize for LED display
                image = self.optimize_for_led(image)
                print(f"  Applied LED optimizations")
                
                # Optional color quantization
                if quantize:
                    image = self.quantize_colors(image)
                    print(f"  Applied color quantization")
                
                # Optional dithering
                if apply_dithering:
                    image = self.apply_led_dithering(image)
                    print(f"  Applied LED dithering")
                
                # Save as 24-bit BMP
                image.save(output_path, 'BMP')
                print(f"  Saved: {output_path}")
                
                return True
                
        except Exception as e:
            print(f"  Error processing {input_path}: {e}")
            return False
    
    def batch_convert(self, input_dir, output_dir, apply_dithering=False, quantize=False):
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
        
        success_count = 0
        for img_file in image_files:
            output_file = output_path / f"{img_file.stem}.bmp"
            if self.convert_image(img_file, output_file, apply_dithering, quantize):
                success_count += 1
        
        print(f"\nConversion complete: {success_count}/{len(image_files)} images successful")

def main():
    parser = argparse.ArgumentParser(description='Convert images to LED matrix optimized BMPs')
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('output', help='Output file or directory')
    parser.add_argument('--dither', action='store_true', help='Apply LED-optimized dithering')
    parser.add_argument('--quantize', action='store_true', help='Reduce color palette')
    parser.add_argument('--brightness', type=float, default=0.7, help='Brightness factor (0.1-1.0)')
    parser.add_argument('--contrast', type=float, default=1.2, help='Contrast factor (0.5-2.0)')
    parser.add_argument('--size', type=int, nargs=2, default=[64, 64], help='Matrix size (width height)')
    
    args = parser.parse_args()
    
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
        converter.convert_image(input_path, output_path, args.dither, args.quantize)
    elif input_path.is_dir():
        # Batch conversion
        converter.batch_convert(input_path, output_path, args.dither, args.quantize)
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)

if __name__ == "__main__":
    main()