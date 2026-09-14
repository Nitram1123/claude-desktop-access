"""Accessible recent and archived chat-history dialog."""

import addonHandler
import ui
import wx


addonHandler.initTranslation()


class ChatHistoryDialog(wx.Dialog):
	"""Search and operate recent and archived titles exposed by Claude."""

	def __init__(self, parent, mode, agentName, recentTitles, archivedTitles, archivedLoaded, onRefresh, onAction, onClose):
		super().__init__(parent, title=_("{agent} chat history").format(agent=agentName))
		self._mode = mode
		self._agentName = agentName
		self._allRecentTitles = tuple(recentTitles)
		self._allArchivedTitles = tuple(archivedTitles)
		self._onActionCallback = onAction
		self._onRefreshCallback = onRefresh
		self._onCloseCallback = onClose
		self._closing = False
		self._lastList = None
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(wx.StaticText(self, label=_("Search chats:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=10)
		self.search = wx.TextCtrl(self)
		mainSizer.Add(self.search, flag=wx.EXPAND | wx.ALL, border=10)
		mainSizer.Add(wx.StaticText(self, label=_("Recent chats:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self.recentList = wx.ListBox(self, choices=list(self._allRecentTitles), style=wx.LB_SINGLE)
		mainSizer.Add(self.recentList, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
		mainSizer.Add(wx.StaticText(self, label=_("Archived chats:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self._archivedLoaded = archivedLoaded
		self._archivedEmptyMessage = self._emptyArchivedMessage(archivedLoaded)
		archivedChoices = list(self._allArchivedTitles) or [self._archivedEmptyMessage]
		self.archivedList = wx.ListBox(self, choices=archivedChoices, style=wx.LB_SINGLE)
		mainSizer.Add(self.archivedList, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
		self.resultStatus = wx.StaticText(self, label="")
		mainSizer.Add(self.resultStatus, flag=wx.LEFT | wx.RIGHT, border=10)
		self.refreshButton = wx.Button(self, label=_("&Refresh chat lists"))
		mainSizer.Add(self.refreshButton, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = self.CreateButtonSizer(wx.OK | wx.CANCEL)
		mainSizer.Add(buttons, flag=wx.EXPAND | wx.ALL, border=10)
		self.SetSizerAndFit(mainSizer)
		self.SetMinSize((520, 420))
		self.search.Bind(wx.EVT_TEXT, self._onFilter)
		self.search.Bind(wx.EVT_KEY_DOWN, self._onSearchKey)
		self.recentList.Bind(wx.EVT_LISTBOX_DCLICK, self._onOpen)
		self.archivedList.Bind(wx.EVT_LISTBOX_DCLICK, self._onOpen)
		self.recentList.Bind(wx.EVT_CONTEXT_MENU, self._onContextMenu)
		self.archivedList.Bind(wx.EVT_CONTEXT_MENU, self._onContextMenu)
		self.recentList.Bind(wx.EVT_SET_FOCUS, lambda evt: self._rememberListFocus(evt, self.recentList))
		self.archivedList.Bind(wx.EVT_SET_FOCUS, lambda evt: self._rememberListFocus(evt, self.archivedList))
		self.refreshButton.Bind(wx.EVT_BUTTON, self._onRefresh)
		self.Bind(wx.EVT_BUTTON, self._onOpen, id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON, lambda evt: self.Close(), id=wx.ID_CANCEL)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self._selectFirst(self.recentList)
		self._selectFirst(self.archivedList)
		self._lastList = self.recentList
		self._updateResultStatus()
		self.search.SetFocus()

	def _emptyArchivedMessage(self, archivedLoaded):
		if archivedLoaded:
			return _("No archived {agent} chats").format(agent=self._agentName)
		return _("Claude has not exposed archived chats in this view. This beta reads only accessible native controls.")

	def _rememberListFocus(self, evt, control):
		self._lastList = control
		evt.Skip()

	def _selectFirst(self, control):
		if control.GetCount():
			control.SetSelection(0)

	def _onFilter(self, evt):
		query = self.search.GetValue().strip().casefold()
		recentChoices = [title for title in self._allRecentTitles if query in title.casefold()]
		archivedChoices = [title for title in self._allArchivedTitles if query in title.casefold()]
		self.recentList.Set(recentChoices)
		self.archivedList.Set(archivedChoices or ([self._archivedEmptyMessage] if not self._allArchivedTitles else []))
		self._selectFirst(self.recentList)
		self._selectFirst(self.archivedList)
		self._updateResultStatus()

	def _updateResultStatus(self):
		recentCount = self.recentList.GetCount()
		archivedCount = len(self._allArchivedTitles) if self.archivedList.GetCount() and not self._allArchivedTitles else self.archivedList.GetCount()
		self.resultStatus.SetLabel(
			_("{recent} recent results; {archived} archived results").format(
				recent=recentCount, archived=archivedCount,
			)
		)

	def _onRefresh(self, evt):
		recentTitles, archivedTitles, archivedLoaded = self._onRefreshCallback()
		self._allRecentTitles = tuple(recentTitles)
		self._allArchivedTitles = tuple(archivedTitles)
		self._archivedLoaded = archivedLoaded
		self._archivedEmptyMessage = self._emptyArchivedMessage(archivedLoaded)
		self._onFilter(None)
		ui.message(self.resultStatus.GetLabel())

	def _onSearchKey(self, evt):
		if evt.GetKeyCode() not in (wx.WXK_DOWN, wx.WXK_UP):
			evt.Skip()
			return
		target = self.recentList if self.recentList.GetCount() else (
			self.archivedList if self._allArchivedTitles and self.archivedList.GetCount() else None
		)
		if target is not None:
			target.SetFocus()
			target.SetSelection(0 if evt.GetKeyCode() == wx.WXK_DOWN else target.GetCount() - 1)
			return
		evt.Skip()

	def _onOpen(self, evt):
		selection = self.selectedEntry()
		if selection is None:
			if self._lastList is self.archivedList and not self._allArchivedTitles:
				ui.message(self._archivedEmptyMessage)
			else:
				ui.message(_("No matching {agent} chats").format(agent=self._agentName))
			return
		self._onActionCallback(selection[0], "open", selection[1], self._mode)
		self.Close()

	def _onCharHook(self, evt):
		selection = self.selectedEntry()
		if evt.GetKeyCode() == wx.WXK_F10 and evt.ShiftDown() and selection is not None:
			self._showChatActionMenu(selection)
			return
		evt.Skip()

	def _onContextMenu(self, evt):
		"""Handle Shift+F10 and the Context Menu key emitted by native list boxes."""
		control = evt.GetEventObject()
		if control in (self.recentList, self.archivedList):
			self._lastList = control
		selection = self.selectedEntry()
		if selection is None:
			ui.message(_("No matching {agent} chats").format(agent=self._agentName))
			return
		self._showChatActionMenu(selection)

	def _showChatActionMenu(self, selection):
		"""Move recent-chat focus to native actions; retain an archived-chat menu."""
		if selection[1] != "archived":
			self._performSelectedAction(selection, "focusActions")
			return
		menu = wx.Menu()
		chosen = []
		openItem = menu.Append(wx.ID_ANY, _("Open archived chat"))
		menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("open"), openItem)
		try:
			self.PopupMenu(menu)
		finally:
			menu.Destroy()
		if chosen:
			self._performSelectedAction(selection, chosen[0])

	def _performSelectedAction(self, selection, action):
		if self._closing:
			return
		self._onActionCallback(selection[0], action, selection[1], self._mode)
		self.Close()

	def _onClose(self, evt):
		if self._closing:
			return
		self._closing = True
		self.Hide()
		self.Destroy()
		self._onCloseCallback()

	def selectedEntry(self):
		focused = wx.Window.FindFocus()
		control = focused if focused in (self.recentList, self.archivedList) else self._lastList
		selection = control.GetSelection()
		if selection == wx.NOT_FOUND:
			return None
		title = control.GetString(selection)
		if title == self._archivedEmptyMessage:
			return None
		return title, ("archived" if control is self.archivedList else "recent")
