import time
import spidev
import lgpio
from PIL import Image
import math

# Pin Definitions (BCM)
PIN_DC = 25
PIN_RST = 24
PIN_BL = 17
PIN_CS = 8  # SPI0 CE0

# SPI Configuration
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 60000000  # 60MHz

class LCD_GC9A01:
    def __init__(self, width=240, height=240):
        self.width = width
        self.height = height
        
        # Initialize GPIO
        self.h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.h, PIN_DC, 0)
        lgpio.gpio_claim_output(self.h, PIN_RST, 1)
        
        # PWM for Backlight
        # lgpio supports PWM on Pi 5 directly
        try:
            lgpio.gpio_claim_output(self.h, PIN_BL, 1) # simple ON for now
            # TODO: Add PWM support if needed. For now just turn it on.
        except:
            pass # Might be already claimed
            
        # Initialize SPI
        self.spi = spidev.SpiDev()
        self.spi.open(SPI_BUS, SPI_DEVICE)
        self.spi.max_speed_hz = SPI_SPEED_HZ
        self.spi.mode = 0b00

        self.reset()
        self.init_display()

    def reset(self):
        """Hardware reset"""
        lgpio.gpio_write(self.h, PIN_RST, 1)
        time.sleep(0.01)
        lgpio.gpio_write(self.h, PIN_RST, 0)
        time.sleep(0.01)
        lgpio.gpio_write(self.h, PIN_RST, 1)
        time.sleep(0.120)

    def write_cmd(self, cmd):
        lgpio.gpio_write(self.h, PIN_DC, 0) # Command mode
        self.spi.writebytes([cmd])

    def write_data(self, data):
        lgpio.gpio_write(self.h, PIN_DC, 1) # Data mode
        if isinstance(data, list):
            self.spi.writebytes(data)
        else:
            self.spi.writebytes([data])

    def init_display(self):
        """Initialize GC9A01 display"""
        # Internal register enable
        self.write_cmd(0xFE)
        self.write_cmd(0xEF)
        
        self.write_cmd(0xB0)
        self.write_data(0xC0)
        
        self.write_cmd(0xB2)
        self.write_data(0x2F)
        
        self.write_cmd(0xB3)
        self.write_data(0x03)
        
        self.write_cmd(0xB6)
        self.write_data(0x19)
        
        self.write_cmd(0xB7)
        self.write_data(0x01)
        
        self.write_cmd(0xAC)
        self.write_data(0xCB)
        
        self.write_cmd(0xAB)
        self.write_data(0x0E)
        
        self.write_cmd(0xB4)
        self.write_data(0x04)
        
        self.write_cmd(0xA8)
        self.write_data(0x19)
        
        self.write_cmd(0x38) # IDLOFF
        self.write_cmd(0x23)
        
        self.write_cmd(0xE0)
        self.write_data([0x70, 0x07, 0x08, 0x09, 0x09, 0x05, 0x2A, 0x33, 0x41, 0x07, 0x13, 0x13, 0x29, 0x2F])
        
        self.write_cmd(0xE1)
        self.write_data([0x70, 0x09, 0x08, 0x08, 0x06, 0x06, 0x2A, 0x32, 0x40, 0x02, 0x12, 0x13, 0x28, 0x2E])
        
        self.write_cmd(0xF0)
        self.write_data([0x36, 0x09, 0x0C, 0x0B, 0x03, 0x04, 0x25, 0x33, 0x3F, 0x14, 0x14, 0x2F, 0x32])
        
        self.write_cmd(0xF1)
        self.write_data([0x3C, 0x09, 0x0C, 0x0B, 0x04, 0x03, 0x24, 0x33, 0x3E, 0x13, 0x14, 0x2D, 0x31])
        
        self.write_cmd(0xFE)
        self.write_cmd(0xFF)
        
        self.write_cmd(0x3A) # Pixel format
        self.write_data(0x05) # 16-bit color
        
        self.write_cmd(0x36) # Memory access control
        self.write_data(0x08) # BGR order
        
        self.write_cmd(0x35) # Tearing effect on
        self.write_data(0x00)
        
        self.write_cmd(0x11) # Sleep out
        time.sleep(0.120)
        
        self.write_cmd(0x29) # Display on
        self.write_cmd(0x2C) # RAM write

    def set_window(self, x_start, y_start, x_end, y_end):
        self.write_cmd(0x2A)
        self.write_data([x_start >> 8, x_start & 0xFF, x_end >> 8, x_end & 0xFF])
        
        self.write_cmd(0x2B)
        self.write_data([y_start >> 8, y_start & 0xFF, y_end >> 8, y_end & 0xFF])
        
        self.write_cmd(0x2C)

    def display_image(self, image):
        """Send PIL Image to display"""
        import numpy as np
        
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Resize if necessary
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
            
        # Convert to numpy array
        img_data = np.array(image, dtype=np.uint16)
        
        # RGB888 -> RGB565
        r = (img_data[:, :, 0] >> 3).astype(np.uint16)
        g = (img_data[:, :, 1] >> 2).astype(np.uint16)
        b = (img_data[:, :, 2] >> 3).astype(np.uint16)
        
        rgb565 = (r << 11) | (g << 5) | b
        
        # Breakdown to high/low bytes for SPI
        # GC9A01 expects Big Endian usually for 16-bit
        # Convert to bytes
        # spidev writebytes expects a list of integers or a bytes/bytearray object
        # tobytes() gives raw bytes. We need to ensure byte order.
        # usually SPI needs MSB first.
        # numpy is typically little endian on Pi?
        # Let's verify byte order manually: (high_byte, low_byte)
        
        rgb565_high = (rgb565 >> 8).astype(np.uint8)
        rgb565_low = (rgb565 & 0xFF).astype(np.uint8)
        
        # Stack them: [h, l, h, l...]
        # This is efficient interleaving
        packed = np.dstack((rgb565_high, rgb565_low)).flatten()
        
        self.set_window(0, 0, self.width - 1, self.height - 1)
        
        # DC=1 for data
        lgpio.gpio_write(self.h, PIN_DC, 1)
        
        # spidev accepts bytes object directly
        # Write in chunks if too large (4096 is common spidev buffer limit, but Python wrapper handles it usually)
        # However, specifically explicitly chunking is safer for large buffers on Pi
        data_bytes = packed.tobytes()
        chunk_size = 4096
        for i in range(0, len(data_bytes), chunk_size):
            self.spi.writebytes(data_bytes[i:i+chunk_size])

    def close(self):
        self.spi.close()
        lgpio.gpio_write(self.h, PIN_BL, 0)
        lgpio.gpiochip_close(self.h)

if __name__ == "__main__":
    # Test pattern
    disp = LCD_GC9A01()
    img = Image.new("RGB", (240, 240), (255, 0, 0)) # Red
    disp.display_image(img)
    time.sleep(1)
    img = Image.new("RGB", (240, 240), (0, 255, 0)) # Green
    disp.display_image(img)
    time.sleep(1)
    img = Image.new("RGB", (240, 240), (0, 0, 255)) # Blue
    disp.display_image(img)
    time.sleep(1)
    disp.close()
