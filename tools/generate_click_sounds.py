"""Generate original, license-free click earcons for Claude Desktop Access."""

from pathlib import Path
import math
import random
import struct
import wave


SAMPLE_RATE = 44100
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "globalPlugins" / "claudeDesktopAccess" / "sounds"
PATTERNS = {
	# Entries are offset milliseconds, resonant frequency, and percussive character.
	"thinking": ((0, 720, "hollow"), (125, 980, "hollow")),
	"working": ((0, 680, "muted"),),
	"command": ((0, 560, "sharp"), (145, 1320, "sharp")),
	"search": ((0, 1050, "bright"), (68, 1370, "bright"), (136, 1740, "bright")),
	"file": ((0, 1080, "dry"), (52, 760, "dry"), (185, 520, "hollow")),
	"build": ((0, 520, "heavy"), (112, 820, "sharp"), (224, 1160, "bright")),
	"tool": ((0, 1420, "dry"), (48, 1420, "dry")),
	"completion": ((0, 620, "hollow"), (105, 970, "sharp"), (220, 1510, "bright")),
	"failure": ((0, 1380, "heavy"), (130, 780, "heavy"), (270, 390, "heavy")),
	"other": ((0, 860, "dry"),),
	"commentary": ((0, 480, "hollow"), (78, 620, "muted")),
	"attention": ((0, 1180, "bright"), (72, 1720, "bright"), (205, 1180, "bright"), (277, 1720, "bright")),
	"backgroundPulse1": ((0, 430, "muted"), (170, 650, "hollow")),
	"backgroundPulse2": ((0, 700, "muted"), (205, 470, "hollow")),
	"monitoringActive": ((0, 520, "hollow"), (135, 1120, "bright")),
	"monitoringInactive": ((0, 1120, "dry"), (165, 430, "muted")),
	"submission": ((0, 620, "dry"), (58, 920, "sharp"), (128, 1420, "bright"), (218, 1840, "bright")),
}
# Keep large perceptual gaps between these short sounds. Small amplitude
# differences are difficult to distinguish in NVDA's normal audio mix.
LEVELS = {"soft": 0.10, "normal": 0.30, "loud": 0.58}


CHARACTERS = {
	"muted": (0.020, 0.0040, 0.72, 0.28, 0.55),
	"dry": (0.026, 0.0045, 0.62, 0.38, 0.35),
	"sharp": (0.034, 0.0055, 0.45, 0.55, 0.18),
	"bright": (0.040, 0.0070, 0.32, 0.68, 0.10),
	"hollow": (0.052, 0.0120, 0.24, 0.76, -0.20),
	"heavy": (0.058, 0.0140, 0.40, 0.60, -0.45),
}


def clickSample(relativeTime, frequency, character, amplitude, rng):
	duration, decay, noiseMix, toneMix, sweep = CHARACTERS[character]
	if relativeTime < 0 or relativeTime >= duration:
		return 0.0
	attack = min(1.0, relativeTime / 0.0008)
	envelope = attack * math.exp(-relativeTime / decay)
	phase = 2 * math.pi * frequency * (relativeTime + sweep * relativeTime * relativeTime * 5)
	resonance = math.sin(phase) + 0.28 * math.sin(phase * 2.01)
	noise = rng.uniform(-1.0, 1.0)
	return envelope * (noiseMix * noise + toneMix * resonance) * amplitude


def render(name, pattern, levelName, amplitude):
	rng = random.Random(f"code-status-announcer-{name}")
	duration = max(offset / 1000 + CHARACTERS[character][0] for offset, frequency, character in pattern) + 0.015
	frames = []
	for sampleIndex in range(math.ceil(duration * SAMPLE_RATE)):
		time = sampleIndex / SAMPLE_RATE
		value = sum(
			clickSample(time - offset / 1000, frequency, character, amplitude, rng)
			for offset, frequency, character in pattern
		)
		value = max(-0.50, min(0.50, value))
		frames.append(struct.pack("<h", round(value * 32767)))
	levelDir = OUTPUT_DIR / levelName
	levelDir.mkdir(parents=True, exist_ok=True)
	path = levelDir / f"{name}.wav"
	with wave.open(str(path), "wb") as output:
		output.setnchannels(1)
		output.setsampwidth(2)
		output.setframerate(SAMPLE_RATE)
		output.writeframes(b"".join(frames))


OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
for levelName, amplitude in LEVELS.items():
	for soundName, soundPattern in PATTERNS.items():
		render(soundName, soundPattern, levelName, amplitude)
print(f"Generated {len(PATTERNS) * len(LEVELS)} click earcons in {OUTPUT_DIR}")
