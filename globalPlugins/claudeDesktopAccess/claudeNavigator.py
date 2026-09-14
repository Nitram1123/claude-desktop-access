"""User-requested, bounded Claude navigation with explicit activation."""
import time

import addonHandler
import api
import gui
import ui
import wx

from .claudeAdapter import navigationKind, roleName

addonHandler.initTranslation()


class ClaudeNavigator(wx.Dialog):
	def __init__(self, items, onAction, onClose, truncated=False):
		super().__init__(gui.mainFrame, title=_("Claude navigation"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.items = items
		self.visible = []
		self.onAction, self.onClose = onAction, onClose
		self.closed = False
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(wx.StaticText(self, label=_("&Search modes, artifacts and attachments:")), flag=wx.ALL, border=8)
		self.search = wx.TextCtrl(self)
		sizer.Add(self.search, flag=wx.EXPAND | wx.ALL, border=8)
		self.results = wx.ListBox(self)
		sizer.Add(self.results, 1, wx.EXPAND | wx.ALL, 8)
		self.status = wx.StaticText(self, label="")
		sizer.Add(self.status, flag=wx.ALL, border=8)
		if truncated:
			sizer.Add(wx.StaticText(self, label=_("Scan limit reached. Some controls may be missing.")), flag=wx.ALL, border=8)
		buttons = wx.BoxSizer(wx.HORIZONTAL)
		for label, action in ((_("&Move to item"), "move"), (_("&Activate item"), "activate")):
			button = wx.Button(self, label=label)
			button.Bind(wx.EVT_BUTTON, lambda event, action=action: self.perform(action))
			buttons.Add(button, flag=wx.ALL, border=8)
		close = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
		close.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		buttons.Add(close, flag=wx.ALL, border=8)
		sizer.Add(buttons)
		self.SetSizer(sizer)
		self.SetSize((650, 440))
		self.search.Bind(wx.EVT_TEXT, self.filter)
		self.results.Bind(wx.EVT_LISTBOX_DCLICK, lambda event: self.perform("move"))
		self.Bind(wx.EVT_CHAR_HOOK, self.key)
		self.Bind(wx.EVT_CLOSE, self.close)
		self.filter()
		self.search.SetFocus()

	def filter(self, event=None):
		query = self.search.GetValue().casefold().strip()
		self.visible = [item for item in self.items if query in item[0].casefold()]
		self.results.Set([item[0] for item in self.visible])
		if self.visible:
			self.results.SetSelection(0)
		self.status.SetLabel(_("{count} items. Enter moves to the selected item.").format(count=len(self.visible)))

	def key(self, event):
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.perform("move")
		elif event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def perform(self, action):
		index = self.results.GetSelection()
		if index == wx.NOT_FOUND or index >= len(self.visible):
			ui.message(_("No Claude control is selected"))
			return
		obj = self.visible[index][1]
		self.Close()
		wx.CallLater(150, self.onAction, obj, action)

	def close(self, event):
		if self.closed:
			return
		self.closed = True
		self.items = self.visible = []
		self.onClose()
		self.Destroy()


class NavigationScan:
	"""Yield to NVDA between small slices; never run as a background poll."""
	def __init__(self, root, valid, completed):
		self.root = root
		self.pending = [root]
		self.seen = {}
		self.items = []
		self.valid, self.completed = valid, completed
		self.timer = None
		self.cancelled = False
		self.startTime = time.monotonic()

	def cancel(self):
		self.cancelled = True
		if self.timer:
			self.timer.Stop()
		self.timer = None
		self.pending.clear()
		self.items.clear()
		self.seen.clear()

	def step(self):
		self.timer = None
		if self.cancelled or not self.valid():
			self.cancel()
			return
		deadline = time.monotonic() + .008
		count = 0
		while self.pending and len(self.seen) < 700 and count < 15 and time.monotonic() < deadline:
			obj = self.pending.pop()
			if id(obj) in self.seen:
				continue
			self.seen[id(obj)] = obj
			count += 1
			try:
				kind = navigationKind(getattr(obj, "name", ""), getattr(obj, "role", None))
				if kind:
					self.items.append((f"{kind}: {obj.name}", obj))
				# One sibling at a time avoids unbounded child enumeration.
				sibling = getattr(obj, "next", None)
				child = getattr(obj, "firstChild", None) if obj is self.root or roleName(getattr(obj, "role", None)) != "document" else None
				if sibling and obj is not self.root:
					self.pending.append(sibling)
				if child:
					self.pending.append(child)
			except Exception:
				continue
		if self.pending and len(self.seen) < 700 and time.monotonic() - self.startTime < 8:
			self.timer = wx.CallLater(15, self.step)
		else:
			items = tuple(self.items)
			truncated = bool(self.pending)
			self.pending.clear()
			self.items.clear()
			self.seen.clear()
			self.completed(items, truncated)
