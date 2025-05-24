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
        # Initialize matrix display with 4-bit color depth
        self.matrix = Matrix(width=64, height=64, bit_depth=4)
        self.display = self.matrix.display
        
        # Keep auto-refresh on for smoother operation
        self.display.auto_refresh = True
        print("Matrix display initialized")
        
        # Show a test pattern first
        self.show_test_pattern()
        
        # Connect to WiFi
        self.connect_wifi()
        
        # Setup HTTP requests
        pool = socketpool.SocketPool(wifi.radio)
        context = ssl.create_default_context()
        self.requests = adafruit_requests.Session(pool, context)
        
        self.current_image_index = 0
        self.current_group = None  # Keep track of current display group
        self.dither_frame = 0  # Track dithering frame
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
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
        print(f"Connected to {WIFI_SSID}")
        print(f"IP: {wifi.radio.ipv4_address}")
    
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
                
                # Instead of saving to file, process directly from memory
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
        """Display BMP image with optimized color handling and dithering"""
        try:
            print(f"Processing image data: {len(image_data)} bytes")
            
            # Brief black screen for smooth transition (shorter duration)
            print("Showing transition screen...")
            self.show_black_screen()
            time.sleep(0.05)  # Shorter black screen to maintain colors
            
            # Create a BytesIO-like object for adafruit_imageload
            import io
            image_file = io.BytesIO(image_data)
            
            # Load image from memory
            print("Loading bitmap from memory...")
            bitmap, palette = adafruit_imageload.load(image_file)
            print(f"Bitmap loaded: {bitmap.width}x{bitmap.height}")
            print(f"Palette colors: {len(palette) if palette else 'No palette'}")
            
            # Create sprite with proper color handling
            sprite = displayio.TileGrid(bitmap, pixel_shader=palette)
            
            # Create new group
            print("Creating display group...")
            group = displayio.Group()
            group.append(sprite)
            
            # Update display
            self.display.root_group = group
            self.current_group = group
            
            print("Image displayed successfully!")
            
        except Exception as e:
            print(f"Error displaying image from data: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
    
    def show_black_screen(self):
        """Show a black screen for smooth transitions"""
        try:
            # Create a black rectangle covering the entire display
            import vectorio
            
            black_rect = vectorio.Rectangle(
                pixel_shader=displayio.Palette(1),
                width=64,
                height=64,
                x=0,
                y=0
            )
            # Make the palette color black
            black_rect.pixel_shader[0] = 0x000000
            
            group = displayio.Group()
            group.append(black_rect)
            self.display.root_group = group
            
        except Exception as e:
            print(f"Could not show black screen: {e}")
            # Fallback - just clear display
            self.display.root_group = displayio.Group()

    def display_image(self, filename):
        try:
            print(f"Loading image file: {filename}")
            
            # Check file size
            import os
            try:
                file_size = os.stat(filename)[6]
                print(f"File size: {file_size} bytes")
            except:
                print("Could not get file size")
            
            # Clear current display
            print("Clearing display...")
            self.display.root_group = displayio.Group()
            
            # Load image
            print("Loading bitmap...")
            bitmap, palette = adafruit_imageload.load(filename)
            print(f"Bitmap loaded: {bitmap.width}x{bitmap.height}")
            
            # Create sprite
            print("Creating sprite...")
            sprite = displayio.TileGrid(bitmap, pixel_shader=palette)
            
            # Add to display group
            print("Adding to display group...")
            group = displayio.Group()
            group.append(sprite)
            self.display.root_group = group
            
            print("Image displayed successfully!")
            
        except Exception as e:
            print(f"Error displaying image: {e}")
            import traceback
            traceback.print_exception(type(e), e, e.__traceback__)
    
    def run(self):
        print("Starting photo slideshow...")
        
        while True:
            # Get current image URL
            url = IMAGE_URLS[self.current_image_index]
            print(f"Processing image {self.current_image_index + 1}/{len(IMAGE_URLS)}: {url}")
            
            # Download and display
            self.download_and_display_image(url)
            
            # Move to next image
            self.current_image_index = (self.current_image_index + 1) % len(IMAGE_URLS)
            
            # Wait before next image
            print(f"Image displayed. Waiting {CYCLE_TIME} seconds before next image...")
            time.sleep(CYCLE_TIME)

# Create and run the photo display
if __name__ == "__main__":
    try:
        photo_display = PhotoDisplay()
        photo_display.run()
    except Exception as e:
        print(f"Main error: {e}")
        # Show error on display or restart