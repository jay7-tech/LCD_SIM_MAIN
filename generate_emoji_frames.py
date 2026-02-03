import os
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Output folder (will create ./assets/*)
OUT_DIR = Path(__file__).parent / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

W, H = 240, 240
BG = (11, 26, 19, 255)

# Windows emoji font (keeps emoji shape/features)
FONT_PATH = r"C:\Windows\Fonts\seguiemj.ttf"
if not os.path.exists(FONT_PATH):
    raise FileNotFoundError(f"Emoji font not found: {FONT_PATH}")

FONT_SIZE = 150
FONT = ImageFont.truetype(FONT_PATH, FONT_SIZE)

# Idle face pattern (what simulator uses as IDLE_FACE string)
IDLE_FACE = "👁️-👁️"


# ----------------------------
# 1) Special idle-face renderer (GUARANTEED two eyes)
# ----------------------------
def render_idle_face_graphics() -> Image.Image:
    """
    Draw two eyes + dash using shapes.
    This avoids Pillow's unreliable multi-emoji rendering on Windows.
    """
    out = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(out)

    # Make it small-ish and centered (you said it's okay to be small)
    cy = H // 2
    eye_r = 26          # eye outer radius
    iris_r = 12
    pupil_r = 6

    # Positions
    left_x = W // 2 - 55
    right_x = W // 2 + 55
    dash_len = 28

    # Dash
    dash_y = cy
    d.line(
        [(W // 2 - dash_len // 2, dash_y), (W // 2 + dash_len // 2, dash_y)],
        fill=(220, 240, 235, 255),
        width=6
    )

    def eye(cx, cy):
        # outer white
        d.ellipse((cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r), fill=(245, 245, 245, 255))
        # iris (brown)
        d.ellipse((cx - iris_r, cy - iris_r, cx + iris_r, cy + iris_r), fill=(120, 70, 45, 255))
        # pupil (dark)
        d.ellipse((cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r), fill=(10, 10, 10, 255))
        # highlight
        d.ellipse((cx - 9, cy - 10, cx - 3, cy - 4), fill=(255, 255, 255, 255))

        # subtle outline
        d.ellipse((cx - eye_r, cy - eye_r, cx + eye_r, cy + eye_r), outline=(200, 200, 200, 255), width=3)

    eye(left_x, cy)
    eye(right_x, cy)

    return out


# ----------------------------
# 2) Normal emoji renderer (for all other emojis)
# ----------------------------
def render_emoji(emoji: str) -> Image.Image:
    # ✅ Idle face uses graphics instead of emoji font (fixes missing eye)
    if emoji == IDLE_FACE:
        return render_idle_face_graphics()

    big = 512
    tmp = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(tmp)

    bbox = d.textbbox((0, 0), emoji, font=FONT)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (big - tw) // 2 - bbox[0]
    y = (big - th) // 2 - bbox[1]

    d.text((x, y), emoji, font=FONT, fill=(255, 255, 255, 255), embedded_color=True)

    alpha = tmp.split()[-1]
    tight = alpha.getbbox()
    if not tight:
        return Image.new("RGBA", (W, H), BG)

    cropped = tmp.crop(tight)

    margin = 18
    max_w = W - 2 * margin
    max_h = H - 2 * margin

    scale = min(max_w / cropped.size[0], max_h / cropped.size[1], 1.0)
    new_size = (max(1, int(cropped.size[0] * scale)), max(1, int(cropped.size[1] * scale)))
    cropped = cropped.resize(new_size, Image.Resampling.LANCZOS)

    out = Image.new("RGBA", (W, H), BG)
    px = (W - cropped.size[0]) // 2
    py = (H - cropped.size[1]) // 2
    out.alpha_composite(cropped, (px, py))
    return out


def transform(base: Image.Image, dx=0, dy=0, scale=1.0, rot=0.0) -> Image.Image:
    nw = max(1, int(W * scale))
    nh = max(1, int(H * scale))
    img = base.resize((nw, nh), Image.Resampling.BICUBIC)

    if rot != 0:
        img = img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)

    out = Image.new("RGBA", (W, H), BG)
    px = (W - img.size[0]) // 2 + int(dx)
    py = (H - img.size[1]) // 2 + int(dy)
    out.alpha_composite(img, (px, py))
    return out


def save_sequence(name: str, frames: list[Image.Image]) -> None:
    folder = OUT_DIR / name
    folder.mkdir(parents=True, exist_ok=True)

    for f in folder.glob("frame_*.png"):
        f.unlink()

    for i, im in enumerate(frames, start=1):
        im.save(folder / f"frame_{i:03d}.png")


# ---- animation primitives ----

def pulse(emoji: str, amp=0.08, n=24) -> list[Image.Image]:
    base = render_emoji(emoji)
    frames = []
    for t in range(n):
        phase = 2 * math.pi * (t / n)
        s = 1.0 + amp * (0.5 + 0.5 * math.sin(phase))
        frames.append(transform(base, scale=s))
    return frames


def bounce(emoji: str, amp=14, n=20) -> list[Image.Image]:
    base = render_emoji(emoji)
    frames = []
    for t in range(n):
        phase = 2 * math.pi * (t / n)
        dy = -amp * math.sin(phase)
        s = 1.0 + 0.03 * math.sin(phase)
        frames.append(transform(base, dy=dy, scale=s))
    return frames


def shake(emoji: str, amp=12, n=18) -> list[Image.Image]:
    base = render_emoji(emoji)
    frames = []
    for t in range(n):
        phase = 2 * math.pi * (t / n)
        dx = amp * math.sin(phase)
        rot = 4.0 * math.sin(phase)
        frames.append(transform(base, dx=dx, rot=rot))
    return frames


def floaty(emoji: str, amp=6, n=28) -> list[Image.Image]:
    base = render_emoji(emoji)
    frames = []
    for t in range(n):
        phase = 2 * math.pi * (t / n)
        dy = amp * math.sin(phase)
        frames.append(transform(base, dy=dy))
    return frames


def idle_eyes_frames(n=30) -> list[Image.Image]:
    # idle is IDLE_FACE (graphics eyes) + tiny pulse
    return pulse(IDLE_FACE, amp=0.01, n=n)


def look_shift_frames(direction: str) -> list[Image.Image]:
    base = render_emoji(IDLE_FACE)
    dx = -10 if direction == "left" else 10
    frames = []
    frames += [transform(base, dx=dx) for _ in range(10)]
    frames += [transform(base, dx=0) for _ in range(10)]
    return frames


def repeat(frames: list[Image.Image], times: int) -> list[Image.Image]:
    return frames * max(1, times)


# ---- generate all sequences ----
save_sequence("idle_center", idle_eyes_frames(n=30))
save_sequence("idle_left", look_shift_frames("left"))
save_sequence("idle_right", look_shift_frames("right"))

# Existing events
save_sequence("laugh", repeat(bounce("😂", amp=14, n=20), 2))
save_sequence("focus_on", repeat(pulse("🎯", amp=0.10, n=24), 2))
save_sequence("focus_off", repeat(pulse("🧘", amp=0.06, n=24), 2))
save_sequence("phone", repeat(shake("📵", amp=12, n=18), 2))
save_sequence("proximity", repeat(shake("🫸", amp=10, n=18), 2))

# NEW events
save_sequence("sleep", repeat(floaty("💤", amp=5, n=28), 2))
save_sequence("love", repeat(pulse("❤️", amp=0.14, n=24), 2))
save_sequence("hate", repeat(floaty("😔", amp=4, n=28), 2))
save_sequence("silence", repeat(bounce("🤐", amp=6, n=20), 2))
save_sequence("blush", repeat(pulse("🥰", amp=0.12, n=24), 2))
save_sequence("angry", repeat(shake("🙄", amp=10, n=18), 3))

print("Generated emoji frame sequences into ./assets/")
