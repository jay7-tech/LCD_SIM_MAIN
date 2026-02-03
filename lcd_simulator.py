import re
import time
import math
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageTk
import threading
import os

try:
    import winsound
except ImportError:
    winsound = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

# ✅ idle face pattern
IDLE_FACE = "👁️-👁️"


# ----------------------------
# Neon / DJ-style colors (very saturated)
# ----------------------------
GLOW_COLORS = {
    "😂": (255, 220, 0),     # neon yellow
    "❤️": (255, 20, 80),     # neon pink/red
    "💤": (0, 180, 255),     # electric blue
    "🎯": (0, 255, 140),     # neon green
    "🧘": (0, 200, 255),     # cyan blue
    "📵": (255, 40, 40),     # alarm red
    "🫸": (255, 120, 0),     # neon orange
    "😔": (180, 100, 255),   # purple neon
    "🤐": (220, 220, 220),   # white neon
    "👀": (0, 255, 200),     # mint neon (kept for safety)
    "👁️-👁️": (0, 255, 200),  # mint neon for idle face
    "🥰": (255, 100, 180),   # blush pink
    "🙄": (240, 240, 240),   # grey/white neon for rolling eyes
}


# ----------------------------
# Emoji extraction
# ----------------------------
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "]+"
)


def extract_first_emoji(text: str) -> Optional[str]:
    m = EMOJI_PATTERN.search(text)
    return m.group(0) if m else None


# ----------------------------
# Flexible text -> emoji (stub)
# Later replace with your real LLM output
# ----------------------------
def llm_stub(user_prompt: str) -> str:
    p = user_prompt.lower().strip()

    # Sleep
    if any(k in p for k in ["sleep", "go to sleep", "sleep mode", "going to sleep"]):
        return "💤"

    # Proximity
    if any(k in p for k in [
        "proximity", "too close", "close to the screen", "close to screen", "come closer",
        "you are close", "you're close", "move back", "back up", "sit back", "distance"
    ]):
        return "🫸"

    # Phone
    if any(k in p for k in [
        "phone", "mobile", "cell", "cellphone", "smartphone",
        "scroll", "scrolling", "instagram", "reels", "tiktok", "youtube shorts",
        "using phone", "on my phone", "picked up my phone", "device"
    ]):
        return "📵"

    # Love
    if any(k in p for k in ["love", "i love you", "i love u", "love you", "heart", "❤️", "❤", "♥"]):
        return "❤️"

    # Hate / dislike -> 😔
    if any(k in p for k in [
        "hate", "i hate you", "dislike", "i dislike", "dont like", "don't like",
        "i dont like", "i don't like", "i dont love", "i don't love"
    ]):
        return "😔"

    # Silence
    if any(k in p for k in ["silence", "mute", "be quiet", "quiet", "stop talking", "shut up"]):
        return "🤐"

    # Joke
    if any(k in p for k in ["joke", "funny", "make me laugh"]):
        return "😂"

    # Focus on/off
    if any(k in p for k in ["focus mode on", "focus on", "turn on focus", "enable focus", "start focus"]):
        return "🎯"
    if any(k in p for k in ["focus mode off", "focus off", "turn off focus", "disable focus", "stop focus"]):
        return "🧘"

    # Default idle
    return IDLE_FACE


# ----------------------------
# Load PNG frames from ./assets/<anim_name>/*.png
# ----------------------------
def load_frames(folder: Path) -> List[Image.Image]:
    if not folder.exists():
        return []
    frames: List[Image.Image] = []
    for fp in sorted(folder.glob("*.png")):
        try:
            frames.append(Image.open(fp).convert("RGBA"))
        except Exception:
            pass
    return frames


@dataclass
class DisplayState:
    mode: str = "BOOT"            # BOOT | IDLE | EVENT
    idle_variant: str = "center"  # center | left | right
    last_idle_move: float = 0.0


class MiniLCDSimulator:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Mini LCD Simulator (Emoji Frames + Neon Glow)")

        self.lcd_w = 260
        self.lcd_h = 260

        # Neon glow driven by emoji
        self.current_emoji = IDLE_FACE
        self.volume = 50

        container = ttk.Frame(root, padding=12)
        container.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.screen = tk.Canvas(
            container,
            width=self.lcd_w,
            height=self.lcd_h,
            bg="#06080a",
            highlightthickness=3,
            highlightbackground="#1f3b2e",
        )
        self.screen.grid(row=0, column=0, sticky="n")

        controls = ttk.Frame(container, padding=(0, 12, 0, 0))
        controls.grid(row=1, column=0, sticky="ew")
        controls.columnconfigure(0, weight=1)

        ttk.Label(controls, text="Type what the user says (simulates speech→LLM):").grid(row=0, column=0, sticky="w")
        self.prompt_var = tk.StringVar()
        self.entry = ttk.Entry(controls, textvariable=self.prompt_var)
        self.entry.grid(row=1, column=0, sticky="ew", pady=(6, 6))
        self.entry.bind("<Return>", lambda e: self.on_user_prompt())

        touch_frame = ttk.LabelFrame(container, text="Touch Sensor Simulation", padding=10)
        touch_frame.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        touch_frame.columnconfigure(2, weight=1)

        self.loc_var = tk.StringVar(value="Head")
        ttk.Radiobutton(touch_frame, text="Head", variable=self.loc_var, value="Head").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(touch_frame, text="Cheek Left", variable=self.loc_var, value="Left").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(touch_frame, text="Cheek Right", variable=self.loc_var, value="Right").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(touch_frame, text="Both Cheeks", variable=self.loc_var, value="Both").grid(row=3, column=0, sticky="w")

        ttk.Label(touch_frame, text="Taps (Head only):").grid(row=0, column=1, sticky="w", padx=(15, 5))
        self.head_var = tk.IntVar(value=1)
        self.head_spin = tk.Spinbox(touch_frame, from_=1, to=3, textvariable=self.head_var, width=5)
        self.head_spin.grid(row=0, column=2, sticky="w")

        self.vol_var = tk.StringVar(value=f"Volume: {self.volume}%")
        self.vol_label = ttk.Label(touch_frame, textvariable=self.vol_var)
        self.vol_label.grid(row=4, column=0, columnspan=3, pady=5)

        ttk.Button(touch_frame, text="Apply Touch → Robot", command=self.apply_touch).grid(row=5, column=0, columnspan=3, sticky="ew")

        self.state = DisplayState(last_idle_move=time.time())

        base = Path(__file__).parent / "assets"
        self.anim: Dict[str, List[Image.Image]] = {
            "idle_center": load_frames(base / "idle_center"),
            "idle_left": load_frames(base / "idle_left"),
            "idle_right": load_frames(base / "idle_right"),

            "laugh": load_frames(base / "laugh"),
            "focus_on": load_frames(base / "focus_on"),
            "focus_off": load_frames(base / "focus_off"),
            "phone": load_frames(base / "phone"),
            "proximity": load_frames(base / "proximity"),

            "sleep": load_frames(base / "sleep"),
            "love": load_frames(base / "love"),
            "hate": load_frames(base / "hate"),
            "silence": load_frames(base / "silence"),
            "blush": load_frames(base / "blush"),
            "angry": load_frames(base / "angry"),
        }

        self._current_frames: List[Image.Image] = []
        self._frame_index: int = 0
        self._playing: bool = False
        self._loop: bool = True
        self._fps_ms: int = 170
        self._tk_img_ref = None
        self._fallback_to_idle = False
        self._hold_last_ms = 0

        self.entry.focus_set()
        self.start_boot_marquee("Hello there")

        self._idle_tick()
        self._glow_refresh()

    def clear_screen(self):
        self.screen.delete("all")

        self.screen.create_rectangle(
            0, 0, self.lcd_w, self.lcd_h,
            fill="#06080a", outline=""
        )

        r, g, b = GLOW_COLORS.get(self.current_emoji, (0, 255, 200))

        t = time.time()
        pulse = 0.65 + 0.35 * abs(math.sin(t * 2.6))

        def neon_channel(c: int, strength: float) -> int:
            return max(0, min(255, int(c * strength)))

        layers = [
            (26, 0.10),
            (22, 0.18),
            (18, 0.30),
            (14, 0.45),
            (10, 0.70),
            (7,  0.95),
            (4,  1.20),
        ]

        for pad, intensity in layers:
            strength = intensity * pulse
            col = f"#{neon_channel(r, strength):02x}{neon_channel(g, strength):02x}{neon_channel(b, strength):02x}"
            self.screen.create_rectangle(
                pad, pad, self.lcd_w - pad, self.lcd_h - pad,
                outline=col, width=4
            )

        self.screen.create_rectangle(
            10, 10, self.lcd_w - 10, self.lcd_h - 10,
            outline="#10251c", width=2
        )

    def draw_frame(self, img: Image.Image):
        self.clear_screen()
        frame = img.resize((self.lcd_w - 20, self.lcd_h - 20), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(frame)
        self._tk_img_ref = tk_img
        self.screen.create_image(self.lcd_w // 2, self.lcd_h // 2, image=tk_img, anchor="center")

    def _glow_refresh(self):
        if not self._playing and self._current_frames:
            idx = max(0, min(len(self._current_frames) - 1, self._frame_index - 1))
            self.draw_frame(self._current_frames[idx])

        self.root.after(33, self._glow_refresh)

    def play_animation(self, name: str, loop: bool, fps_ms: int, fallback_to_idle: bool, hold_last_ms: int = 0):
        frames = self.anim.get(name, [])
        if not frames:
            self.play_idle("center")
            return

        self._current_frames = frames
        self._frame_index = 0
        self._playing = True
        self._loop = loop
        self._fps_ms = fps_ms
        self._fallback_to_idle = fallback_to_idle
        self._hold_last_ms = hold_last_ms

        self._animate_step()

    def _animate_step(self):
        if not self._playing or not self._current_frames:
            return

        self.draw_frame(self._current_frames[self._frame_index])
        self._frame_index += 1

        if self._frame_index >= len(self._current_frames):
            if self._loop:
                self._frame_index = 0
            else:
                self._playing = False
                if self._fallback_to_idle:
                    if self._hold_last_ms > 0:
                        self.root.after(self._hold_last_ms, lambda: self.play_idle(self.state.idle_variant))
                    else:
                        self.play_idle(self.state.idle_variant)
                return

        self.root.after(self._fps_ms, self._animate_step)

    def play_idle(self, variant: str):
        self.state.mode = "IDLE"
        self.state.idle_variant = variant
        self.current_emoji = IDLE_FACE

        if variant == "left":
            self.play_animation("idle_left", loop=False, fps_ms=120, fallback_to_idle=True, hold_last_ms=700)
        elif variant == "right":
            self.play_animation("idle_right", loop=False, fps_ms=120, fallback_to_idle=True, hold_last_ms=700)
        else:
            self.play_animation("idle_center", loop=True, fps_ms=170, fallback_to_idle=False)

    def _idle_tick(self):
        now = time.time()
        if self.state.mode == "IDLE":
            if (now - self.state.last_idle_move) >= 60:
                self.state.last_idle_move = now
                next_variant = "left" if self.state.idle_variant != "left" else "right"
                self.play_idle(next_variant)

        self.root.after(500, self._idle_tick)

    def start_boot_marquee(self, text: str):
        self.state.mode = "BOOT"
        self.current_emoji = IDLE_FACE
        self.clear_screen()

        self.marquee_text = self.screen.create_text(
            self.lcd_w + 10,
            self.lcd_h // 2,
            text=text,
            fill="#d9f7e8",
            font=("Consolas", 28, "bold"),
            anchor="w",
        )

        self.marquee_speed_px = 3
        self.marquee_loops_remaining = 2
        self._animate_marquee()

    def _animate_marquee(self):
        if self.state.mode != "BOOT":
            return

        self.screen.move(self.marquee_text, -self.marquee_speed_px, 0)
        bbox = self.screen.bbox(self.marquee_text)

        if bbox and bbox[2] < 0:
            self.marquee_loops_remaining -= 1
            if self.marquee_loops_remaining <= 0:
                self.state.last_idle_move = time.time()
                self.play_idle("center")
                return
            self.screen.coords(self.marquee_text, self.lcd_w + 10, self.lcd_h // 2)

        self.root.after(16, self._animate_marquee)

    def emoji_to_animation(self, emoji: str) -> Optional[str]:
        if emoji in ("❤️", "❤", "♥", "♥️"):
            return "love"

        return {
            "😂": "laugh",
            "🎯": "focus_on",
            "🧘": "focus_off",
            "📵": "phone",
            "🫸": "proximity",
            "💤": "sleep",
            "😔": "hate",
            "🤐": "silence",
            "🥰": "blush",
            "🙄": "angry",
            "👀": "idle_center",
        }.get(emoji)

    def on_user_prompt(self):
        user_prompt = self.prompt_var.get().strip()
        if not user_prompt:
            return
        self.prompt_var.set("")

        llm_out = llm_stub(user_prompt)
        emoji = extract_first_emoji(llm_out) or IDLE_FACE

        if emoji in ("❤", "♥", "♥️"):
            emoji = "❤️"

        self.current_emoji = emoji
        anim_name = self.emoji_to_animation(emoji)

        if anim_name in ("idle_center", None):
            self.play_idle("center")
            return

        self.state.mode = "EVENT"
        self.play_animation(anim_name, loop=False, fps_ms=90, fallback_to_idle=True, hold_last_ms=5000)

    # ----------------------------
    # Touch & Sound Logic
    # ----------------------------
    def apply_touch(self):
        loc = self.loc_var.get()

        # Location Logic
        if loc == "Both":
            self.current_emoji = "❤️"
            self.play_animation("love", loop=False, fps_ms=90, fallback_to_idle=True, hold_last_ms=5000)
            self.speak_tts("I love you")
        elif loc == "Left":
            self.volume = max(0, self.volume - 10)
            self.vol_var.set(f"Volume: {self.volume}%")
        elif loc == "Right":
            self.volume = min(100, self.volume + 10)
            self.vol_var.set(f"Volume: {self.volume}%")
        elif loc == "Head":
            head = self.head_var.get()
            if head == 1:
                self.current_emoji = "�"
                self.play_animation("angry", loop=False, fps_ms=90, fallback_to_idle=True, hold_last_ms=5000)
            elif head == 2:
                self.current_emoji = "🥰"
                self.play_animation("blush", loop=False, fps_ms=90, fallback_to_idle=True, hold_last_ms=5000)
            elif head == 3:
                self.current_emoji = "💤"
                self.play_animation("sleep", loop=False, fps_ms=90, fallback_to_idle=True, hold_last_ms=5000)

    def play_sound(self, name, freq, dur):
        """Play wav or fallback to beep."""
        def _target():
            wav = Path(__file__).parent / "sounds" / f"{name}.wav"
            if wav.exists() and winsound:
                try:
                    winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC)
                    return
                except:
                    pass
            if winsound:
                winsound.Beep(freq, dur)
        threading.Thread(target=_target, daemon=True).start()

    def speak_tts(self, text):
        """Non-blocking TTS."""
        def _target():
            if pyttsx3:
                try:
                    engine = pyttsx3.init()
                    engine.say(text)
                    engine.runAndWait()
                except Exception as e:
                    print(f"TTS Error: {e}")
            else:
                print(f"Robot says: {text} (pyttsx3 not installed)")
        threading.Thread(target=_target, daemon=True).start()


def main():
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", 1.2)
    except Exception:
        pass

    MiniLCDSimulator(root)
    root.mainloop()


if __name__ == "__main__":
    main()
