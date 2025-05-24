# MatrixPortal Photo Display

A CircuitPython project that displays a slideshow of images on an Adafruit MatrixPortal (64x64 LED matrix display).

## Hardware Required
- Adafruit MatrixPortal M4
- 64x64 RGB LED Matrix Panel
- Power supply for the LED matrix

## Setup

1. **Install CircuitPython libraries** on your MatrixPortal:
   - `adafruit_matrixportal`
   - `adafruit_requests`
   - `adafruit_imageload`
   - `adafruit_display_text`

2. **Configure WiFi credentials**:
   - Copy `settings_template.toml` to `settings.toml`
   - Edit `settings.toml` with your actual WiFi network name and password

3. **Add image URLs**:
   - Edit the `IMAGE_URLS` list in `circuitpy.py`
   - Add direct links to BMP image files (64x64 pixels recommended)

4. **Upload to MatrixPortal**:
   - Copy `circuitpy.py` and `settings.toml` to the CIRCUITPY drive
   - The display will start automatically

## Features
- Automatic WiFi connection
- Downloads and displays images from URLs
- Smooth transitions between images
- Configurable display cycle time
- Memory management and garbage collection

## Configuration
- `CYCLE_TIME`: Time in seconds between image changes (default: 10 seconds)
- `IMAGE_URLS`: List of direct image URLs to display
- WiFi credentials stored in `settings.toml` (CircuitPython's recommended approach)

## Image Requirements
- Format: BMP
- Size: 64x64 pixels (recommended)
- Direct download links (not web page URLs)

## Troubleshooting
- Check serial output for debug information
- Ensure image URLs are direct links to BMP files
- Verify WiFi credentials in `settings.toml`
- Monitor memory usage if images fail to load 