"""Observe updates to one Chromium virtual buffer owned by NVDA."""

import time

import wx
from logHandler import log


class BufferUpdateObserver:
	def __init__(self, onUpdate):
		self._onUpdate = onUpdate
		self._detach = None
		self._request = None

	def attach(self, buffer):
		self.detach()
		if buffer is None:
			return
		original = getattr(buffer, "_handleUpdate", None)

		missing = object()
		originalOverride = vars(buffer).get("_handleUpdate", missing)
		pending = None
		lastSampleAt = None
		attached = True

		def sample():
			nonlocal pending, lastSampleAt
			pending = None
			if not attached:
				return
			lastSampleAt = time.monotonic()
			try:
				self._onUpdate(buffer)
			except Exception:
				log.debugWarning("Claude Desktop Access could not read the updated task state", exc_info=True)

		def request():
			nonlocal pending
			if attached and pending is None:
				delay = 120 if lastSampleAt is None else max(120, round(1000 * (1 - (time.monotonic() - lastSampleAt))))
				try:
					pending = wx.CallLater(delay, sample)
				except Exception:
					log.debugWarning("Claude Desktop Access could not schedule a task state read", exc_info=True)

		def handleUpdate(*args, **kwargs):
			result = original(*args, **kwargs)
			request()
			return result

		def detach():
			nonlocal attached, pending
			attached = False
			if pending is not None:
				pending.Stop()
				pending = None
			if vars(buffer).get("_handleUpdate") is handleUpdate:
				if originalOverride is missing:
					del buffer._handleUpdate
				else:
					buffer._handleUpdate = originalOverride

		if callable(original):
			try:
				# NVDA exposes no public virtual-buffer update subscription.
				buffer._handleUpdate = handleUpdate
			except (AttributeError, TypeError):
				log.debugWarning("Claude Desktop Access could not observe this virtual buffer", exc_info=True)
		self._detach = detach
		self._request = request
		request()

	def request(self):
		if self._request is not None:
			self._request()

	def detach(self):
		self._request = None
		if self._detach is not None:
			detach, self._detach = self._detach, None
			detach()
