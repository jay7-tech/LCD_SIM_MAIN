import time
import os
import threading
import math
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

# Import the hardware driver
try:
    from lcd_driver_pi import LCD_GC9A01
    HARDWARE_AVAILABLE = True
except ImportError:
    print("Hardware driver not found or dependencies missing (lgpio/spidev). Running in mock mode.")
    HARDWARE_AVAILABLE = False
    
# ----------------------------
# Configuration
# ----------------------------
ASSETS_DIR = Path(__file__).parent / "assets"
IDLE_FACE = "eyes"  # Default fallback

# ----------------------------
# Asset Loading
# ----------------------------
def load_frames(folder: Path) -> List[Image.Image]:
    if not folder.exists():
        return []
    frames = []
    # Sort by filename to ensure correct animation order
    for fp in sorted(folder.glob("*.png")):
        try:
            img = Image.open(fp).convert("RGB")
            frames.append(img)
        except Exception as e:
            print(f"Error loading {fp}: {e}")
    return frames

class PiLCDApp:
    def __init__(self):
        self.lcd = None
        if HARDWARE_AVAILABLE:
            try:
                self.lcd = LCD_GC9A01()
                print("LCD Initialized.")
            except Exception as e:
                print(f"Failed to init LCD: {e}")
        
        self.running = True
        self.current_anim_name = "idle_center"
        self.anim_queue = [] # (name, loop, fps, fallback)
        
        # Load Assets
        print("Loading assets...")
        self.anims: Dict[str, List[Image.Image]] = {}
        for folder in ASSETS_DIR.iterdir():
            if folder.is_dir():
                self.anims[folder.name] = load_frames(folder)
                print(f"Loaded {folder.name}: {len(self.anims[folder.name])} frames")
                
        # State
        self.mode = "IDLE" # IDLE, ANIMATING
        self.idle_variant = "center"
        self.last_idle_move = time.time()
        
        self.current_frames = self.anims.get("idle_center", [])
        self.frame_idx = 0
        self.fps_ms = 100 # Default speed
        self.loop = True
        self.fallback_to_idle = False
        
        # Start Input Thread
        self.input_thread = threading.Thread(target=self.input_loop, daemon=True)
        self.input_thread.start()

    def input_loop(self):
        print("\n--- Command Interface ---")
        print("Type 'love', 'sleep', 'happy', 'angry' etc. to trigger animations.")
        print("Type 'quit' to exit.")
        while self.running:
            try:
                cmd = input("Command> ").strip().lower()
                if cmd == "quit":
                    self.running = False
                    break
                self.handle_command(cmd)
            except EOFError:
                break
                
    def handle_command(self, cmd):
        # Map simple commands to folder names
        # Logic similar to lcd_simulator.py
        
        mapping = {
            "love": "love",
            "sleep": "sleep",
            "happy": "laugh",
            "laugh": "laugh",
            "angry": "angry",
            "hate": "hate",
            "blush": "blush",
            "focus": "focus_on",
            "unfocus": "focus_off",
            "phone": "phone",
            "proximity": "proximity",
            "silence": "silence",
            "idle": "idle_center"
        }
        
        anim_name = mapping.get(cmd, cmd) # Default to direct name
        
        if anim_name in self.anims:
            is_idle = "idle" in anim_name
            loop = is_idle
            fallback = not is_idle
            
            self.play_animation(anim_name, loop=loop, fps_ms=90, fallback_to_idle=fallback)
        else:
            print(f"Animation '{anim_name}' not found.")

    def play_animation(self, name, loop=False, fps_ms=100, fallback_to_idle=True):
        if name not in self.anims:
            print(f"Missing animation: {name}")
            return
            
        self.current_frames = self.anims[name]
        self.frame_idx = 0
        self.fps_ms = fps_ms
        self.loop = loop
        self.fallback_to_idle = fallback_to_idle
        self.mode = "ANIMATING" if not loop else "IDLE"
        
        # If it's an idle state, update tracker
        if "idle" in name:
            self.idle_variant = name.replace("idle_", "")
            self.last_idle_move = time.time()

    def run(self):
        print("Starting Main Loop...")
        try:
            while self.running:
                start_time = time.time()
                
                # Logic: Draw current frame
                if self.current_frames:
                    if self.frame_idx < len(self.current_frames):
                        frame = self.current_frames[self.frame_idx]
                        if self.lcd:
                            self.lcd.display_image(frame)
                        
                        self.frame_idx += 1
                    else:
                        # End of animation
                        if self.loop:
                            self.frame_idx = 0
                        else:
                            if self.fallback_to_idle:
                                self.play_animation(f"idle_{self.idle_variant}", loop=True)
                            else:
                                # Stay on last frame? or restart?
                                # for now restart if no fallback
                                self.frame_idx = 0 

                # Idle Drift Logic
                # Every ~6 seconds, look around
                if self.mode == "IDLE":
                    if time.time() - self.last_idle_move > 6.0:
                        # simple random shift
                        next_state = "idle_left" if self.idle_variant == "center" else "idle_center"
                        if self.idle_variant == "left": next_state = "idle_right"
                        
                        # Play loop=False for look-around, then back to center?
                        # Actually lcd_simulator used specific logic. simple is fine here.
                        self.play_animation(next_state, loop=False, fps_ms=120, fallback_to_idle=True)
                        self.idle_variant = next_state.replace("idle_", "")
                        self.last_idle_move = time.time()

                # FPS Control
                elapsed = (time.time() - start_time) * 1000
                sleep_ms = max(0, self.fps_ms - elapsed)
                time.sleep(sleep_ms / 1000.0)
                
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            if self.lcd:
                self.lcd.close()

if __name__ == "__main__":
    app = PiLCDApp()
    app.run()
