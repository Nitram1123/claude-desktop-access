"""Bounded, cancellable retrieval of virtualized conversation messages."""

import time


class MessageReview:
	def __init__(self, position, read, activate, valid, report, failed, schedule, clock=time.monotonic):
		self.position = position
		self.read, self.activate, self.valid = read, activate, valid
		self.report, self.failed, self.schedule, self.clock = report, failed, schedule, clock
		self.deadline = clock() + 5.0
		self.activated = set()
		self.timer = None
		self.cancelled = False

	def cancel(self):
		self.cancelled = True
		if self.timer is not None:
			self.timer.Stop()
			self.timer = None

	def step(self):
		self.timer = None
		if self.cancelled:
			return
		try:
			if not self.valid():
				self.cancel()
				return
			messages, loader = self.read(self.position)
			if not self.valid() or self.cancelled:
				self.cancel()
				return
			if len(messages) >= self.position:
				self.report(messages)
				return
			if self.clock() >= self.deadline:
				self.failed()
				return
			if loader is None:
				if self.activated:
					# The old buffer can disappear before its replacement is ready.
					self.timer = self.schedule(150, self.step)
				else:
					self.report(messages)
				return
			if loader not in self.activated:
				if len(self.activated) >= 10:
					self.failed()
					return
				self.activated.add(loader)
				self.activate(loader)
			self.timer = self.schedule(150, self.step)
		except Exception:
			self.failed()
