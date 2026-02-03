import time
import spidev
import lgpio
from PIL import Image
import math
import numpy as np

# Pin Definitions (BCM)
PIN_DC = 25
PIN_RST = 24
PIN_BL = 17
PIN_CS = 8  # SPI0 CE0

# SPI Configuration
SPI_BUS = 0
SPI_DEVICE = 0
SPI_SPEED_HZ = 40000000 # ST7735 usually handles up to ~30-40MHz

class LCD_ST7735:
    def __init__(self, width=128, height=128, rotation=90):
        self.width = width
        self.height = height
        self.rotation = rotation
        
        # ST7735 1.44" often has an offset because the controller is 132x162
        # Adjust these if the image is shifted
        self.offset_x = 2
        self.offset_y = 3
        
        # Initialize GPIO
        self.h = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.h, PIN_DC, 0)
        lgpio.gpio_claim_output(self.h, PIN_RST, 1)
        
        try:
            lgpio.gpio_claim_output(self.h, PIN_BL, 1) # Backlight ON
        except:
            pass 
            
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
        elif isinstance(data, (bytes, bytearray)):
            self.spi.writebytes(data)
        else:
            self.spi.writebytes([data])

    def init_display(self):
        """Initialize ST7735 display"""
        # SWRESET
        self.write_cmd(0x01)
        time.sleep(0.150)
        
        # SLPOUT
        self.write_cmd(0x11)
        time.sleep(0.200)
        
        # COLMOD - 16-bit color
        self.write_cmd(0x3A)
        self.write_data(0x05) 
        
        # MADCTL - Memory Access Control
        # Standard: BGR (0x08) or MV/MX/MY variants. 
        # We use standard 0x08 (BGR) and rely on software rotation.
        self.write_cmd(0x36)
        self.write_data(0xC8) # default
        
        # GAMSET (Gamma) - Default curve 1
        self.write_cmd(0x26)
        self.write_data(0x01)
        
        # DISPON
        self.write_cmd(0x29)
        time.sleep(0.100)

    def set_window(self, x_start, y_start, x_end, y_end):
        # Adjust for offset
        x_start += self.offset_x
        x_end += self.offset_x
        y_start += self.offset_y
        y_end += self.offset_y
        
        # CASET
        self.write_cmd(0x2A)
        self.write_data([x_start >> 8, x_start & 0xFF, x_end >> 8, x_end & 0xFF])
        
        # RASET
        self.write_cmd(0x2B)
        self.write_data([y_start >> 8, y_start & 0xFF, y_end >> 8, y_end & 0xFF])
        
        # RAMWR
        self.write_cmd(0x2C)

    def display_image(self, image):
        """Send PIL Image to display"""
        if image.mode != "RGB":
            image = image.convert("RGB")
        
        # Software Rotation
        if self.rotation != 0:
            image = image.rotate(self.rotation)

        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
            
        img_data = np.array(image, dtype=np.uint16)
        
        # RGB888 -> RGB565
        r = (img_data[:, :, 0] >> 3).astype(np.uint16)
        g = (img_data[:, :, 1] >> 2).astype(np.uint16)
        b = (img_data[:, :, 2] >> 3).astype(np.uint16)
        
        rgb565 = (r << 11) | (g << 5) | b
        
        rgb565_high = (rgb565 >> 8).astype(np.uint8)
        rgb565_low = (rgb565 & 0xFF).astype(np.uint8)
        
        packed = np.dstack((rgb565_high, rgb565_low)).flatten()
        
        self.set_window(0, 0, self.width - 1, self.height - 1)
        
        lgpio.gpio_write(self.h, PIN_DC, 1)
        
        # Chunk transfer
        data_bytes = packed.tobytes()
        chunk_size = 4096
        for i in range(0, len(data_bytes), chunk_size):
            self.spi.writebytes(data_bytes[i:i+chunk_size])

    def close(self):
        self.spi.close()
        lgpio.gpio_write(self.h, PIN_BL, 0)
        lgpio.gpiochip_close(self.h)

if __name__ == "__main__":
    disp = LCD_ST7735()
    img = Image.new("RGB", (128, 128), (255, 0, 0))
    disp.display_image(img)
    time.sleep(1)
    disp.close()
