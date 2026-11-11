"""Application-scoped commands for the Claude desktop app."""

import addonHandler
import api
import appModuleHandler
import textInfos
import ui
from editableText import EditableText
from scriptHandler import isScriptWaiting, script, willSayAllResume


addonHandler.initTranslation()


def _activeToolkitPlugin():
	"""Return the running toolkit instance without creating another global plugin."""
	try:
		from globalPlugins import claudeDesktopAccess
		return claudeDesktopAccess._activePluginInstance
	except Exception:
		return None


class ClaudeComposer:
	"""Report text replaced by Claude while NVDA handles a native arrow key."""

	def _readComposerText(self):
		try:
			return self.makeTextInfo(textInfos.POSITION_ALL).text.strip()
		except Exception:
			return None

	def _caretMovementScriptHelper(self, gesture, unit):
		from globalPlugins.claudeDesktopAccess.claudeAdapter import isCodeDocument, isComposerArrowGestureIdentifier

		# Other arrow gestures still use NVDA's standard line and selection handling.
		if unit != textInfos.UNIT_LINE or not any(
			isComposerArrowGestureIdentifier(identifier) for identifier in gesture.identifiers
		):
			return super()._caretMovementScriptHelper(gesture, unit)
		try:
			root = getattr(getattr(self, "treeInterceptor", None), "rootNVDAObject", None)
			before = self._readComposerText() if isCodeDocument(root) else None
		except Exception:
			# The Chromium document can disappear while focus is changing.
			before = None
		if before is None:
			return super()._caretMovementScriptHelper(gesture, unit)
		self._claudeTextBeforeArrow = before
		try:
			return super()._caretMovementScriptHelper(gesture, unit)
		finally:
			self._claudeTextBeforeArrow = None

	def _caretScriptPostMovedHelper(self, speakUnit, gesture, info=None):
		before = getattr(self, "_claudeTextBeforeArrow", None)
		if (
			before is not None and speakUnit == textInfos.UNIT_LINE and self == api.getFocusObject()
			and not isScriptWaiting() and not willSayAllResume(gesture)
		):
			recalled = self._readComposerText()
			if recalled and recalled != before:
				# Keep NVDA's normal caret, review and braille updates.
				super()._caretScriptPostMovedHelper(None, gesture, info)
				ui.message(recalled)
				return
		return super()._caretScriptPostMovedHelper(speakUnit, gesture, info)


class AppModule(appModuleHandler.AppModule):
	"""Expose commands only while Claude or its Code host has focus."""

	scriptCategory = _("Claude Desktop Access")
	__gestures = {
		"kb:control+1": "readMostRecentChatMessage",
		"kb:control+2": "readSecondMostRecentChatMessage",
		"kb:control+3": "readThirdMostRecentChatMessage",
		"kb:control+4": "readFourthMostRecentChatMessage",
		"kb:control+5": "readFifthMostRecentChatMessage",
		"kb:control+6": "readSixthMostRecentChatMessage",
		"kb:control+7": "readSeventhMostRecentChatMessage",
		"kb:control+8": "readEighthMostRecentChatMessage",
		"kb:control+9": "readNinthMostRecentChatMessage",
		"kb:control+0": "readTenthMostRecentChatMessage",
		"kb:NVDA+alt+v": "toggleVoiceMode",
		"kb:NVDA+alt+m": "toggleMicrophoneMute",
		"kb:NVDA+`": "toggleConversationMode",
	}

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if any(issubclass(cls, EditableText) for cls in clsList):
			from globalPlugins.claudeDesktopAccess.claudeAdapter import isNativeComposer

			if isNativeComposer(obj):
				clsList.insert(0, ClaudeComposer)

	def _runToolkitCommand(self, methodName, *args):
		plugin = _activeToolkitPlugin()
		handler = getattr(plugin, methodName, None) if plugin is not None else None
		if not callable(handler):
			ui.message(_("Claude Desktop Access is not ready"))
			return
		handler(*args)

	@script(description=_("Read the most recent Claude message"))
	def script_readMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 1)

	@script(description=_("Read the second-most-recent Claude message"))
	def script_readSecondMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 2)

	@script(description=_("Read the third-most-recent Claude message"))
	def script_readThirdMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 3)

	@script(description=_("Read the fourth-most-recent Claude message"))
	def script_readFourthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 4)

	@script(description=_("Read the fifth-most-recent Claude message"))
	def script_readFifthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 5)

	@script(description=_("Read the sixth-most-recent Claude message"))
	def script_readSixthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 6)

	@script(description=_("Read the seventh-most-recent Claude message"))
	def script_readSeventhMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 7)

	@script(description=_("Read the eighth-most-recent Claude message"))
	def script_readEighthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 8)

	@script(description=_("Read the ninth-most-recent Claude message"))
	def script_readNinthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 9)

	@script(description=_("Read the tenth-most-recent Claude message"))
	def script_readTenthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 10)

	@script(description=_("Start or end Claude voice mode"))
	def script_toggleVoiceMode(self, gesture):
		self._runToolkitCommand("_activateVoiceControl", ("stop", "start"))

	@script(description=_("Mute or unmute the Claude microphone"))
	def script_toggleMicrophoneMute(self, gesture):
		self._runToolkitCommand("_activateVoiceControl", ("unmute", "mute"))

	@script(description=_("Open Claude navigation for modes, artifacts and attachments"))
	def script_toggleConversationMode(self, gesture):
		"""Open the accessible Claude navigation list."""
		self._runToolkitCommand("_openConversationModeSelector")
