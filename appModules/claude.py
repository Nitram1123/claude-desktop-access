"""Application-scoped commands for the Claude desktop app."""

import addonHandler
import appModuleHandler
import ui
from scriptHandler import script

from globalPlugins.claudeDesktopAccess import strings


addonHandler.initTranslation()


def _activeToolkitPlugin():
	"""Return the running toolkit instance without creating another global plugin."""
	try:
		from globalPlugins import claudeDesktopAccess
		return claudeDesktopAccess._activePluginInstance
	except Exception:
		return None


class AppModule(appModuleHandler.AppModule):
	"""Expose commands only while Claude or its Code host has focus."""

	scriptCategory = _(strings.CLAUDE_DESKTOP_ACCESS)
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

	def _runToolkitCommand(self, methodName, *args):
		plugin = _activeToolkitPlugin()
		handler = getattr(plugin, methodName, None) if plugin is not None else None
		if not callable(handler):
			ui.message(_(strings.CLAUDE_DESKTOP_ACCESS_IS_NOT_READY))
			return
		handler(*args)

	@script(description=_(strings.READ_THE_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 1)

	@script(description=_(strings.READ_THE_SECOND_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readSecondMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 2)

	@script(description=_(strings.READ_THE_THIRD_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readThirdMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 3)

	@script(description=_(strings.READ_THE_FOURTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readFourthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 4)

	@script(description=_(strings.READ_THE_FIFTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readFifthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 5)

	@script(description=_(strings.READ_THE_SIXTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readSixthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 6)

	@script(description=_(strings.READ_THE_SEVENTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readSeventhMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 7)

	@script(description=_(strings.READ_THE_EIGHTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readEighthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 8)

	@script(description=_(strings.READ_THE_NINTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readNinthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 9)

	@script(description=_(strings.READ_THE_TENTH_MOST_RECENT_CLAUDE_MESSAGE))
	def script_readTenthMostRecentChatMessage(self, gesture):
		self._runToolkitCommand("_readRecentChatMessage", 10)

	@script(description=_(strings.START_OR_END_CLAUDE_VOICE_MODE))
	def script_toggleVoiceMode(self, gesture):
		self._runToolkitCommand("_activateVoiceControl", ("stop", "start"))

	@script(description=_(strings.MUTE_OR_UNMUTE_THE_CLAUDE_MICROPHONE))
	def script_toggleMicrophoneMute(self, gesture):
		self._runToolkitCommand("_activateVoiceControl", ("unmute", "mute"))

	@script(description=_(strings.OPEN_CLAUDE_NAVIGATION_FOR_MODES_ARTIFACTS_AND_ATTACHMENTS))
	def script_toggleConversationMode(self, gesture):
		"""Open the accessible Claude navigation list."""
		self._runToolkitCommand("_openConversationModeSelector")
