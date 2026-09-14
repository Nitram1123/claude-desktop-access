"""Accessible navigator for Claude's embedded browser."""

import addonHandler
import ui
import wx

from .browserAccess import browserNavigatorMatches


addonHandler.initTranslation()


class BrowserNavigatorDialog(wx.Dialog):
	"""Search page structure and invoke explicit browser navigation actions."""

	_CATEGORY_CHOICES = (
		("all", _("All items")),
		("controls", _("Browser controls")),
		("headings", _("Headings")),
		("landmarks", _("Landmarks")),
		("links", _("Links")),
		("buttons", _("Buttons")),
		("formFields", _("Form fields")),
		("tables", _("Tables")),
	)
	_CLOSE_ACTIONS = {"move", "activate", "restore", "snapshot", "external", "returnPrompt"}

	def __init__(
		self, parent, pageTitle, addressLabel, summary, items, truncated, savedSignature,
		onAction, onRefresh, onClose,
	):
		super().__init__(parent, title=_("Embedded Browser Navigator"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self._allItems = tuple(items)
		self._visibleItems = ()
		self._truncated = bool(truncated)
		self._savedSignature = savedSignature
		self._preferredSelectionSignature = savedSignature
		self._onActionCallback = onAction
		self._onRefreshCallback = onRefresh
		self._onCloseCallback = onClose
		self._closing = False

		mainSizer = wx.BoxSizer(wx.VERTICAL)
		self.pageInfo = wx.StaticText(self, label="")
		mainSizer.Add(self.pageInfo, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)

		filterSizer = wx.StaticBoxSizer(wx.VERTICAL, self, _("Find page items"))
		filterSizer.Add(wx.StaticText(self, label=_("Search current page:")), flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)
		self.search = wx.TextCtrl(self)
		filterSizer.Add(self.search, flag=wx.EXPAND | wx.ALL, border=8)
		filterSizer.Add(wx.StaticText(self, label=_("Item category:")), flag=wx.LEFT | wx.RIGHT, border=8)
		self.category = wx.Choice(self, choices=[label for key, label in self._CATEGORY_CHOICES])
		self.category.SetSelection(0)
		filterSizer.Add(self.category, flag=wx.EXPAND | wx.ALL, border=8)
		mainSizer.Add(filterSizer, flag=wx.EXPAND | wx.ALL, border=10)

		resultsSizer = wx.StaticBoxSizer(wx.VERTICAL, self, _("Page items"))
		self.results = wx.ListBox(self, style=wx.LB_SINGLE)
		resultsSizer.Add(self.results, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)
		self.resultStatus = wx.StaticText(self, label="")
		resultsSizer.Add(self.resultStatus, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)
		mainSizer.Add(resultsSizer, proportion=1, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

		itemActions = wx.StaticBoxSizer(wx.HORIZONTAL, self, _("Selected item"))
		self.moveButton = wx.Button(self, wx.ID_OK, label=_("&Move to item"))
		self.activateButton = wx.Button(self, label=_("&Activate item"))
		itemActions.Add(self.moveButton, flag=wx.ALL, border=6)
		itemActions.Add(self.activateButton, flag=wx.ALL, border=6)
		mainSizer.Add(itemActions, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

		pageActions = wx.StaticBoxSizer(wx.VERTICAL, self, _("Page actions"))
		pageGrid = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
		pageGrid.AddGrowableCol(0, 1)
		pageGrid.AddGrowableCol(1, 1)
		self.summaryButton = wx.Button(self, label=_("Page su&mmary"))
		self.snapshotButton = wx.Button(self, label=_("Accessible &snapshot"))
		self.refreshButton = wx.Button(self, label=_("&Refresh page items"))
		self.restoreButton = wx.Button(self, label=_("Restore &last location"))
		self.copyAddressButton = wx.Button(self, label=_("&Copy address"))
		self.externalButton = wx.Button(self, label=_("Open in default &browser"))
		self.returnButton = wx.Button(self, label=_("Return to Claude &prompt"))
		for button in (
			self.summaryButton, self.snapshotButton, self.refreshButton, self.restoreButton,
			self.copyAddressButton, self.externalButton, self.returnButton,
		):
			pageGrid.Add(button, flag=wx.EXPAND | wx.ALL, border=3)
		pageActions.Add(pageGrid, flag=wx.EXPAND | wx.ALL, border=3)
		mainSizer.Add(pageActions, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

		closeButton = wx.Button(self, wx.ID_CANCEL, label=_("Close"))
		mainSizer.Add(closeButton, flag=wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		self.SetSizerAndFit(mainSizer)
		self.SetMinSize((680, 560))

		self.search.Bind(wx.EVT_TEXT, self._onFilter)
		self.search.Bind(wx.EVT_KEY_DOWN, self._onSearchKey)
		self.category.Bind(wx.EVT_CHOICE, self._onFilter)
		self.results.Bind(wx.EVT_LISTBOX, self._onSelectionChanged)
		self.results.Bind(wx.EVT_LISTBOX_DCLICK, lambda evt: self._perform("move"))
		self.results.Bind(wx.EVT_CONTEXT_MENU, self._onContextMenu)
		self.moveButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("move"))
		self.activateButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("activate"))
		self.summaryButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("summary", pageAction=True))
		self.snapshotButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("snapshot", pageAction=True))
		self.restoreButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("restore", pageAction=True))
		self.copyAddressButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("copyAddress", pageAction=True))
		self.externalButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("external", pageAction=True))
		self.returnButton.Bind(wx.EVT_BUTTON, lambda evt: self._perform("returnPrompt", pageAction=True))
		self.refreshButton.Bind(wx.EVT_BUTTON, self._onRefresh)
		self.Bind(wx.EVT_BUTTON, lambda evt: self.Close(), id=wx.ID_CANCEL)
		self.Bind(wx.EVT_CHAR_HOOK, self._onCharHook)
		self.Bind(wx.EVT_CLOSE, self._onClose)
		self.updateSnapshot(pageTitle, addressLabel, summary, items, truncated, savedSignature)
		self.search.SetFocus()

	def updateSnapshot(self, pageTitle, addressLabel, summary, items, truncated, savedSignature):
		"""Replace results after a bounded refresh without recreating the dialog."""
		selected = self.selectedItem()
		if selected is not None:
			self._preferredSelectionSignature = selected.get("signature", "")
		self._allItems = tuple(items)
		self._truncated = bool(truncated)
		self._savedSignature = savedSignature
		self.pageInfo.SetLabel(_("Page: {title}. Address: {address}").format(
			title=pageTitle or _("Untitled page"), address=addressLabel or _("unavailable"),
		))
		self.pageInfo.SetToolTip(summary)
		self._onFilter(None)
		self.copyAddressButton.Enable(bool(addressLabel))
		self.externalButton.Enable(bool(addressLabel) or any(item.get("kind") == "external" for item in self._allItems))
		self.restoreButton.Enable(bool(savedSignature and any(
			item.get("signature") == savedSignature for item in self._allItems
		)))
		self.Layout()

	def setLoading(self):
		self.resultStatus.SetLabel(_("Refreshing accessible browser items…"))
		self.refreshButton.Disable()

	def refreshFinished(self):
		self._onFilter(None)
		self.refreshButton.Enable()

	def selectedItem(self):
		selection = self.results.GetSelection()
		if selection == wx.NOT_FOUND or selection >= len(self._visibleItems):
			return None
		return self._visibleItems[selection]

	def _onFilter(self, evt):
		selected = self.selectedItem()
		if selected is not None:
			self._preferredSelectionSignature = selected.get("signature", "")
		categoryIndex = self.category.GetSelection()
		category = self._CATEGORY_CHOICES[categoryIndex][0] if categoryIndex >= 0 else "all"
		query = self.search.GetValue()
		self._visibleItems = tuple(
			item for item in self._allItems if browserNavigatorMatches(item, category, query)
		)
		self.results.Set([item.get("label", "") for item in self._visibleItems])
		selection = next((
			index for index, item in enumerate(self._visibleItems)
			if item.get("signature") == self._preferredSelectionSignature
		), 0)
		if self._visibleItems:
			self.results.SetSelection(selection)
			self._preferredSelectionSignature = self._visibleItems[selection].get("signature", "")
		status = _("{visible} matching items; {total} total items").format(
			visible=len(self._visibleItems), total=len(self._allItems),
		)
		if self._truncated:
			status += _("; safe scan limit reached")
		self.resultStatus.SetLabel(status)
		self.results.SetName(status)
		self._updateActionState()

	def _updateActionState(self):
		item = self.selectedItem()
		self.moveButton.Enable(item is not None)
		self.activateButton.Enable(bool(item and item.get("actionable")))

	def _onSelectionChanged(self, evt):
		self._updateActionState()
		evt.Skip()

	def _onSearchKey(self, evt):
		if evt.GetKeyCode() in (wx.WXK_DOWN, wx.WXK_UP) and self.results.GetCount():
			self.results.SetFocus()
			self.results.SetSelection(0 if evt.GetKeyCode() == wx.WXK_DOWN else self.results.GetCount() - 1)
			self._updateActionState()
			return
		evt.Skip()

	def _onCharHook(self, evt):
		if evt.GetKeyCode() == wx.WXK_F10 and evt.ShiftDown():
			self._showContextMenu()
			return
		evt.Skip()

	def _onContextMenu(self, evt):
		self._showContextMenu()

	def _showContextMenu(self):
		item = self.selectedItem()
		menu = wx.Menu()
		chosen = []
		if item is not None:
			moveItem = menu.Append(wx.ID_ANY, _("Move to item"))
			menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("move"), moveItem)
			activateItem = menu.Append(wx.ID_ANY, _("Activate item"))
			activateItem.Enable(bool(item.get("actionable")))
			menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("activate"), activateItem)
			menu.AppendSeparator()
		copyItem = menu.Append(wx.ID_ANY, _("Copy page address"))
		copyItem.Enable(self.copyAddressButton.IsEnabled())
		menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("copyAddress"), copyItem)
		externalItem = menu.Append(wx.ID_ANY, _("Open page in default browser"))
		externalItem.Enable(self.externalButton.IsEnabled())
		menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("external"), externalItem)
		returnItem = menu.Append(wx.ID_ANY, _("Return to Claude prompt"))
		menu.Bind(wx.EVT_MENU, lambda evt: chosen.append("returnPrompt"), returnItem)
		try:
			self.PopupMenu(menu)
		finally:
			menu.Destroy()
		if chosen:
			self._perform(chosen[0], pageAction=chosen[0] not in ("move", "activate"))

	def _perform(self, action, pageAction=False):
		if self._closing:
			return
		item = None if pageAction else self.selectedItem()
		if not pageAction and item is None:
			ui.message(_("No matching browser item is selected"))
			return
		if action == "activate" and not item.get("actionable"):
			ui.message(_("The selected browser item does not expose an activate action"))
			return
		self._onActionCallback(action, item)
		if action in self._CLOSE_ACTIONS:
			self.Close()

	def _onRefresh(self, evt):
		if self._closing:
			return
		self.setLoading()
		self._onRefreshCallback()

	def _onClose(self, evt):
		if self._closing:
			return
		self._closing = True
		self.Hide()
		self.Destroy()
		self._onCloseCallback()
