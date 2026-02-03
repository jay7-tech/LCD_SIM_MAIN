import time
import os
import threading
import math
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image

# Import the hardware driver
try:
    from lcd_driver_pi import LCD_ST7735
    HARDWARE_AVAILABLE = True
except ImportError:
    print("Raspberry Pi hardware driver not found. Using Tkinter simulation.")
    HARDWARE_AVAILABLE = False

try:
    import tkinter as tk
    from PIL import ImageTk
except ImportError:
    tk = None

class TkinterDisplay:
    """Simulates the SPI Display using a Tkinter window"""
    def __init__(self, width=128, height=128, on_command=None):
        if not tk:
            self.root = None
            return
            
        self.root = tk.Tk()
        self.root.title("Pi LCD Simulator")
        
        # Main Layout
        container = tk.Frame(self.root)
        container.pack(fill="both", expand=True)
        
        # LCD Area
        self.width = width
        self.height = height
        self.canvas = tk.Canvas(container, width=width, height=height, bg="black", highlightthickness=0)
        self.canvas.pack(side="left", padx=10, pady=10)
        
        # Controls Area
        if on_command:
            controls = tk.Frame(container)
            controls.pack(side="right", fill="y", padx=10, pady=10)
            
            tk.Label(controls, text="Triggers", font=("Arial", 10, "bold")).pack(pady=(0, 5))
            
            cmds = ["Happy", "Sleep", "Love", "Angry", "Blush", "Focus", "Phone", "Silence"]
            for cmd in cmds:
                btn = tk.Button(controls, text=cmd, width=10, 
                                command=lambda c=cmd.lower(): on_command(c))
                btn.pack(pady=2)
                
            tk.Button(controls, text="Quit", width=10, bg="#ffcccc",
                      command=lambda: on_command("quit")).pack(pady=(10, 0))

        # Position window
        self.root.resizable(False, False)
        
        self.tk_img_ref = None
        
        # Start GUI update loop
        self.root.update()

    def display_image(self, image):
        if not self.root: return
        
        # Resize if needed
        if image.size != (self.width, self.height):
            image = image.resize((self.width, self.height))
            
        try:
            # Explicitly pass master to avoid "no default root" error if multiple threads/contexts exist
            self.tk_img_ref = ImageTk.PhotoImage(image, master=self.root)
            self.canvas.create_image(0, 0, image=self.tk_img_ref, anchor="nw")
            
            # Handle GUI events
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            print("Window closed. Stopping.")
            self.root = None
            
    def close(self):
        if self.root:
            try:
                self.root.destroy()
            except tk.TclError:
                pass
            self.root = None
    
# ----------------------------
# Configuration
# ----------------------------
ASSETS_DIR = Path(__file__).parent / "assets"
IDLE_FACE = "eyes"  # Default fallback

# ----------------------------
# Asset Loading
# ----------------------------
def load_frames(folder: Path, target_size: tuple) -> List[Image.Image]:
    if not folder.exists():
        return []
    frames = []
    # Sort by filename to ensure correct animation order
    for fp in sorted(folder.glob("*.png")):
        try:
            img = Image.open(fp).convert("RGB")
            if img.size != target_size:
                img = img.resize(target_size, Image.Resampling.LANCZOS)
            frames.append(img)
        except Exception as e:
            print(f"Error loading {fp}: {e}")
    return frames

class PiLCDApp:
    def __init__(self, initial_rotation=90):
        global HARDWARE_AVAILABLE
        self.target_size = (128, 128) # ST7735 Resolution
        
        self.lcd = None
        if HARDWARE_AVAILABLE:
            try:
                self.lcd = LCD_ST7735(rotation=initial_rotation)
                print(f"Hardware LCD Initialized (Rotation: {initial_rotation}).")
            except Exception as e:
                print(f"Failed to init Hardware LCD: {e}")
                HARDWARE_AVAILABLE = False # Fallback
        
        if not HARDWARE_AVAILABLE:
            # Init simulator
            if 'TkinterDisplay' in globals():
                # Pass handle_command as callback
                self.lcd = TkinterDisplay(width=self.target_size[0], height=self.target_size[1], on_command=self.handle_command)
                print("Simulation LCD Initialized.")
        
        self.running = True
        self.current_anim_name = "idle_center"
        self.anim_queue = [] # (name, loop, fps, fallback)
        
        # Load Assets
        print(f"Loading assets (target size {self.target_size})...")
        self.anims: Dict[str, List[Image.Image]] = {}
        for folder in ASSETS_DIR.iterdir():
            if folder.is_dir():
                self.anims[folder.name] = load_frames(folder, self.target_size)
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
        # Get list of simplified commands
        cmds = ["love", "sleep", "happy", "angry", "hate", "blush", "focus", "phone", "silence", "idle"]
        print(f"Available commands: {', '.join(cmds)}")
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--rot", type=int, default=90, help="Rotation: 0, 90, 180, 270")
    args = parser.parse_args()
    
    app = PiLCDApp(initial_rotation=args.rot)
    app.run()
