"""Isolated, failure-safe sound output for Claude Desktop Access."""

import os

import nvwave
import tones
import wx
from logHandler import log

from .core import soundKey, tonePattern


def safeBeep(frequency, duration):
	try:
		tones.beep(frequency, duration)
	except Exception:
		log.debugWarning("Claude Desktop Access tone output failed", exc_info=True)


def _playProgressTone(category, message=""):
	delay = 0
	for index, (frequency, duration) in enumerate(tonePattern(category, message)):
		if index == 0:
			safeBeep(frequency, duration)
		else:
			wx.CallLater(delay, safeBeep, frequency, duration)
		delay += duration + 25


def playProgressSound(category, message="", style="clicks", volume="normal"):
	"""Play one progress earcon, falling back to the matching tone pattern."""
	if style == "tones":
		_playProgressTone(category, message)
		return
	path = os.path.join(os.path.dirname(__file__), "sounds", volume, f"{soundKey(category, message)}.wav")
	try:
		nvwave.playWaveFile(path)
	except Exception:
		log.debugWarning("Claude Desktop Access could not play click earcon; using tones", exc_info=True)
		_playProgressTone(category, message)
