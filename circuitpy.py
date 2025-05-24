import time
import board
import displayio
import adafruit_requests
import ssl
import wifi
import socketpool
import adafruit_imageload
from adafruit_matrixportal.matrix import Matrix
import gc
import os
import io

# Import WiFi credentials from settings.toml (CircuitPython's recommended approach)
try:
    WIFI_SSID = os.getenv("WIFI_SSID")
    WIFI_PASSWORD = os.getenv("WIFI_PASSWORD")
    
    if not WIFI_SSID or not WIFI_PASSWORD:
        raise ValueError("WiFi credentials not found in settings.toml")
        
except Exception as e:
    print("WiFi settings are kept in settings.toml, please add them there!")
    print(f"Error: {e}")
    raise

# List of image URLs (must be direct links to image files)
IMAGE_URLS = [
    "https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/bmp/DSC07557.bmp",
    "https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/bmp/IMG_2144.bmp",
    "https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/bmp/IMG_2391.bmp",
    "https://raw.githubusercontent.com/lisheld/MatrixPortalThings/refs/heads/main/bmp/IMG_2590.bmp",
]

# Display cycle time in seconds (start with 10 seconds for testing)
CYCLE_TIME = 10  # Change to 300 (5 minutes) once working

# DITHERING CONTROL - Set to False to disable all temporal dithering
ENABLE_DITHERING = True  # Change to False to turn off dithering completely

# COLOR ACCURACY SETTINGS (when dithering is off)
IMPROVE_STATIC_COLORS = True  # Enhance palette colors for better accuracy when dithering is off

# VERSION CHECK - This should print if you're running the updated code
print("ADAPTIVE DITHERING VERSION 2.2 - MAXIMUM SPEED (EVERY FRAME UPDATE)")

class PhotoDisplay:
    def __init__(self):
        print("Initializing MatrixPortal...")
        # Initialize matrix display with 4-bit for temporal dithering
        self.matrix = Matrix(width=64, height=64, bit_depth=4)
        self.display = self.matrix.display
        
        # Keep auto-refresh on for smoother operation
        self.display.auto_refresh = True
        print("Matrix display initialized with temporal dithering")
        
        # Temporal dithering variables
        self.dither_frame = 0
        self.dither_patterns = {
            # Pattern definitions: (frame0, frame1, frame2, frame3)
            # Each represents which brightness offset to use
            'light': (0, 1, 0, 1),    # ABAB - 50/50 mix - for high contrast images
            'medium': (0, 0, 0, 1),   # AAAB - 75/25 mix - for medium range images
            'heavy': (0, 1, 1, 1),    # ABBB - 25/75 mix - for low contrast images
        }
        self.current_bitmap_data = None
        self.current_group = None
        self.current_dither_pattern = 'medium'  # Default pattern
        
        # Timing variables
        self.last_image_time = None
        # Remove dithering timing - now updates every frame
        
        # Show a test pattern first
        self.show_test_pattern()
        
        # Connect to WiFi
        self.connect_wifi()
        
        # Setup HTTP requests
        pool = socketpool.SocketPool(wifi.radio)
        context = ssl.create_default_context()
        self.requests = adafruit_requests.Session(pool, context)
        
        self.current_image_index = 0
        
        print("Initialization complete!")
        
    def show_test_pattern(self):
        """Show a simple test pattern to verify display works"""
        print("Showing test pattern...")
        try:
            import terminalio
            from adafruit_display_text import label
            
            # Create a simple text display
            text = "LOADING..."
            text_area = label.Label(terminalio.FONT, text=text, color=0xFF0000)
            text_area.x = 2
            text_area.y = 32
            
            group = displayio.Group()
            group.append(text_area)
            self.display.root_group = group
            self.current_group = group
            print("Test pattern displayed")
            
            time.sleep(2)  # Show for 2 seconds
            
        except Exception as e:
            print(f"Could not show test pattern: {e}")
        
    def connect_wifi(self):
        print("Connecting to WiFi...")
        try:
            wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
            print(f"Connected to {WIFI_SSID}")
            print(f"IP: {wifi.radio.ipv4_address}")
        except Exception as e:
            print(f"WiFi connection failed: {e}")
            raise
    
    def analyze_color_range(self, bitmap, palette, sample_size=100):
        """
        Analyze the color range of an image to determine appropriate dithering pattern.
        Returns 'light', 'medium', or 'heavy' based on color distribution.
        """
        print("Analyzing image color range...")
        try:
            # Check if palette exists
            if palette is None:
                print("ERROR: Palette is None, using medium dithering")
                return 'medium'
            
            # Test if we can actually access palette data
            try:
                test_color = palette[0]
                print(f"Palette access OK - first color: 0x{test_color:06X}")
            except Exception as pe:
                print(f"ERROR: Cannot access palette data ({pe}), using medium dithering")
                return 'medium'
            
            # Sample pixels from the bitmap to analyze color distribution
            width = bitmap.width
            height = bitmap.height
            
            # Calculate step size for sampling
            step_x = max(1, width // int(sample_size ** 0.5))
            step_y = max(1, height // int(sample_size ** 0.5))
            
            color_frequencies = {}
            brightness_values = []
            palette_colors_found = set()
            
            # Sample pixels across the image
            pixel_count = 0
            error_count = 0
            
            for y in range(0, height, step_y):
                for x in range(0, width, step_x):
                    try:
                        # Get pixel value (palette index)
                        pixel_index = bitmap[x, y]
                        pixel_count += 1
                        
                        # Count color frequency
                        color_frequencies[pixel_index] = color_frequencies.get(pixel_index, 0) + 1
                        palette_colors_found.add(pixel_index)
                        
                        # Get actual color from palette and calculate brightness
                        try:
                            color = palette[pixel_index]
                            # Calculate perceived brightness (luminance formula)
                            r = (color >> 16) & 0xFF
                            g = (color >> 8) & 0xFF
                            b = color & 0xFF
                            brightness = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                            brightness_values.append(brightness)
                        except Exception:
                            error_count += 1
                            continue
                            
                    except Exception:
                        error_count += 1
                        continue
            
            print(f"Analyzed {pixel_count} pixels ({len(brightness_values)} valid)")
            
            if not brightness_values:
                print("ERROR: Could not analyze any colors, using medium dithering")
                return 'medium'
            
            # Calculate statistics
            min_brightness = min(brightness_values)
            max_brightness = max(brightness_values)
            brightness_range = max_brightness - min_brightness
            avg_brightness = sum(brightness_values) / len(brightness_values)
            
            # Count unique colors used
            unique_colors = len(color_frequencies)
            max_palette_index = max(palette_colors_found) if palette_colors_found else 0
            
            # Estimate total palette size based on maximum index found + some buffer
            estimated_palette_size = min(256, max_palette_index + 50)  
            color_usage_ratio = unique_colors / estimated_palette_size if estimated_palette_size > 0 else 0
            
            print(f"Brightness range: {brightness_range:.3f}, Colors: {unique_colors}, Usage: {color_usage_ratio:.1%}")
            
            # Determine dithering pattern based on analysis
            if brightness_range > 0.6:  # High contrast
                pattern = 'light'
                reason = f"high contrast ({brightness_range:.3f})"
            elif brightness_range < 0.25:  # Low contrast
                pattern = 'heavy'
                reason = f"low contrast ({brightness_range:.3f})"
            else:  # Medium contrast
                pattern = 'medium'
                reason = f"medium contrast ({brightness_range:.3f})"
            
            # Also consider color diversity
            if color_usage_ratio < 0.15 and pattern != 'heavy':
                pattern = 'heavy'
                reason += ", limited colors"
            elif color_usage_ratio > 0.4 and pattern != 'light':
                pattern = 'light'
                reason += ", diverse colors"
            
            # Additional check: if very few unique colors, use heavy dithering
            if unique_colors < 20:
                pattern = 'heavy'
                reason = f"few colors ({unique_colors})"
            elif unique_colors > 100:
                pattern = 'light'
                reason = f"many colors ({unique_colors})"
            
            print(f"Selected pattern: {pattern} ({reason})")
            return pattern
            
        except Exception as e:
            print(f"Analysis error: {e}")
            return 'medium'  # Default fallback
    
    def enhance_palette_for_leds(self, original_palette):
        """
        Enhance palette colors for better LED display when temporal dithering is off.
        Applies gamma correction and color optimization for 4-bit display.
        """
        if not IMPROVE_STATIC_COLORS or original_palette is None:
            return original_palette
            
        try:
            print("  - Enhancing palette for LED display")
            
            # Probe to find the actual palette size
            max_valid_index = 0
            for i in range(256):
                try:
                    test_color = original_palette[i]
                    max_valid_index = i
                except (IndexError, TypeError):
                    break
            
            palette_size = max_valid_index + 1
            enhanced_palette = displayio.Palette(palette_size)
            
            # LED display characteristics
            gamma = 2.2  # Typical LED gamma
            brightness_boost = 1.1  # Slight brightness increase
            saturation_boost = 1.15  # Enhance saturation for LEDs
            
            for i in range(palette_size):
                try:
                    color = original_palette[i]
                    
                    # Extract RGB components
                    r = (color >> 16) & 0xFF
                    g = (color >> 8) & 0xFF
                    b = color & 0xFF
                    
                    # Convert to 0-1 range
                    r_norm = r / 255.0
                    g_norm = g / 255.0
                    b_norm = b / 255.0
                    
                    # Apply gamma correction for LED displays
                    r_gamma = pow(r_norm, 1.0/gamma)
                    g_gamma = pow(g_norm, 1.0/gamma)
                    b_gamma = pow(b_norm, 1.0/gamma)
                    
                    # Apply brightness boost
                    r_bright = min(1.0, r_gamma * brightness_boost)
                    g_bright = min(1.0, g_gamma * brightness_boost)
                    b_bright = min(1.0, b_gamma * brightness_boost)
                    
                    # Enhance saturation for more vivid LED colors
                    # Convert to HSV-like adjustment
                    max_rgb = max(r_bright, g_bright, b_bright)
                    min_rgb = min(r_bright, g_bright, b_bright)
                    
                    if max_rgb > min_rgb:  # Only enhance if there's color
                        # Increase the difference between max and min (saturation)
                        mid_point = (max_rgb + min_rgb) / 2
                        
                        r_sat = mid_point + (r_bright - mid_point) * saturation_boost
                        g_sat = mid_point + (g_bright - mid_point) * saturation_boost
                        b_sat = mid_point + (b_bright - mid_point) * saturation_boost
                        
                        # Clamp to valid range
                        r_final = max(0.0, min(1.0, r_sat))
                        g_final = max(0.0, min(1.0, g_sat))
                        b_final = max(0.0, min(1.0, b_sat))
                    else:
                        # Grayscale colors - just use brightness adjusted values
                        r_final = r_bright
                        g_final = g_bright
                        b_final = b_bright
                    
                    # Quantize to 4-bit levels (16 levels per channel)
                    # This matches the 4-bit display depth
                    r_4bit = round(r_final * 15) / 15
                    g_4bit = round(g_final * 15) / 15
                    b_4bit = round(b_final * 15) / 15
                    
                    # Convert back to 8-bit for palette storage
                    r_out = int(r_4bit * 255)
                    g_out = int(g_4bit * 255)
                    b_out = int(b_4bit * 255)
                    
                    enhanced_palette[i] = (r_out << 16) | (g_out << 8) | b_out
                    
                except Exception as e:
                    # If enhancement fails for a color, use original
                    try:
                        enhanced_palette[i] = original_palette[i]
                    except:
                        break
            
            print(f"  - Enhanced {palette_size} colors with gamma correction and LED optimization")
            return enhanced_palette
            
        except Exception as e:
            print(f"  - Color enhancement failed ({e}), using original palette")
            return original_palette
    
    def download_and_display_image(self, url):
        print(f"Downloading: {url}")
        try:
            # Download image
            print("Making HTTP request...")
            response = self.requests.get(url)
            print(f"Response status: {response.status_code}")
            print(f"Content length: {len(response.content)}")
            
            if response.status_code == 200:
                print("Processing image data directly from memory...")
                
                # Process directly from memory
                image_data = response.content
                response.close()
                
                # Display image from memory
                self.display_image_from_data(image_data)
                    
            else:
                print(f"Failed to download image: {response.status_code}")
                response.close()
                
        except Exception as e:
            print(f"Error downloading image: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
        
        # Force garbage collection
        gc.collect()
        print("Garbage collection completed")
    
    def display_image_from_data(self, image_data):
        """Display BMP image with adaptive temporal dithering for better colors"""
        try:
            print(f"Processing image data: {len(image_data)} bytes")
            
            # Create a BytesIO-like object for adafruit_imageload
            image_file = io.BytesIO(image_data)
            
            # Load image from memory
            print("Loading bitmap from memory...")
            bitmap, palette = adafruit_imageload.load(image_file)
            print(f"Bitmap loaded: {bitmap.width}x{bitmap.height}")
            
            # Check if we have a real palette or a ColorConverter
            palette_type = type(palette).__name__
            print(f"Pixel shader type: {palette_type}")
            
            # More detailed debugging
            print(f"Palette object: {palette}")
            print(f"Has __len__: {hasattr(palette, '__len__')}")
            
            # Check if it's a CircuitPython Palette object
            is_palette = palette_type == 'Palette' or 'Palette' in str(type(palette))
            
            print(f"Palette debugging - palette exists: {palette is not None}")
            
            if is_palette:
                print("✓ Valid CircuitPython Palette found")
                
                if ENABLE_DITHERING:
                    print("  - Analyzing for adaptive dithering")
                    # Analyze the image to determine optimal dithering pattern
                    self.current_dither_pattern = self.analyze_color_range(bitmap, palette)
                    print(f"  - Using dithering pattern: {self.current_dither_pattern}")
                    
                    self.current_bitmap_data = (bitmap, palette)
                    dithering_enabled = True
                else:
                    print("  - Dithering disabled by ENABLE_DITHERING setting")
                    self.current_bitmap_data = None
                    self.current_dither_pattern = 'medium'
                    dithering_enabled = False
            else:
                print("✗ No valid palette found - dithering disabled")
                print(f"  Palette type: {type(palette)}")
                print(f"  Palette dir: {[attr for attr in dir(palette) if not attr.startswith('_')]}")
                self.current_bitmap_data = None
                self.current_dither_pattern = 'medium'  # Reset to default
                dithering_enabled = False
            
            # Create initial sprite with palette/color converter
            sprite = displayio.TileGrid(bitmap, pixel_shader=palette)
            
            # Create new group
            print("Creating display group...")
            group = displayio.Group()
            group.append(sprite)
            
            # Update display
            self.display.root_group = group
            self.current_group = group
            
            # Reset dither frame
            self.dither_frame = 0
            
            if dithering_enabled:
                print(f"Image displayed with adaptive temporal dithering (pattern: {self.current_dither_pattern})!")
            else:
                if ENABLE_DITHERING:
                    print("Image displayed (24-bit direct color - temporal dithering disabled - no palette)")
                else:
                    print("Image displayed (temporal dithering disabled by user setting)")
            
        except Exception as e:
            print(f"Error displaying image from data: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            
    def create_dithered_palette(self, original_palette, brightness_offset=0):
        """Create a dithered version of the palette"""
        if original_palette is None:
            return None
            
        try:
            # Test palette access first
            try:
                test_color = original_palette[0]
            except Exception as pe:
                print(f"Cannot access original palette: {pe}")
                return original_palette
            
            # For CircuitPython Palette objects, determine the actual size by probing
            # Most BMPs use 256-color palettes, but let's find the actual used range
            max_valid_index = 0
            
            # Probe to find the highest valid palette index
            for i in range(256):  # Standard 8-bit palette max
                try:
                    test_color = original_palette[i]
                    max_valid_index = i
                except (IndexError, TypeError):
                    break
            
            palette_size = max_valid_index + 1
            # Reduced debug output for speed
            if palette_size <= 16:
                print(f"  Creating dithered palette with {palette_size} colors (small palette)")
            
            # Create new palette with detected size
            dithered_palette = displayio.Palette(palette_size)
            
            # Copy and modify colors
            for i in range(palette_size):
                try:
                    color = original_palette[i]
                    
                    # Extract RGB components
                    r = (color >> 16) & 0xFF
                    g = (color >> 8) & 0xFF
                    b = color & 0xFF
                    
                    # Apply brightness offset for dithering
                    # Adjust offset magnitude based on dithering pattern
                    if self.current_dither_pattern == 'light':
                        offset = brightness_offset * 3  # Subtle dithering for high contrast
                    elif self.current_dither_pattern == 'heavy':
                        offset = brightness_offset * 12  # Strong dithering for low contrast
                    else:  # medium
                        offset = brightness_offset * 6  # Default dithering
                    
                    r = max(0, min(255, r + offset))
                    g = max(0, min(255, g + offset))
                    b = max(0, min(255, b + offset))
                    
                    dithered_palette[i] = (r << 16) | (g << 8) | b
                    
                except (IndexError, TypeError) as e:
                    print(f"  Error at palette index {i}: {e}")
                    break
                    
            return dithered_palette
            
        except Exception as e:
            print(f"Error creating dithered palette: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
            return original_palette
    
    def update_dither_frame(self):
        """Update the dithering frame counter and refresh display if needed"""
        # Only do temporal dithering if we have palette data
        if self.current_bitmap_data is None or self.current_group is None:
            return
            
        try:
            self.dither_frame = (self.dither_frame + 1) % 4
            
            # Use the current dithering pattern determined by image analysis
            pattern = self.dither_patterns[self.current_dither_pattern]
            brightness_offset = 1 if pattern[self.dither_frame] else -1
            
            # Get the current bitmap and original palette
            bitmap, original_palette = self.current_bitmap_data
            
            # Check if palette exists and is accessible
            if original_palette is not None:
                # Create dithered palette
                dithered_palette = self.create_dithered_palette(original_palette, brightness_offset)
                
                if dithered_palette and len(self.current_group) > 0:
                    # Update the pixel shader of the current sprite
                    current_sprite = self.current_group[0]
                    if hasattr(current_sprite, 'pixel_shader'):
                        current_sprite.pixel_shader = dithered_palette
                    
        except Exception as e:
            print(f"Dithering update error: {e}")
            # Don't print full traceback for dithering errors to avoid spam

    def change_image(self):
        """Change to the next image"""
        # Get current image URL
        url = IMAGE_URLS[self.current_image_index]
        print(f"Processing image {self.current_image_index + 1}/{len(IMAGE_URLS)}: {url}")
        
        # Download and display
        self.download_and_display_image(url)
        
        # Move to next image
        self.current_image_index = (self.current_image_index + 1) % len(IMAGE_URLS)
        
        # Record time
        self.last_image_time = time.monotonic()
        
        if ENABLE_DITHERING:
            print(f"Image displayed with {self.current_dither_pattern} dithering. Next change in {CYCLE_TIME} seconds...")
        else:
            print(f"Image displayed (no dithering). Next change in {CYCLE_TIME} seconds...")
    
    def run(self):
        print("Starting photo slideshow with adaptive temporal dithering...")
        
        # Show first image immediately
        self.change_image()
        
        while True:
            try:
                current_time = time.monotonic()
                
                # Update dithering on EVERY loop iteration (only if enabled)
                if ENABLE_DITHERING:
                    self.update_dither_frame()
                
                # Check if it's time to change images
                if self.last_image_time and (current_time - self.last_image_time >= CYCLE_TIME):
                    self.change_image()
                
                # No sleep - run as fast as possible!
                
            except KeyboardInterrupt:
                print("Slideshow stopped by user")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(1)  # Wait before retrying

# Create and run the photo display
if __name__ == "__main__":
    try:
        photo_display = PhotoDisplay()
        photo_display.run()
    except Exception as e:
        print(f"Main error: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        # Keep the device from restarting immediately
        while True:
            time.sleep(60)