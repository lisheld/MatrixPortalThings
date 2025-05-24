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
            'light': (0, 1, 0, 1),  # ABAB - 50/50 mix
            'medium': (0, 0, 0, 1), # AAAB - 75/25 mix  
            'heavy': (0, 1, 1, 1),  # ABBB - 25/75 mix
        }
        self.current_bitmap_data = None
        self.current_group = None
        
        # Timing variables
        self.last_image_time = None
        self.last_dither_time = 0
        self.dither_interval = 1.0 / 15.0  # 15 Hz dithering (4 frames at 60fps)
        
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
        """Display BMP image with temporal dithering for better colors"""
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
            
            # Handle different pixel shader types
            if hasattr(palette, '__len__'):
                print(f"Palette colors: {len(palette)}")
                # Store bitmap data for dithering (only if we have a real palette)
                self.current_bitmap_data = (bitmap, palette)
            else:
                print("Using ColorConverter (24-bit direct color)")
                # For ColorConverter, we can't do palette-based dithering
                self.current_bitmap_data = None
            
            # Create initial sprite with original palette/color converter
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
            
            if self.current_bitmap_data is None:
                print("Image displayed (24-bit direct color - temporal dithering disabled)")
            else:
                print("Image displayed with temporal dithering enabled!")
            
        except Exception as e:
            print(f"Error displaying image from data: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
    
    def create_dithered_palette(self, original_palette, brightness_offset=0):
        """Create a dithered version of the palette"""
        if not original_palette:
            return None
            
        try:
            dithered_palette = displayio.Palette(len(original_palette))
            
            for i in range(len(original_palette)):
                color = original_palette[i]
                
                # Extract RGB components
                r = (color >> 16) & 0xFF
                g = (color >> 8) & 0xFF
                b = color & 0xFF
                
                # Apply brightness offset for dithering
                # Smaller offset for subtler dithering
                offset = brightness_offset * 4  # Scale the offset
                r = max(0, min(255, r + offset))
                g = max(0, min(255, g + offset))
                b = max(0, min(255, b + offset))
                
                dithered_palette[i] = (r << 16) | (g << 8) | b
                
            return dithered_palette
            
        except Exception as e:
            print(f"Error creating dithered palette: {e}")
            return original_palette
    
    def update_dither_frame(self):
        """Update the dithering frame counter and refresh display if needed"""
        # Only do temporal dithering if we have palette data
        if self.current_bitmap_data is None or self.current_group is None:
            return
            
        try:
            self.dither_frame = (self.dither_frame + 1) % 4
            
            # Determine brightness offset based on dither pattern
            # Using 'light' pattern (ABAB) for now
            pattern = self.dither_patterns['light']
            brightness_offset = 1 if pattern[self.dither_frame] else -1
            
            # Get the current bitmap and original palette
            bitmap, original_palette = self.current_bitmap_data
            
            # Only proceed if we have a real palette (not ColorConverter)
            if hasattr(original_palette, '__len__'):
                # Create dithered palette
                dithered_palette = self.create_dithered_palette(original_palette, brightness_offset)
                
                if dithered_palette and len(self.current_group) > 0:
                    # Update the pixel shader of the current sprite
                    current_sprite = self.current_group[0]
                    if hasattr(current_sprite, 'pixel_shader'):
                        current_sprite.pixel_shader = dithered_palette
                    
        except Exception as e:
            print(f"Dithering update error: {e}")

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
        
        print(f"Image displayed. Next change in {CYCLE_TIME} seconds...")
    
    def run(self):
        print("Starting photo slideshow with temporal dithering...")
        
        # Show first image immediately
        self.change_image()
        
        while True:
            try:
                current_time = time.monotonic()
                
                # Handle dithering updates
                if current_time - self.last_dither_time >= self.dither_interval:
                    self.update_dither_frame()
                    self.last_dither_time = current_time
                
                # Check if it's time to change images
                if self.last_image_time and (current_time - self.last_image_time >= CYCLE_TIME):
                    self.change_image()
                
                # Small sleep to prevent busy waiting
                time.sleep(0.01)
                
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