"""Provide accessible feedback and navigation for the Claude desktop app."""

import os
import json
import re
import time
from pathlib import Path

import addonHandler
import api
import braille
import config
import globalPluginHandler
import gui
import inputCore
import keyboardHandler
import queueHandler
import speech
import textInfos
import ui
import versionInfo
import winUser
import wx
from controlTypes import Role, State
from gui import guiHelper
from gui.settingsDialogs import NVDASettingsDialog, SettingsPanel
from logHandler import log
from scriptHandler import script

from .browserAccess import (
	browserAddressDomain, browserNavigatorCategory, browserNavigatorItemLabel,
	browserNavigatorSignature, browserPageAddress, browserPageIdentity, browserPageSummary,
	browserSnapshotLine, browserSnapshotText, embeddedBrowserControlKind,
	embeddedBrowserProgress, embeddedBrowserTitle, isEmbeddedBrowserContainerRole,
	isEmbeddedBrowserContainerText, isEmbeddedBrowserDocumentStructure,
)
from .browserNavigatorDialog import BrowserNavigatorDialog
from .chatHistoryDialog import ChatHistoryDialog
from .core import AnnouncementHistory, CATEGORY_SETTING, announcementPriority, backgroundActivityName, brailleStatusMessage, brailleTypingGestureCommitsText, bufferInspectionDue, categoryOutputActions, changelogForDisplay, chatActionMatches, chatHistorySnapshotDecision, chatMessagesFromTokens, chatTitleMatches, coalescedPollDelay, completedTextDelta, confirmedUserMessageSubmission, conversationModeFromDocumentNames, conversationModeFromSwitchLabel, conversationWindowShouldDetach, currentActivitySummary, duplicateChannelActions, elapsedSeconds, firstStatusLabel, focusStateTransition, formatCommandSpeech, formatCustomAnnouncement, formatElapsedDuration, intermediateCompletionCategory, isBrailleTypingGestureIdentifier, isChatHistoryConversationBoundary, isChatHistoryInterfaceText, isCodePromptLabel, isKnownNonStatusButton, isPermissionDecisionLabel, isPermissionPromptText, isPromptSubmissionGestureIdentifier, isResponseCompletionMarkerText, isStopControlLabel, isTaskCompletionLabel, looksLikeBlankCodeConversation, mergeSupportedAppNames, modeSpecificRecentChatTitles, nextBusyState, outputActions, pendingChatTitle, pluginInstallProgress, pluginProgressBusyTransition, pollDelay, previewSelection, promptControlKind, promptSubmissionGestureShouldStart, promptSubmissionTransition, redactSensitive, repairConfigurationValues, responseCompletionScanMarker, responseCompletionTransition, shouldFinalizeResponseCompletion, shouldLogDiagnosticSnapshot, shouldPreserveBrailleComposition, shouldReplaceScheduledPoll, shouldSuppressNativeConversationUpdate, shouldSuppressRoutineBraille, shouldSuppressSemanticDuplicate, soundKey, statusDetails, statusMessage, stopControlTransition, supersedesResponseCompletionCandidate, usageLimitNotice, userMessageNumber, userMessageSubmissionTransition, viewerTitleMatches
from .core import voiceControlKind
from .claudeAdapter import modeDisplayName, speakerFromLabel, modeFromTab, promptLabel, navigationKind, conversationDocumentMode, messageTokens
from .bufferUpdates import BufferUpdateObserver
from .claudeAdapter import (
	codeDocumentUrl, codeFeedTaskProgress, isCodeDocument, isCodeTaskFeed,
	isNativeComposer, isTaskTimerObject, nativeCodeFeedTaskProgress,
)
from .claudeNavigator import ClaudeNavigator, NavigationScan
from .soundOutput import playProgressSound as _playProgressSound, safeBeep as _safeBeep

addonHandler.initTranslation()

CONFIG_SECTION = "claudeDesktopAccess"
ADDON_VERSION = "2026.2.2"
CLAUDE_USAGE_URL = "https://claude.ai/settings/usage"
DEFAULT_SUPPORTED_APP_NAMES = "claude"
CURRENT_RELEASE_NOTES = _(
    "Claude Desktop Access 2026.2.2 — beta bug fixes\n\n"
    "• Read aloud and ordinary links or sidebar titles no longer count as activity.\n"
    "• Completed tool output no longer prevents the response-completion settling timer from starting.\n"
    "• When generation resumes, completion waits for a fresh quiet interval.\n"
    "• Unchanged chat history no longer schedules repeated confirmation scans.\n"
    "This update targets stable NVDA 2026.2. Live beta testing remains ongoing."
)
VERBOSITY_CHOICES = ("minimal", "full")
FULL_SPEECH_PROFILE_CHOICES = ("standard", "developer", "raw")
MINIMAL_SPEECH_PROFILE_CHOICES = ("essential", "balanced", "informative")
BRAILLE_DETAIL_CHOICES = ("concise", "informative", "full")
SOUND_STYLE_CHOICES = ("clicks", "tones")
CLICK_VOLUME_CHOICES = ("soft", "normal", "loud")
COMMAND_PUNCTUATION_CHOICES = ("normal", "enhanced", "literal")
OUTPUT_MODE_CHOICES = ("all", "speech", "sound", "braille", "off")
CATEGORY_OUTPUT_CONFIG = {
	"thinking": "outputThinking", "working": "outputWorking", "command": "outputCommands",
	"search": "outputSearches", "file": "outputFiles", "build": "outputBuilds",
	"tool": "outputTools", "completion": "outputCompletions", "attention": "outputAttention",
	"other": "outputOther", "commentary": "outputCommentary",
}
PREVIEW_ITEMS = (
	("thinking", "announcementThinking", _("Thinking"), _("Thinking")),
	("working", "announcementWorking", _("Working"), _("Working")),
	("command", "announcementCommand", _("Command"), _("Running command")),
	("search", "announcementSearch", _("Search"), _("Searching the web")),
	("file", "announcementFile", _("File"), _("Editing file")),
	("build", "announcementBuild", _("Build and test"), _("Running tests")),
	("tool", "announcementTool", _("Tool"), _("Using tool")),
	("commentary", "announcementCommentary", _("Commentary"), _("I am inspecting the current task.")),
	("backgroundPulse1", "announcementPulse1", _("Background progress one"), _("Command still running, 5 seconds")),
	("backgroundPulse2", "announcementPulse2", _("Background progress two"), _("Command still running, 10 seconds")),
	("completion", "announcementCompletion", _("Completion"), _("Command finished")),
	("completion", "announcementFailure", _("Failure"), _("Command failed")),
	("attention", "announcementAttention", _("Permission required"), _("Permission required")),
	("other", "announcementOther", _("Other progress"), _("Waiting")),
	("monitoringActive", "announcementMonitoringActive", _("Monitoring active"), _("Activity monitoring active")),
	("monitoringInactive", "announcementMonitoringInactive", _("Monitoring inactive"), _("Activity monitoring inactive")),
	("submission", "announcementSubmission", _("Prompt submitted"), _("Prompt submitted")),
)
ANNOUNCEMENT_CONFIG_BY_ACTION = {item[0]: item[1] for item in PREVIEW_ITEMS if item[0] != "completion"}
ANNOUNCEMENT_CONFIG_BY_ACTION.update({"completion": "announcementCompletion", "failure": "announcementFailure"})
RESPONSE_COMPLETION_SETTLE_SECONDS = 5.0
PROMPT_TYPING_QUIET_SECONDS = 1.25
CONVERSATION_NAVIGATION_QUIET_SECONDS = 3.0
CONVERSATION_WINDOW_CLOSE_GRACE_SECONDS = 2.0
CHAT_HISTORY_MODE_SETTLE_SECONDS = 0.75
CHAT_HISTORY_SNAPSHOT_CONFIRM_SECONDS = 0.25
CHAT_HISTORY_RETRY_MILLISECONDS = 300
CHAT_HISTORY_EXPANSION_DELAY_MILLISECONDS = 700
CHAT_HISTORY_EXPANSION_RETRY_MILLISECONDS = 300
CHAT_HISTORY_EXPANSION_MAX_PAGES = 20
CHAT_HISTORY_EXPANSION_MAX_STALE_SCANS = 30
BUFFER_TAIL_SCAN_CHARACTERS = 8192
MODE_CONTROL_RETRY_SECONDS = 5.0
PROMPT_INSPECTION_DELAY_MS = 250
BRAILLE_CARET_GRACE_SECONDS = 1.0
BROWSER_LOAD_SETTLE_MILLISECONDS = 1500
BROWSER_BUSY_FALLBACK_MILLISECONDS = 30000
BROWSER_SCAN_SLICE_OBJECTS = 20
BROWSER_SCAN_SLICE_SECONDS = 0.008
BROWSER_SCAN_YIELD_MILLISECONDS = 15
BROWSER_SCAN_MAX_OBJECTS = 900
BROWSER_SCAN_MAX_ITEMS = 500
BROWSER_SNAPSHOT_MAX_LINES = 700
VOICE_CONTROL_SEARCH_LABELS = (
	("stop", "Stop voice chat"),
	("stop", "End voice chat"),
	("stop", "Leave voice mode"),
	("stop", "Exit voice mode"),
	("start", "Start voice chat"),
	("start", "Start voice mode"),
	("unmute", "Unmute microphone"),
	("unmute", "Unmute mic"),
	("mute", "Mute microphone"),
	("mute", "Mute mic"),
)
VOICE_CONTROL_CONFIRMATION_DELAY_MS = 500
VOICE_CONTROL_CONFIRMATION_ATTEMPTS = 2
APP_SCOPED_SCRIPT_NAMES = (
	"readMostRecentChatMessage", "readSecondMostRecentChatMessage",
	"readThirdMostRecentChatMessage", "readFourthMostRecentChatMessage",
	"readFifthMostRecentChatMessage", "readSixthMostRecentChatMessage",
	"readSeventhMostRecentChatMessage", "readEighthMostRecentChatMessage",
	"readNinthMostRecentChatMessage", "readTenthMostRecentChatMessage",
	"toggleVoiceMode", "toggleMicrophoneMute", "toggleConversationMode",
)
APP_SCOPED_DEFAULT_GESTURES = (
	"kb:control+1", "kb:control+2", "kb:control+3", "kb:control+4", "kb:control+5",
	"kb:control+6", "kb:control+7", "kb:control+8", "kb:control+9", "kb:control+0",
	"kb:NVDA+alt+v", "kb:NVDA+alt+m", "kb:NVDA+`",
)
_lastConfigurationRepairs = ()
_activePluginInstance = None
config.conf.spec[CONFIG_SECTION] = {
	"verbosity": "option('minimal', 'full', default='full')",
	"fullSpeechProfile": "option('standard', 'developer', 'raw', default='developer')",
	"minimalSpeechProfile": "option('essential', 'balanced', 'informative', default='balanced')",
	"commandPunctuation": "option('normal', 'enhanced', 'literal', default='enhanced')",
	"maximumSpokenCommandCharacters": "integer(default=240, min=40, max=2000)",
	"speech": "boolean(default=True)",
	"braille": "boolean(default=True)",
	"brailleDetail": "option('concise', 'informative', 'full', default='full')",
	"protectBrailleReading": "boolean(default=True)",
	"interruptUrgentSpeech": "boolean(default=True)",
	"redactSensitive": "boolean(default=False)",
	"workingIntervalSeconds": "integer(default=5, min=1, max=300)",
	"idlePollMs": "integer(default=500, min=100, max=5000)",
	"completionSound": "boolean(default=False)",
	"soundWhenSpeechUnavailable": "boolean(default=True)",
	"progressSoundStyle": "option('clicks', 'tones', default='clicks')",
	"clickVolume": "option('soft', 'normal', 'loud', default='normal')",
	"continuousWorkingClicks": "boolean(default=True)",
	"workingClickIntervalMs": "integer(default=1400, min=500, max=5000)",
	"workingClickStartDelayMs": "integer(default=750, min=0, max=10000)",
	"announceHeartbeat": "boolean(default=True)",
	"promptSubmissionClick": "boolean(default=True)",
	"monitoringFocusClicks": "boolean(default=True)",
	"maximumBusyMinutes": "integer(default=60, min=1, max=240)",
	"welcomeShown": "boolean(default=False)",
	"lastShownVersion": "string(default='')",
	"supportedAppNames": "string(default='claude')",
	"diagnosticLogging": "boolean(default=False)",
	"announceEmbeddedBrowserProgress": "boolean(default=True)",
	"announceThinking": "boolean(default=True)",
	"announceWorking": "boolean(default=True)",
	"announceCommands": "boolean(default=True)",
	"announceSearches": "boolean(default=True)",
	"announceFiles": "boolean(default=True)",
	"announceBuilds": "boolean(default=True)",
	"announceTools": "boolean(default=True)",
	"announceCompletions": "boolean(default=True)",
	"announceOther": "boolean(default=True)",
	"announceCommentary": "boolean(default=True)",
	"announceAttention": "boolean(default=True)",
	"outputThinking": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputWorking": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputCommands": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputSearches": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputFiles": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputBuilds": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputTools": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputCompletions": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputAttention": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputOther": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"outputCommentary": "option('all', 'speech', 'sound', 'braille', 'off', default='all')",
	"announcementThinking": "string(default='')",
	"announcementWorking": "string(default='')",
	"announcementCommand": "string(default='')",
	"announcementSearch": "string(default='')",
	"announcementFile": "string(default='')",
	"announcementBuild": "string(default='')",
	"announcementTool": "string(default='')",
	"announcementCommentary": "string(default='')",
	"announcementPulse1": "string(default='')",
	"announcementPulse2": "string(default='')",
	"announcementCompletion": "string(default='')",
	"announcementFailure": "string(default='')",
	"announcementAttention": "string(default='')",
	"announcementOther": "string(default='')",
	"announcementMonitoringActive": "string(default='')",
	"announcementMonitoringInactive": "string(default='')",
	"announcementSubmission": "string(default='')",
}


def _settings():
	return config.conf[CONFIG_SECTION]


def _repairConfiguration():
	"""Repair migrated choice and numeric values without discarding valid preferences."""
	global _lastConfigurationRepairs
	conf = _settings()
	choiceDefaults = {
		"verbosity": (VERBOSITY_CHOICES, "full"),
		"fullSpeechProfile": (FULL_SPEECH_PROFILE_CHOICES, "developer"),
		"minimalSpeechProfile": (MINIMAL_SPEECH_PROFILE_CHOICES, "balanced"),
		"brailleDetail": (BRAILLE_DETAIL_CHOICES, "full"),
		"commandPunctuation": (COMMAND_PUNCTUATION_CHOICES, "enhanced"),
		"progressSoundStyle": (SOUND_STYLE_CHOICES, "clicks"),
		"clickVolume": (CLICK_VOLUME_CHOICES, "normal"),
	}
	for key in CATEGORY_OUTPUT_CONFIG.values():
		choiceDefaults[key] = (OUTPUT_MODE_CHOICES, "all")
	numericDefaults = {
		"maximumSpokenCommandCharacters": (40, 2000, 240),
		"workingIntervalSeconds": (1, 300, 5),
		"idlePollMs": (100, 5000, 500),
		"workingClickIntervalMs": (500, 5000, 1400),
		"workingClickStartDelayMs": (0, 10000, 750),
		"maximumBusyMinutes": (1, 240, 60),
	}
	booleanKeys = tuple((key, default) for key, default in {
		"speech": True, "braille": True, "protectBrailleReading": True,
		"interruptUrgentSpeech": True, "redactSensitive": False,
		"completionSound": False, "soundWhenSpeechUnavailable": True,
		"continuousWorkingClicks": True, "promptSubmissionClick": True, "announceHeartbeat": True,
		"monitoringFocusClicks": True, "welcomeShown": False,
		"diagnosticLogging": False,
		"announceEmbeddedBrowserProgress": True, "announceThinking": True,
		"announceWorking": True, "announceCommands": True,
		"announceSearches": True, "announceFiles": True,
		"announceBuilds": True, "announceTools": True,
		"announceCompletions": True, "announceOther": True,
		"announceCommentary": True,
		"announceAttention": True,
	}.items())
	repaired = repairConfigurationValues(
		conf, choiceDefaults, numericDefaults, booleanKeys,
		(("supportedAppNames", DEFAULT_SUPPORTED_APP_NAMES), ("lastShownVersion", "")),
	)
	mergedAppNames = mergeSupportedAppNames(conf["supportedAppNames"])
	if conf["supportedAppNames"] != mergedAppNames:
		conf["supportedAppNames"] = mergedAppNames
		repaired = tuple(dict.fromkeys((*repaired, "supportedAppNames")))
	if repaired:
		log.warning("Claude Desktop Access repaired configuration fields: %s", ", ".join(repaired))
	_lastConfigurationRepairs = repaired
	return tuple(repaired)


def _migrateApplicationGestureMappings():
	"""A new add-on must never migrate another product's gesture assignments."""
	return False


def _customizeAnnouncement(message, action, activity="", seconds=0, values=None):
	conf = values or _settings()
	key = ANNOUNCEMENT_CONFIG_BY_ACTION.get(action)
	return formatCustomAnnouncement(conf.get(key, "") if key else "", message, activity, seconds)


def _speechIsOff():
	try:
		return speech.getState().speechMode == speech.SpeechMode.off
	except Exception:
		log.debugWarning("Claude Desktop Access could not read NVDA's speech mode", exc_info=True)
		return False


def _send(message, speak=True, showBraille=True, toneCategory=None, progressSoundsEnabled=True, soundStyle=None, clickVolume=None, priority="normal", brailleMessage=None, interruptUrgent=None):
	actions = outputActions(speak, _speechIsOff(), showBraille, progressSoundsEnabled, toneCategory)
	if actions["speech"]:
		if interruptUrgent is None:
			interruptUrgent = _settings()["interruptUrgentSpeech"]
		if priority == "urgent" and interruptUrgent:
			try:
				speech.cancelSpeech()
			except Exception:
				log.debugWarning("Claude Desktop Access could not cancel speech for an urgent message", exc_info=True)
		try:
			speech.speakMessage(message)
		except Exception:
			log.debugWarning("Claude Desktop Access speech output failed", exc_info=True)
	if actions["braille"]:
		try:
			braille.handler.message(message if brailleMessage is None else brailleMessage)
		except Exception:
			log.debugWarning("Claude Desktop Access Braille output failed", exc_info=True)
	if actions["tone"]:
		try:
			_playProgressSound(
				toneCategory, message, soundStyle or _settings()["progressSoundStyle"],
				clickVolume or _settings()["clickVolume"],
			)
			return True
		except Exception:
			log.debugWarning("Claude Desktop Access progress sound output failed", exc_info=True)
	return False


def _moveBrowseableMessageToTop(expectedTitle):
	try:
		foreground = api.getForegroundObject()
		foregroundName = str(getattr(foreground, "name", "") or "")
		if not viewerTitleMatches(expectedTitle, foregroundName):
			log.debug("Claude Desktop Access did not move document focus; expected viewer is not foreground")
			return
		keyboardHandler.KeyboardInputGesture.fromName("control+home").send()
	except Exception:
		log.debugWarning("Claude Desktop Access could not move the document viewer to the top", exc_info=True)


def _showBrowseableMessageAtTop(message, title):
	ui.browseableMessage(message, title=title, closeButton=True)
	wx.CallLater(350, _moveBrowseableMessageToTop, title)


def _completeChangelogMessage():
	changelogPath = Path(addonHandler.getCodeAddon().path) / "changelog.md"
	return changelogForDisplay(changelogPath.read_text(encoding="utf-8"))


def _saveSupportReport(parent, diagnosticReport):
	"""Let the user choose where to save a sanitized support report."""
	defaultName = "claude-desktop-access-support-{timestamp}.txt".format(
		timestamp=time.strftime("%Y%m%d-%H%M%S"),
	)
	with wx.FileDialog(
		parent,
		_("Save sanitized Claude Desktop Access support report"),
		defaultFile=defaultName,
		wildcard=_("Text files (*.txt)|*.txt"),
		style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
	) as dialog:
		if dialog.ShowModal() != wx.ID_OK:
			return False
		path = Path(dialog.GetPath())
	payload = _(
		"Claude Desktop Access sanitized support report\n"
		"Generated: {generated}\nNVDA version: {nvdaVersion}\n\n{report}\n"
	).format(
		generated=time.strftime("%Y-%m-%d %H:%M:%S %z"),
		nvdaVersion=getattr(versionInfo, "version", "unknown"),
		report=diagnosticReport,
	)
	try:
		path.write_text(payload, encoding="utf-8")
	except Exception:
		log.error("Unable to save Claude Desktop Access support report", exc_info=True)
		ui.message(_("The sanitized support report could not be saved"))
		return False
	ui.message(_("Sanitized Claude Desktop Access support report saved"))
	return True


def _openUsageDashboard(message):
	try:
		opened = wx.LaunchDefaultBrowser(CLAUDE_USAGE_URL)
	except Exception:
		log.error("Unable to open Claude usage settings", exc_info=True)
		opened = False
	ui.message(message if opened else _("Claude usage settings could not be opened"))


class ClaudeDesktopAccessSettingsPanel(SettingsPanel):
	title = _("Claude Desktop Access")

	def _addPage(self, title):
		page = wx.Panel(self.notebook)
		sizer = wx.BoxSizer(wx.VERTICAL)
		page.SetSizer(sizer)
		self.notebook.AddPage(page, title)
		return page, guiHelper.BoxSizerHelper(page, sizer=sizer)

	def makeSettings(self, settingsSizer):
		conf = _settings()
		self.notebook = wx.Notebook(self)
		settingsSizer.Add(self.notebook, proportion=1, flag=wx.EXPAND)

		generalPage, helper = self._addPage(_("General"))
		helper.addItem(wx.StaticText(generalPage, label=_(
			"Settings are organized into pages. Press Control+Tab or Shift+Control+Tab to change pages. "
			"Select Apply or OK to save changes."
		)))
		self.verbosity = helper.addLabeledControl(_("Announcement &detail:"), wx.Choice, choices=[
			_("Minimal — brief activity summaries"),
			_("Full — complete progress labels and commands"),
		])
		self.verbosity.SetSelection(VERBOSITY_CHOICES.index(conf["verbosity"]))
		self.speech = helper.addItem(wx.CheckBox(generalPage, label=_("Enable &speech announcements")))
		self.braille = helper.addItem(wx.CheckBox(generalPage, label=_("Enable &braille flash messages")))
		self.redactSensitive = helper.addItem(wx.CheckBox(
			generalPage, label=_("&Redact likely secrets and personal path names in Full mode"),
		))
		for name in ("speech", "braille", "redactSensitive"):
			getattr(self, name).SetValue(conf[name])
		self.testButton = helper.addItem(wx.Button(generalPage, label=_("Test current announcement outputs (&T)")))
		self.testButton.Bind(wx.EVT_BUTTON, self._onTest)

		speechPage, helper = self._addPage(_("Speech and Braille"))
		self.fullSpeechProfile = helper.addLabeledControl(
			_("&Full speech profile:"), wx.Choice,
			choices=[
				_("Standard — action, target, counts, and useful timing"),
				_("Developer — complete normalized commands and progress"),
				_("Raw — exact exposed Claude progress text"),
			],
		)
		self.fullSpeechProfile.SetSelection(FULL_SPEECH_PROFILE_CHOICES.index(conf["fullSpeechProfile"]))
		self.minimalSpeechProfile = helper.addLabeledControl(
			_("&Minimal speech profile:"), wx.Choice,
			choices=[
				_("Essential — thinking, attention, failures, and task completion"),
				_("Balanced — concise activity changes and results"),
				_("Informative — Balanced plus filenames, counts, and timing"),
			],
		)
		self.minimalSpeechProfile.SetSelection(MINIMAL_SPEECH_PROFILE_CHOICES.index(conf["minimalSpeechProfile"]))
		self.commandPunctuation = helper.addLabeledControl(
			_("Command &punctuation for speech:"), wx.Choice,
			choices=[_("Normal"), _("Enhanced — speak pipes and redirects naturally"), _("Literal — name command symbols")],
		)
		self.commandPunctuation.SetSelection(COMMAND_PUNCTUATION_CHOICES.index(conf["commandPunctuation"]))
		self.maximumSpokenCommandCharacters = helper.addLabeledControl(
			_("Maximum spoken command &length:"), wx.SpinCtrl,
			min=40, max=2000, initial=conf["maximumSpokenCommandCharacters"],
		)
		self.brailleDetail = helper.addLabeledControl(
			_("Braille &detail:"), wx.Choice,
			choices=[_("Concise"), _("Informative"), _("Full — complete commands and progress")],
		)
		self.brailleDetail.SetSelection(BRAILLE_DETAIL_CHOICES.index(conf["brailleDetail"]))
		self.protectBrailleReading = helper.addItem(wx.CheckBox(
			speechPage, label=_("Keep &conversation reading stable for speech and Braille during live updates"),
		))
		self.protectBrailleReading.SetValue(conf["protectBrailleReading"])
		self.interruptUrgentSpeech = helper.addItem(wx.CheckBox(
			speechPage, label=_("Allow &urgent permission and failure announcements to interrupt current speech"),
		))
		self.interruptUrgentSpeech.SetValue(conf["interruptUrgentSpeech"])
		self.resetSpeechSettings = helper.addItem(wx.Button(speechPage, label=_("&Reset speech profile settings")))
		self.resetSpeechSettings.Bind(wx.EVT_BUTTON, self._onResetSpeechSettings)

		soundsPage, helper = self._addPage(_("Sounds"))
		self.completionSound = helper.addItem(wx.CheckBox(soundsPage, label=_("Play a sound for task &completion or failure")))
		self.progressSounds = helper.addItem(
			wx.CheckBox(soundsPage, label=_("Play &progress sounds for enabled announcements")),
		)
		self.progressSoundStyle = helper.addLabeledControl(
			_("Progress sound style (&J):"), wx.Choice,
			choices=[_("Clicks — soft percussive earcons"), _("Tones — musical earcons")],
		)
		self.progressSoundStyle.SetSelection(SOUND_STYLE_CHOICES.index(conf["progressSoundStyle"]))
		self.clickVolume = helper.addLabeledControl(
			_("Click volume (&Z):"), wx.Choice,
			choices=[_("Soft"), _("Normal"), _("Loud")],
		)
		self.clickVolume.SetSelection(CLICK_VOLUME_CHOICES.index(conf["clickVolume"]))
		self.continuousWorkingClicks = helper.addItem(wx.CheckBox(
			soundsPage, label=_("Play a recurring &Working sound while Claude Code is working"),
		))
		self.continuousWorkingClicks.SetValue(conf["continuousWorkingClicks"])
		self.workingClickIntervalMs = helper.addLabeledControl(
			_("Working sound &interval (milliseconds):"), wx.SpinCtrl,
			min=500, max=5000, initial=conf["workingClickIntervalMs"],
		)
		self.workingClickStartDelayMs = helper.addLabeledControl(
			_("&Delay before repeating Working sounds (milliseconds):"), wx.SpinCtrl,
			min=0, max=10000, initial=conf["workingClickStartDelayMs"],
		)
		self.promptSubmissionClick = helper.addItem(wx.CheckBox(
			soundsPage, label=_("Play a distinct sound when a prompt is &submitted"),
		))
		self.promptSubmissionClick.SetValue(conf["promptSubmissionClick"])
		self.monitoringFocusClicks = helper.addItem(wx.CheckBox(
			soundsPage, label=_("Play sounds when Claude &monitoring becomes active or inactive"),
		))
		self.monitoringFocusClicks.SetValue(conf["monitoringFocusClicks"])
		self.completionSound.SetValue(conf["completionSound"])
		self.progressSounds.SetValue(conf["soundWhenSpeechUnavailable"])
		self.testSoundButton = helper.addItem(wx.Button(soundsPage, label=_("Test command progress sound (&K)")))
		self.testSoundButton.Bind(wx.EVT_BUTTON, self._onTestSound)

		activityPage, helper = self._addPage(_("Activity Output"))
		helper.addItem(wx.StaticText(activityPage, label=_(
			"Choose an activity category to review its enabled state and output route."
		)))
		self.workingIntervalSeconds = helper.addLabeledControl(
			_("Progress announcement &interval (seconds):"), wx.SpinCtrl,
			min=1, max=300, initial=conf["workingIntervalSeconds"],
		)
		self.maximumBusyMinutes = helper.addLabeledControl(
			_("Maximum background activity (&minutes):"), wx.SpinCtrl,
			min=1, max=240, initial=conf["maximumBusyMinutes"],
		)
		self.announceHeartbeat = helper.addItem(wx.CheckBox(
			activityPage, label=_("Announce a recurring progress &pulse while Claude Code is working"),
		))
		self.announceHeartbeat.SetValue(conf["announceHeartbeat"])
		self._activityCategories = (
			("announceThinking", "thinking", _("Thinking")),
			("announceWorking", "working", _("Working and analysis")),
			("announceCommands", "command", _("Commands")),
			("announceSearches", "search", _("Web searches")),
			("announceFiles", "file", _("File activity")),
			("announceBuilds", "build", _("Builds, compilation, and tests")),
			("announceTools", "tool", _("Tool use")),
			("announceCompletions", "completion", _("Completions and failures")),
			("announceAttention", "attention", _("Permission and input requests")),
			("announceOther", "other", _("Other recognized progress")),
			("announceCommentary", "commentary", _("Plain-language commentary")),
		)
		self._categoryEnabledValues = {key: bool(conf[key]) for key, category, label in self._activityCategories}
		self._categoryOutputValues = {
			category: str(conf[CATEGORY_OUTPUT_CONFIG[category]])
			for key, category, label in self._activityCategories
		}
		self._outputModeLabels = (
			_("all enabled channels"), _("speech only"), _("sound only"), _("braille only"), _("off"),
		)
		self.activityCategory = helper.addLabeledControl(
			_("Activity &category:"), wx.Choice,
			choices=[self._activityCategoryDisplay(index) for index in range(len(self._activityCategories))],
		)
		self.activityCategory.SetSelection(0)
		self.activityEnabled = helper.addItem(wx.CheckBox(activityPage, label=_("&Enable this activity category")))
		self.activityOutput = helper.addLabeledControl(
			_("Output &route for this category:"), wx.Choice,
			choices=[_("All enabled channels"), _("Speech only"), _("Sound only"), _("Braille only"), _("Off")],
		)
		self._activityCategorySelection = 0
		self._loadActivityCategory(0)
		self.activityCategory.Bind(wx.EVT_CHOICE, self._onActivityCategoryChanged)
		self.activityEnabled.Bind(wx.EVT_CHECKBOX, self._onActivitySettingChanged)
		self.activityOutput.Bind(wx.EVT_CHOICE, self._onActivitySettingChanged)

		wordingPage, helper = self._addPage(_("Wording and Preview"))
		self.previewItem = helper.addLabeledControl(
			_("Preview action (&V):"), wx.Choice,
			choices=[label for category, key, label, message in PREVIEW_ITEMS],
		)
		self.previewItem.SetSelection(0)
		self._announcementEdits = {key: str(conf[key]) for category, key, label, message in PREVIEW_ITEMS}
		self.previewItem.Bind(wx.EVT_CHOICE, self._onPreviewItemChanged)
		self.announcementText = helper.addLabeledControl(
			_("Announcement &text (blank uses built-in):"), wx.TextCtrl,
		)
		self.announcementText.SetValue(self._announcementEdits[PREVIEW_ITEMS[0][1]])
		self.restoreAnnouncementButton = helper.addItem(wx.Button(wordingPage, label=_("&Restore built-in announcement")))
		self.restoreAnnouncementButton.Bind(wx.EVT_BUTTON, self._onRestoreAnnouncement)
		helper.addItem(wx.StaticText(wordingPage, label=_(
			"Available placeholders: {message}, {activity}, {seconds}, and {duration}."
		)))
		self.previewSoundButton = helper.addItem(wx.Button(wordingPage, label=_("Preview selected &sound")))
		self.previewSoundButton.Bind(wx.EVT_BUTTON, self._onPreviewSelectedSound)
		self.previewSpeechButton = helper.addItem(wx.Button(wordingPage, label=_("Preview selected s&peech")))
		self.previewSpeechButton.Bind(wx.EVT_BUTTON, self._onPreviewSelectedSpeech)

		browserPage, helper = self._addPage(_("Browser Access"))
		helper.addItem(wx.StaticText(browserPage, label=_(
			"Use Claude's embedded browser like any other web page in NVDA. Enter or Space activates the current control. Tab and Shift+Tab move between controls. NVDA browse-mode commands work normally."
		)))
		self.announceEmbeddedBrowserProgress = helper.addItem(wx.CheckBox(
			browserPage, label=_("Announce when embedded browser pages start and finish &loading"),
		))
		self.announceEmbeddedBrowserProgress.SetValue(conf["announceEmbeddedBrowserProgress"])

		advancedPage, helper = self._addPage(_("Advanced"))
		self.idlePollMs = helper.addLabeledControl(
			_("Idle compatibility &polling interval (milliseconds):"), wx.SpinCtrl,
			min=100, max=5000, initial=conf["idlePollMs"],
		)
		self.supportedAppNames = helper.addLabeledControl(
			_("Supported application &names, comma separated:"), wx.TextCtrl,
		)
		self.supportedAppNames.SetValue(conf["supportedAppNames"])
		self.diagnosticLogging = helper.addItem(wx.CheckBox(
			advancedPage, label=_("Enable sanitized dia&gnostic logging"),
		))
		self.diagnosticLogging.SetValue(conf["diagnosticLogging"])
		helper.addItem(wx.StaticText(advancedPage, label=_(
			"Warning: NVDA debug logging records spoken Full-mode text, including commands, even when add-on diagnostics are sanitized."
		)))

		supportPage, helper = self._addPage(_("Support"))
		helper.addItem(wx.StaticText(supportPage, label=_(
			"Open help and account pages, save sanitized troubleshooting information, or transfer add-on settings."
		)))
		self.checkUsageButton = helper.addItem(wx.Button(supportPage, label=_("&Open Claude usage settings")))
		self.checkUsageButton.Bind(wx.EVT_BUTTON, self._onCheckUsage)
		self.buyCreditsButton = helper.addItem(wx.Button(supportPage, label=_("&Claude help and account information")))
		self.buyCreditsButton.Bind(wx.EVT_BUTTON, self._onBuyCredits)
		self.viewCurrentRelease = helper.addItem(wx.Button(supportPage, label=_("View current release &notes…")))
		self.viewCurrentRelease.Bind(wx.EVT_BUTTON, self._onViewCurrentRelease)
		self.viewCompleteHistory = helper.addItem(wx.Button(supportPage, label=_("View complete release &history…")))
		self.viewCompleteHistory.Bind(wx.EVT_BUTTON, self._onViewCompleteHistory)
		self.saveSupportReport = helper.addItem(wx.Button(supportPage, label=_("Save sanitized support &report…")))
		self.saveSupportReport.Bind(wx.EVT_BUTTON, self._onSaveSupportReport)
		self.exportSettings = helper.addItem(wx.Button(supportPage, label=_("&Export add-on settings…")))
		self.exportSettings.Bind(wx.EVT_BUTTON, self._onExportSettings)
		self.importSettings = helper.addItem(wx.Button(supportPage, label=_("&Import add-on settings…")))
		self.importSettings.Bind(wx.EVT_BUTTON, self._onImportSettings)

	def _activityCategoryDisplay(self, index):
		enabledKey, category, label = self._activityCategories[index]
		state = _("enabled") if self._categoryEnabledValues[enabledKey] else _("disabled")
		output = self._outputModeLabels[OUTPUT_MODE_CHOICES.index(self._categoryOutputValues[category])]
		return _("{label}: {state}; {output}").format(label=label, state=state, output=output)

	def _refreshActivityCategoryDisplay(self, index):
		if 0 <= index < len(self._activityCategories):
			self.activityCategory.SetString(index, self._activityCategoryDisplay(index))

	def _storeActivityCategory(self, index=None):
		index = self._activityCategorySelection if index is None else index
		if index < 0 or index >= len(self._activityCategories):
			return
		enabledKey, category, label = self._activityCategories[index]
		self._categoryEnabledValues[enabledKey] = self.activityEnabled.IsChecked()
		selection = self.activityOutput.GetSelection()
		if 0 <= selection < len(OUTPUT_MODE_CHOICES):
			self._categoryOutputValues[category] = OUTPUT_MODE_CHOICES[selection]
		self._refreshActivityCategoryDisplay(index)

	def _loadActivityCategory(self, index):
		if index < 0 or index >= len(self._activityCategories):
			return
		enabledKey, category, label = self._activityCategories[index]
		self.activityEnabled.SetValue(self._categoryEnabledValues[enabledKey])
		self.activityOutput.SetSelection(OUTPUT_MODE_CHOICES.index(self._categoryOutputValues[category]))

	def _onActivityCategoryChanged(self, evt):
		self._storeActivityCategory(self._activityCategorySelection)
		self._activityCategorySelection = self.activityCategory.GetSelection()
		self._loadActivityCategory(self._activityCategorySelection)

	def _onActivitySettingChanged(self, evt):
		self._storeActivityCategory()

	def _onTest(self, evt):
		verbosity = VERBOSITY_CHOICES[self.verbosity.GetSelection()]
		label = "Testing project: 43 tests for 12 seconds" if verbosity == "minimal" else "Running shell command: python -m unittest discover -s tests"
		fullProfile = FULL_SPEECH_PROFILE_CHOICES[self.fullSpeechProfile.GetSelection()]
		minimalProfile = MINIMAL_SPEECH_PROFILE_CHOICES[self.minimalSpeechProfile.GetSelection()]
		speechMessage = statusMessage(
			label, _, verbosity, self.redactSensitive.IsChecked(), fullProfile, minimalProfile,
		)
		brailleMessage = brailleStatusMessage(
			label, _, BRAILLE_DETAIL_CHOICES[self.brailleDetail.GetSelection()], self.redactSensitive.IsChecked(),
		)
		_send(
			speechMessage,
			self.speech.IsChecked(), self.braille.IsChecked(), "command",
			self.progressSounds.IsChecked(),
			SOUND_STYLE_CHOICES[self.progressSoundStyle.GetSelection()],
			CLICK_VOLUME_CHOICES[self.clickVolume.GetSelection()],
			brailleMessage=brailleMessage,
			interruptUrgent=self.interruptUrgentSpeech.IsChecked(),
		)

	def _onTestSound(self, evt):
		_playProgressSound(
			"command", _("Running command"),
			SOUND_STYLE_CHOICES[self.progressSoundStyle.GetSelection()],
			CLICK_VOLUME_CHOICES[self.clickVolume.GetSelection()],
		)

	def _selectedPreview(self):
		return previewSelection(PREVIEW_ITEMS, self.previewItem.GetSelection())

	def _storeCurrentAnnouncementEdit(self):
		category, key, label, message = self._selectedPreview()
		self._announcementEdits[key] = self.announcementText.GetValue()

	def _onPreviewItemChanged(self, evt):
		oldSelection = getattr(self, "_previousPreviewSelection", 0)
		oldItem = previewSelection(PREVIEW_ITEMS, oldSelection)
		if oldItem:
			self._announcementEdits[oldItem[1]] = self.announcementText.GetValue()
		category, key, label, message = self._selectedPreview()
		self.announcementText.SetValue(self._announcementEdits[key])
		self._previousPreviewSelection = self.previewItem.GetSelection()

	def _onRestoreAnnouncement(self, evt):
		category, key, label, message = self._selectedPreview()
		self._announcementEdits[key] = ""
		self.announcementText.SetValue("")

	def _onPreviewSelectedSound(self, evt):
		style = SOUND_STYLE_CHOICES[self.progressSoundStyle.GetSelection()]
		volume = CLICK_VOLUME_CHOICES[self.clickVolume.GetSelection()]
		category, key, label, message = self._selectedPreview()
		_playProgressSound(category, message, style, volume)

	def _onPreviewSelectedSpeech(self, evt):
		self._storeCurrentAnnouncementEdit()
		category, key, label, message = self._selectedPreview()
		speech.speakMessage(formatCustomAnnouncement(self._announcementEdits[key], message, label, 0))

	def _onCheckUsage(self, evt):
		_openUsageDashboard(_("Opening Claude usage settings"))

	def _onBuyCredits(self, evt):
		wx.LaunchDefaultBrowser("https://support.claude.com/")

	def _onViewCurrentRelease(self, evt):
		_showBrowseableMessageAtTop(
			CURRENT_RELEASE_NOTES, _("Claude Desktop Access — current release notes"),
		)

	def _onViewCompleteHistory(self, evt):
		try:
			message = _completeChangelogMessage()
		except Exception:
			log.error("Unable to open the Claude Desktop Access changelog", exc_info=True)
			ui.message(_("The complete release history could not be opened"))
			return
		_showBrowseableMessageAtTop(
			message, _("Claude Desktop Access — complete release history"),
		)

	def _onSaveSupportReport(self, evt):
		if _activePluginInstance is None:
			ui.message(_("Claude Desktop Access is not currently running"))
			return
		_saveSupportReport(self, _activePluginInstance._diagnosticReport())

	def _onExportSettings(self, evt):
		with wx.FileDialog(
			self, _("Export Claude Desktop Access settings"),
			defaultFile="claude-desktop-access-settings.json",
			wildcard=_("JSON files (*.json)|*.json"), style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			path = Path(dialog.GetPath())
		try:
			values = {key: value for key, value in _settings().items() if isinstance(value, (str, int, float, bool))}
			path.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
		except Exception:
			log.error("Unable to export Claude Desktop Access settings", exc_info=True)
			ui.message(_("Settings could not be exported"))
			return
		ui.message(_("Claude Desktop Access settings exported"))

	def _onImportSettings(self, evt):
		with wx.FileDialog(
			self, _("Import Claude Desktop Access settings"),
			wildcard=_("JSON files (*.json)|*.json"), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
		) as dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return
			path = Path(dialog.GetPath())
		conf = _settings()
		previousValues = {
			key: value for key, value in conf.items()
			if key in config.conf.spec[CONFIG_SECTION] and isinstance(value, (str, int, float, bool))
		}
		try:
			if path.stat().st_size > 1024 * 1024:
				raise ValueError("settings file exceeds 1 MB")
			values = json.loads(path.read_text(encoding="utf-8"))
			if not isinstance(values, dict):
				raise ValueError("settings root is not an object")
			for key, value in values.items():
				if key in config.conf.spec[CONFIG_SECTION] and isinstance(value, (str, int, float, bool)):
					conf[key] = value
			_repairConfiguration()
			config.conf.save()
			self._loadControlsFromConfiguration()
		except Exception:
			for key, value in previousValues.items():
				conf[key] = value
			_repairConfiguration()
			try:
				config.conf.save()
			except Exception:
				log.debugWarning("Unable to save restored Claude Desktop Access settings", exc_info=True)
			self._loadControlsFromConfiguration()
			log.error("Unable to import Claude Desktop Access settings", exc_info=True)
			ui.message(_("Settings could not be imported"))
			return
		ui.message(_("Settings imported and loaded into this panel."))

	def _loadControlsFromConfiguration(self):
		"""Refresh every editable control after an in-place settings import."""
		conf = _settings()
		self.verbosity.SetSelection(VERBOSITY_CHOICES.index(conf["verbosity"]))
		self.fullSpeechProfile.SetSelection(FULL_SPEECH_PROFILE_CHOICES.index(conf["fullSpeechProfile"]))
		self.minimalSpeechProfile.SetSelection(MINIMAL_SPEECH_PROFILE_CHOICES.index(conf["minimalSpeechProfile"]))
		self.brailleDetail.SetSelection(BRAILLE_DETAIL_CHOICES.index(conf["brailleDetail"]))
		self.interruptUrgentSpeech.SetValue(conf["interruptUrgentSpeech"])
		self.commandPunctuation.SetSelection(COMMAND_PUNCTUATION_CHOICES.index(conf["commandPunctuation"]))
		self.maximumSpokenCommandCharacters.SetValue(conf["maximumSpokenCommandCharacters"])
		for name in (
			"speech", "braille", "protectBrailleReading", "redactSensitive", "completionSound",
			"diagnosticLogging", "announceHeartbeat", "announceEmbeddedBrowserProgress",
		):
			getattr(self, name).SetValue(conf[name])
		self.workingIntervalSeconds.SetValue(conf["workingIntervalSeconds"])
		self.idlePollMs.SetValue(conf["idlePollMs"])
		self.supportedAppNames.SetValue(conf["supportedAppNames"])
		self.progressSounds.SetValue(conf["soundWhenSpeechUnavailable"])
		self.progressSoundStyle.SetSelection(SOUND_STYLE_CHOICES.index(conf["progressSoundStyle"]))
		self.clickVolume.SetSelection(CLICK_VOLUME_CHOICES.index(conf["clickVolume"]))
		self.promptSubmissionClick.SetValue(conf["promptSubmissionClick"])
		self.continuousWorkingClicks.SetValue(conf["continuousWorkingClicks"])
		self.workingClickIntervalMs.SetValue(conf["workingClickIntervalMs"])
		self.workingClickStartDelayMs.SetValue(conf["workingClickStartDelayMs"])
		self.monitoringFocusClicks.SetValue(conf["monitoringFocusClicks"])
		self.maximumBusyMinutes.SetValue(conf["maximumBusyMinutes"])
		self._categoryEnabledValues = {
			key: bool(conf[key]) for key, category, label in self._activityCategories
		}
		self._categoryOutputValues = {
			category: str(conf[CATEGORY_OUTPUT_CONFIG[category]])
			for key, category, label in self._activityCategories
		}
		for index in range(len(self._activityCategories)):
			self._refreshActivityCategoryDisplay(index)
		self._activityCategorySelection = max(0, self.activityCategory.GetSelection())
		self._loadActivityCategory(self._activityCategorySelection)
		self._announcementEdits = {key: str(conf[key]) for category, key, label, message in PREVIEW_ITEMS}
		selected = self._selectedPreview()
		self.announcementText.SetValue(self._announcementEdits[selected[1]])
		self._previousPreviewSelection = self.previewItem.GetSelection()

	def _onResetSpeechSettings(self, evt):
		self.verbosity.SetSelection(VERBOSITY_CHOICES.index("full"))
		self.fullSpeechProfile.SetSelection(FULL_SPEECH_PROFILE_CHOICES.index("developer"))
		self.minimalSpeechProfile.SetSelection(MINIMAL_SPEECH_PROFILE_CHOICES.index("balanced"))
		self.commandPunctuation.SetSelection(COMMAND_PUNCTUATION_CHOICES.index("enhanced"))
		self.maximumSpokenCommandCharacters.SetValue(240)
		self.redactSensitive.SetValue(False)
		ui.message(_("Speech profile settings reset. Select OK to save."))

	def onSave(self):
		conf = _settings()
		self._storeCurrentAnnouncementEdit()
		self._storeActivityCategory()
		conf["verbosity"] = VERBOSITY_CHOICES[self.verbosity.GetSelection()]
		conf["fullSpeechProfile"] = FULL_SPEECH_PROFILE_CHOICES[self.fullSpeechProfile.GetSelection()]
		conf["minimalSpeechProfile"] = MINIMAL_SPEECH_PROFILE_CHOICES[self.minimalSpeechProfile.GetSelection()]
		conf["brailleDetail"] = BRAILLE_DETAIL_CHOICES[self.brailleDetail.GetSelection()]
		conf["interruptUrgentSpeech"] = self.interruptUrgentSpeech.IsChecked()
		conf["commandPunctuation"] = COMMAND_PUNCTUATION_CHOICES[self.commandPunctuation.GetSelection()]
		conf["maximumSpokenCommandCharacters"] = self.maximumSpokenCommandCharacters.GetValue()
		for name in (
			"speech", "braille", "protectBrailleReading", "redactSensitive", "completionSound",
			"diagnosticLogging", "announceHeartbeat", "announceEmbeddedBrowserProgress",
		):
			conf[name] = getattr(self, name).IsChecked()
		conf["soundWhenSpeechUnavailable"] = self.progressSounds.IsChecked()
		conf["progressSoundStyle"] = SOUND_STYLE_CHOICES[self.progressSoundStyle.GetSelection()]
		conf["clickVolume"] = CLICK_VOLUME_CHOICES[self.clickVolume.GetSelection()]
		conf["continuousWorkingClicks"] = self.continuousWorkingClicks.IsChecked()
		conf["workingClickIntervalMs"] = self.workingClickIntervalMs.GetValue()
		conf["workingClickStartDelayMs"] = self.workingClickStartDelayMs.GetValue()
		conf["promptSubmissionClick"] = self.promptSubmissionClick.IsChecked()
		conf["monitoringFocusClicks"] = self.monitoringFocusClicks.IsChecked()
		conf["maximumBusyMinutes"] = self.maximumBusyMinutes.GetValue()
		for key, value in self._announcementEdits.items():
			conf[key] = value.strip()
		for name, value in self._categoryEnabledValues.items():
			conf[name] = value
		for category, value in self._categoryOutputValues.items():
			conf[CATEGORY_OUTPUT_CONFIG[category]] = value
		conf["workingIntervalSeconds"] = self.workingIntervalSeconds.GetValue()
		conf["idlePollMs"] = self.idlePollMs.GetValue()
		conf["supportedAppNames"] = mergeSupportedAppNames(self.supportedAppNames.GetValue())


def _isClaudeObject(obj):
	try:
		appName = str(getattr(getattr(obj, "appModule", None), "appName", "") or "").lower()
		supported = {name.strip().lower() for name in _settings()["supportedAppNames"].split(",") if name.strip()}
		return appName in supported
	except Exception:
		return False


def _conversationModeForObject(obj):
	if not _isClaudeObject(obj):
		return ""
	current, documents = obj, []
	for _ in range(40):
		if current is None:
			break
		if _roleName(current) == "document":
			if isCodeDocument(current):
				return "" if documents else "code"
			documents.append(current)
		current = getattr(current, "parent", None)
	if len(documents) != 1:
		return ""
	return conversationDocumentMode([getattr(documents[0], "name", "")])


def _isConversationObject(obj):
	return bool(_conversationModeForObject(obj))


def _isCodePromptObject(obj):
	if not _isClaudeObject(obj) or getattr(obj, "role", None) != Role.EDITABLETEXT:
		return False
	if isNativeComposer(obj):
		return True
	if _conversationModeForObject(obj) == "code":
		return False
	return any(promptLabel(getattr(obj, attr, "")) for attr in ("name", "placeholder", "description"))


def _roleName(obj):
	role = getattr(obj, "role", None)
	name = getattr(role, "name", "")
	if name:
		return str(name).casefold()
	return str(role or "").rsplit(".", 1)[-1].casefold()


def _isDefunctObject(obj):
	"""Return whether NVDA has marked an object as no longer available."""
	try:
		return State.DEFUNCT in (getattr(obj, "states", ()) or ())
	except Exception:
		return False


def _isEmbeddedBrowserObject(obj):
	"""Recognize an explicit browser container or a web document nested in Claude."""
	if not _isClaudeObject(obj):
		return False
	cached = getattr(obj, "_codeEmbeddedBrowserDetected", None)
	if cached is not None:
		return bool(cached)
	# The primary prompt and its known toolbar controls are never embedded-browser
	# content. Reject them before any Chromium ancestor access; these objects are
	# recreated frequently while typing and a negative ancestry walk blocks NVDA's
	# main thread and delays queued Braille input.
	if _isCodePromptObject(obj) or promptControlKind(getattr(obj, "name", "")):
		try:
			obj._codeEmbeddedBrowserDetected = False
		except Exception:
			pass
		return False
	current = obj
	ancestorRoles = []
	for _ in range(18):
		if current is None:
			break
		try:
			roleName = _roleName(current)
			ancestorRoles.append(roleName)
			if isEmbeddedBrowserContainerText(
				getattr(current, "name", ""), getattr(current, "description", ""),
			) and isEmbeddedBrowserContainerRole(roleName):
				try:
					obj._codeEmbeddedBrowserDetected = True
				except Exception:
					pass
				return True
			if isEmbeddedBrowserDocumentStructure(*ancestorRoles):
				try:
					obj._codeEmbeddedBrowserDetected = True
				except Exception:
					pass
				return True
			current = getattr(current, "parent", None)
		except Exception:
			return False
	try:
		obj._codeEmbeddedBrowserDetected = False
	except Exception:
		pass
	return False


class CodePromptControlOverlay:
	"""Add concise help to recognized native controls beside the Code prompt."""

	def _get_description(self):
		descriptions = {
			"files": _("Opens file and attachment options. Press Enter or Space to open."),
			"model": _("Opens the model list. Press Enter or Space to open, then use arrow keys and Enter."),
			"permissions": _("Opens permission choices. Press Enter or Space to open, then use arrow keys and Enter."),
		}
		nativeDescription = str(getattr(self, "_codeNativeDescription", "") or "").strip()
		helpDescription = descriptions.get(getattr(self, "_codePromptControlKind", ""), "")
		if nativeDescription and helpDescription.casefold() not in nativeDescription.casefold():
			return _("{native} {help}").format(native=nativeDescription, help=helpDescription)
		return nativeDescription or helpDescription


class CodePromptEditableTextOverlay:
	"""Let Claude handle Enter without NVDA inspecting its replaced prompt object."""

	# Claude submits Enter instead of inserting a newline, then immediately replaces
	# its content-editable object. NVDA's generic multiline-edit Enter script tries to
	# inspect that stale IA2 object and can play the log-error sound even though the
	# message was sent. Disabling only the generic newline-announcement binding leaves
	# physical Enter, numpad Enter, Shift+Enter, and Braille-emulated keys native.
	announceNewLineText = False


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Claude Desktop Access")

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		"""Enhance known controls without adding or intercepting gestures."""
		try:
			if not _isClaudeObject(obj):
				return
			# Known prompt-toolbar controls are much more common than embedded
			# browser controls. Handle them without an unnecessary ancestor walk.
			if obj.role in (Role.BUTTON, Role.COMBOBOX):
				kind = promptControlKind(getattr(obj, "name", ""))
				if kind:
					obj._codePromptControlKind = kind
					obj._codeNativeDescription = getattr(obj, "description", "")
					clsList.insert(0, CodePromptControlOverlay)
					return
			# The prompt submits Enter rather than inserting a newline. Apply the
			# prompt-specific overlay before EditableTextBase initializes so NVDA does
			# not bind its generic caret_newLine script to this transient Chromium node.
			if obj.role == Role.EDITABLETEXT and _isCodePromptObject(obj):
				clsList.insert(0, CodePromptEditableTextOverlay)
				return
		except Exception:
			return

	def __init__(self):
		global _activePluginInstance
		super().__init__()
		_activePluginInstance = self
		_repairConfiguration()
		migratedGestures = _migrateApplicationGestureMappings()
		if migratedGestures:
			log.info("Claude Desktop Access migrated %d application gesture mappings", migratedGestures)
		self._lastMessage = ""
		self._lastMessageAt = 0.0
		self._lastSpeechMessage = ""
		self._lastSpeechMessageAt = 0.0
		self._lastBrailleMessage = ""
		self._lastBrailleMessageAt = 0.0
		self._lastLabel = ""
		self._latestMessage = ""
		self._latestFullMessage = ""
		self._haveBaseline = False
		self._buffer = None
		self._nativeTaskObserver = BufferUpdateObserver(self._observeNativeTaskState)
		self._nativeTaskDocument = ""
		self._nativeTaskState = None
		self._nativeTaskStartedAt = None
		self._nativeTaskSeconds = None
		self._nativeLastClick = None
		self._nativeLastPulse = None
		self._nativePulseCount = 0
		self._nativeFallbackClock = None
		self._lastNativeTaskSampleAt = 0.0
		self._conversationWindowHandle = 0
		self._conversationWindowUnavailableAt = 0.0
		self._conversationMode = ""
		self._conversationModeObserved = False
		self._conversationModeChangedAt = 0.0
		self._lastConversationModeProbeAt = 0.0
		self._conversationModeProbeGeneration = 0
		self._conversationModeProbePendingGeneration = 0
		self._conversationModeProbeActivationGeneration = 0
		self._conversationModeObservedAt = 0.0
		self._monitoringAnnounced = False
		self._lastNoStatusLogAt = 0.0
		self._active = False
		self._busy = False
		self._commentaryOffsets = {}
		self._paused = False
		self._speechHistory = AnnouncementHistory(20)
		self._brailleHistory = AnnouncementHistory(20)
		self._history = self._speechHistory
		self._busyWatchdogAt = 0.0
		self._activeCategory = "other"
		self._appFocusState = None
		self._promptHadText = None
		self._latestUserMessageNumber = None
		self._pendingUserMessageIncrease = False
		self._stopControlVisible = False
		self._lastStateReason = "startup"
		self._lastSubmissionSignal = "none"
		self._documentSwitchCount = 0
		self._lastInspectionError = "none"
		self._lastUnknownButtons = ()
		self._lastUnknownButtonsAt = 0.0
		self._lastRejectedBufferLogAt = 0.0
		self._lastDeferredHistoryLog = ()
		self._lastDeferredHistoryLogAt = 0.0
		self._lastPollAt = 0.0
		self._nextPollAt = 0.0
		self._bufferDirty = True
		self._lastBufferInspectionAt = 0.0
		self._lastScannedLabel = ""
		self._bufferInspectionCount = 0
		self._skippedBufferInspectionCount = 0
		self._promptTypingUntil = 0.0
		self._conversationNavigationUntil = 0.0
		self._promptFocused = False
		self._brailleCompositionActive = False
		self._lastBrailleTextInjectionAt = 0.0
		self._brailleCaretMoveSuppressions = 0
		self._suppressedConversationUpdates = 0
		self._promptInspectionTimer = None
		self._pendingPromptObject = None
		self._lastPromptObject = None
		self._promptSubmissionGestureQueued = False
		self._inputGestureObserverRegistered = False
		self._latestResponseMarker = None
		self._responseMarkerInitialized = False
		self._pendingResponseCompletionAt = 0.0
		self._chatHistoryDialog = None
		self._pendingChatHistoryAction = None
		self._chatHistoryActionTimer = None
		self._chatHistoryExpansionTimer = None
		self._pendingChatHistoryExpansion = None
		self._chatActionRetryTimer = None
		self._pendingDirectChatAction = None
		self._unarchiveFocusTimer = None
		self._unarchiveFocusAttempts = 0
		self._popupFocusTimer = None
		self._pendingPopupDialog = None
		self._lastFocusedPopupDialog = None
		self._usageLimitActive = False
		self._lastUsageLimitNotice = ""
		self._pluginProgressBuckets = {}
		self._pluginProgressOwnedBusy = set()
		self._embeddedBrowserFocused = False
		self._lastEmbeddedBrowserObject = None
		self._embeddedBrowserBuffer = None
		self._embeddedBrowserPageTitle = ""
		self._embeddedBrowserAddress = ""
		self._embeddedBrowserLoadingPercent = None
		self._embeddedBrowserLoading = False
		self._embeddedBrowserBusySeen = False
		self._embeddedBrowserLoadIdentity = ""
		self._embeddedBrowserCompletedIdentity = ""
		self._embeddedBrowserLoadGeneration = 0
		self._embeddedBrowserLoadTimer = None
		self._lastEmbeddedBrowserTitle = ""
		self._lastEmbeddedBrowserNotice = ""
		self._lastEmbeddedBrowserNoticeAt = 0.0
		self._embeddedBrowserProgressBuckets = {}
		self._browserNavigatorDialog = None
		self._browserNavigatorResult = None
		self._browserScanTimer = None
		self._browserScanState = None
		self._browserScanPurpose = ""
		self._browserActionTimer = None
		self._pendingBrowserAction = None
		self._browserSavedLocations = {}
		self._browserScanCount = 0
		self._browserScanLimitCount = 0
		self._lastBrowserScanObjects = 0
		self._pendingOpenedChatTitle = ""
		self._pendingOpenedChatAt = 0.0
		self._chatHistoryCaches = {"claude": (), "code": (), "cowork": ()}
		self._chatHistoryCacheCurrent = {"claude": False, "code": False, "cowork": False}
		self._pendingChatHistorySnapshots = {"claude": None, "code": None, "cowork": None}
		self._pendingChatHistorySnapshotAt = {"claude": 0.0, "code": 0.0, "cowork": 0.0}
		self._chatHistoryMoreAvailable = {"claude": False, "code": False, "cowork": False}
		self._recentHistoryShowMoreOrdinals = {"claude": 0, "code": 0, "cowork": 0}
		self._unifiedRecentCounts = {"claude": 0, "code": 0, "cowork": 0}
		self._chatHistoryScanGenerations = {"claude": 0, "code": 0, "cowork": 0}
		self._activeCodeTitlesCache = ()
		self._activeCodeTitlesSourceSignature = None
		self._recentClassificationSummaries = {"claude": None, "code": None, "cowork": None}
		self._archivedChatHistoryCaches = {"claude": (), "code": (), "cowork": ()}
		self._archivedChatHistoryLoaded = {"claude": False, "code": False, "cowork": False}
		self._archivedChatIds = {"claude": {}, "code": {}, "cowork": {}}
		self._chatHistoryDialogMode = ""
		self._voiceControlConfirmationTimer = None
		self._pendingVoiceControlConfirmation = None
		self._whatsNewTimer = None
		log.info(
			"Claude Desktop Access %s loaded (verbosity=%s, fullProfile=%s, minimalProfile=%s, brailleDetail=%s, soundStyle=%s)",
			ADDON_VERSION,
			_settings()["verbosity"], _settings()["fullSpeechProfile"],
			_settings()["minimalSpeechProfile"], _settings()["brailleDetail"], _settings()["progressSoundStyle"],
		)
		if ClaudeDesktopAccessSettingsPanel not in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.append(ClaudeDesktopAccessSettingsPanel)
		try:
			inputCore.decide_executeGesture.register(self._observeInputGesture)
			self._inputGestureObserverRegistered = True
		except Exception:
			log.debugWarning("Claude Desktop Access could not observe Braille input gestures", exc_info=True)
		self._claudeNavigationScan = None
		self._claudeNavigationDialog = None
		self._timer = wx.CallLater(100, self._poll)
		self._nextPollAt = time.monotonic() + 0.1
		self._whatsNewTimer = wx.CallLater(1500, self._showWhatsNewIfNeeded)

	def terminate(self):
		self._nativeTaskObserver.detach()
		global _activePluginInstance
		if self._claudeNavigationScan:
			self._claudeNavigationScan.cancel()
		if self._claudeNavigationDialog:
			self._claudeNavigationDialog.Close()
		self._conversationModeProbeGeneration += 1
		self._conversationModeProbePendingGeneration = 0
		self._conversationModeProbeActivationGeneration = 0
		if self._inputGestureObserverRegistered:
			try:
				inputCore.decide_executeGesture.unregister(self._observeInputGesture)
			except Exception:
				log.debugWarning("Claude Desktop Access could not remove its Braille input observer", exc_info=True)
			self._inputGestureObserverRegistered = False
		if self._timer:
			self._timer.Stop()
			self._timer = None
		self._nextPollAt = 0.0
		if self._whatsNewTimer:
			self._whatsNewTimer.Stop()
			self._whatsNewTimer = None
		if self._promptInspectionTimer:
			self._promptInspectionTimer.Stop()
			self._promptInspectionTimer = None
		self._pendingPromptObject = None
		if self._embeddedBrowserLoadTimer:
			self._embeddedBrowserLoadTimer.Stop()
			self._embeddedBrowserLoadTimer = None
		if self._chatHistoryDialog:
			self._chatHistoryDialog.Destroy()
			self._chatHistoryDialog = None
			gui.mainFrame.postPopup()
		if self._browserNavigatorDialog:
			self._browserNavigatorDialog.Destroy()
			self._browserNavigatorDialog = None
			gui.mainFrame.postPopup()
		if self._browserScanTimer:
			self._browserScanTimer.Stop()
			self._browserScanTimer = None
		self._browserScanState = None
		self._browserScanPurpose = ""
		if self._browserActionTimer:
			self._browserActionTimer.Stop()
			self._browserActionTimer = None
		self._pendingBrowserAction = None
		if self._chatHistoryActionTimer:
			self._chatHistoryActionTimer.Stop()
			self._chatHistoryActionTimer = None
		self._cancelChatHistoryExpansion()
		if self._chatActionRetryTimer:
			self._chatActionRetryTimer.Stop()
			self._chatActionRetryTimer = None
		self._pendingDirectChatAction = None
		if self._unarchiveFocusTimer:
			self._unarchiveFocusTimer.Stop()
			self._unarchiveFocusTimer = None
		if self._popupFocusTimer:
			self._popupFocusTimer.Stop()
			self._popupFocusTimer = None
		self._cancelVoiceControlConfirmation()
		self._pendingPopupDialog = None
		self._lastFocusedPopupDialog = None
		self._pluginProgressBuckets.clear()
		self._pluginProgressOwnedBusy.clear()
		self._embeddedBrowserProgressBuckets.clear()
		self._browserSavedLocations.clear()
		self._pendingChatHistoryAction = None
		try:
			NVDASettingsDialog.categoryClasses.remove(ClaudeDesktopAccessSettingsPanel)
		except ValueError:
			pass
		if _activePluginInstance is self:
			_activePluginInstance = None
		super().terminate()

	def _schedulePoll(self, delay=150, requestInspection=True):
		if requestInspection:
			self._bufferDirty = True
		now = time.monotonic()
		actualDelay = coalescedPollDelay(
			delay, now - self._lastPollAt if self._lastPollAt else float("inf"),
		)
		requestedDeadline = now + actualDelay / 1000.0
		if self._timer and not shouldReplaceScheduledPoll(self._nextPollAt, requestedDeadline):
			return
		if self._timer:
			self._timer.Stop()
		self._timer = wx.CallLater(actualDelay, self._poll)
		self._nextPollAt = requestedDeadline

	def _showWhatsNewIfNeeded(self):
		self._whatsNewTimer = None
		conf = _settings()
		if conf["lastShownVersion"] == ADDON_VERSION:
			return
		_showBrowseableMessageAtTop(
			CURRENT_RELEASE_NOTES, _("Claude Desktop Access — what's new"),
		)
		conf["lastShownVersion"] = ADDON_VERSION
		conf["welcomeShown"] = True
		try:
			config.conf.save()
		except Exception:
			log.debugWarning("Unable to save the last displayed add-on version", exc_info=True)

	def _resetTaskState(self, reason):
		self._setBusy(False, reason)
		self._lastLabel = ""
		self._haveBaseline = False
		self._commentaryOffsets.clear()
		self._promptHadText = None
		self._promptTypingUntil = 0.0
		self._conversationNavigationUntil = 0.0
		self._brailleCompositionActive = False
		if self._promptInspectionTimer:
			self._promptInspectionTimer.Stop()
			self._promptInspectionTimer = None
		self._pendingPromptObject = None
		self._bufferDirty = True
		self._lastScannedLabel = ""
		self._latestUserMessageNumber = None
		self._pendingUserMessageIncrease = False
		self._stopControlVisible = False
		self._lastUnknownButtons = ()
		self._lastUnknownButtonsAt = 0.0
		self._latestResponseMarker = None
		self._responseMarkerInitialized = False
		self._pendingResponseCompletionAt = 0.0
		self._usageLimitActive = False
		self._lastUsageLimitNotice = ""
		self._speechHistory.clear()
		self._brailleHistory.clear()
		self._latestMessage = ""
		self._latestFullMessage = ""
		self._lastMessage = ""
		self._lastMessageAt = 0.0
		self._lastSpeechMessage = ""
		self._lastSpeechMessageAt = 0.0
		self._lastBrailleMessage = ""
		self._lastBrailleMessageAt = 0.0
		self._activeCategory = "other"

	def _recordHistory(self, speechMessage, brailleMessage=None):
		brailleText = str(brailleMessage if brailleMessage is not None else speechMessage or "").strip()
		# Keep navigation aligned even when an Essential speech profile intentionally
		# omits a live event; explicit history review may still expose its details.
		self._speechHistory.add(str(speechMessage or brailleText).strip())
		self._brailleHistory.add(brailleText or str(speechMessage or "").strip())

	def _historyMessage(self, offset):
		if not self._speechHistory and not self._brailleHistory:
			ui.message(_("No activity announcement history is available"))
			return
		speechMessage = self._speechHistory.move(offset) if self._speechHistory else ""
		brailleMessage = self._brailleHistory.move(offset) if self._brailleHistory else speechMessage
		conf = _settings()
		_send(
			speechMessage or brailleMessage, conf["speech"] and bool(speechMessage), conf["braille"],
			None, False, brailleMessage=brailleMessage,
		)

	def _currentChatMessages(self):
		focus = api.getFocusObject()
		if not _isClaudeObject(focus):
			return ()
		self._rememberBuffer(focus)
		if not self._buffer:
			return ()
		info = self._buffer.makeTextInfo(textInfos.POSITION_ALL)
		return chatMessagesFromTokens(messageTokens(info.getTextWithFields()), 10)

	def _readRecentChatMessage(self, position):
		try:
			messages = self._currentChatMessages()
		except Exception:
			log.debugWarning("Claude Desktop Access could not read recent chat messages", exc_info=True)
			ui.message(_("Recent chat messages could not be read"))
			return
		if not messages:
			ui.message(_("No recent chat messages are available"))
			return
		if len(messages) < position:
			ui.message(_("Only {count} recent chat messages are available").format(count=len(messages)))
			return
		speaker, text = messages[-position]
		speakerLabel = _("You") if speaker == "user" else _("Claude")
		ui.message(_("Chat message {position}, {speaker}: {text}").format(
			position=position, speaker=speakerLabel, text=text,
		))

	def _diagnosticReport(self):
		conf = _settings()
		return _(
			"Beta: live validation ongoing\nNVDA: {nvdaVersion}\nVersion: {version}\nVerbosity: {verbosity}\nFull speech profile: {profile}\nMinimal speech profile: {minimalProfile}\nBraille detail: {brailleDetail}\nSound style: {style}\nClick volume: {volume}\n"
			"Monitoring attached: {attached}\nBackground state: {state}\nPaused: {paused}\n"
			"Active category: {category}\nLast state reason: {reason}\nLast submission signal: {signal}\n"
			"Claude document switches: {switches}\nFull buffer inspections: {inspections}\nLightweight ticks without inspection: {skipped}\nPrompt typing protection: {typingProtection}\nPreserved Braille compositions: {braillePreserved}\nSuppressed disruptive conversation updates: {conversationUpdates}\nLast inspection error: {error}\n"
			"Embedded browser focus detected: {browserFocused}\nNative browser interaction: yes\n"
			"Embedded browser loading announcements: {browserProgress}\n"
			"Speech history entries: {speechHistory}\nBraille history entries: {brailleHistory}\nRecent chats cached: {recent}\nArchived chats cached: {archived}\n"
			"Configuration repairs this session: {repairs}\nSupported applications: {apps}\n"
			"Speech: {speech}\nBraille: {braille}\nStable conversation reading: {protectBraille}\nUrgent speech interruption: {interrupt}\nProgress sounds: {sounds}\nCategory output routing:\n{routing}"
		).format(
			version=ADDON_VERSION, nvdaVersion=getattr(versionInfo, "version", "unknown"),
			verbosity=conf["verbosity"], profile=conf["fullSpeechProfile"], minimalProfile=conf["minimalSpeechProfile"],
			brailleDetail=conf["brailleDetail"],
			style=conf["progressSoundStyle"], volume=conf["clickVolume"],
			attached=bool(self._buffer), state="active" if self._busy else "idle", paused=self._paused,
			category=self._activeCategory, reason=self._lastStateReason, signal=self._lastSubmissionSignal,
			switches=self._documentSwitchCount, inspections=self._bufferInspectionCount,
			skipped=self._skippedBufferInspectionCount,
			typingProtection="active" if time.monotonic() < self._promptTypingUntil else "inactive",
			braillePreserved=self._brailleCaretMoveSuppressions,
			conversationUpdates=self._suppressedConversationUpdates,
			error=self._lastInspectionError,
			browserFocused=self._embeddedBrowserFocused,
			browserProgress=conf["announceEmbeddedBrowserProgress"],
			speechHistory=len(self._speechHistory), brailleHistory=len(self._brailleHistory),
			recent=len(self._chatHistoryTitles()),
			archived=len(self._archivedChatHistoryCaches.get(self._conversationMode, ())),
			repairs=", ".join(_lastConfigurationRepairs) or "none", apps=conf["supportedAppNames"], speech=conf["speech"],
			braille=conf["braille"], protectBraille=conf["protectBrailleReading"],
			interrupt=conf["interruptUrgentSpeech"], sounds=conf["soundWhenSpeechUnavailable"],
			routing="\n".join(
				"{category}: {mode}".format(category=category, mode=conf[key])
				for category, key in CATEGORY_OUTPUT_CONFIG.items()
			),
		)

	def _bufferCandidates(self, obj):
		seen = set()
		current = obj
		for _ in range(24):
			if current is None or id(current) in seen:
				break
			seen.add(id(current))
			yield current
			current = getattr(current, "parent", None)
		for current in reversed(api.getFocusAncestors() or []):
			if current is not None and id(current) not in seen:
				yield current

	def _queueConversationModeProbe(self, reason, openSelector=False):
		"""Claude uses native tabs; do not poll a ChatGPT-specific UIA selector."""
		return False

	def _completeConversationModeProbe(
		self, generation, windowHandle, mode, reason,
		selectorRequested=False, selectorOpened=False,
	):
		"""Apply an asynchronous mode result only to the conversation that requested it."""
		global _activePluginInstance
		if generation != self._conversationModeProbePendingGeneration:
			return
		self._conversationModeProbePendingGeneration = 0
		if getattr(self, "_conversationModeProbeActivationGeneration", 0) == generation:
			self._conversationModeProbeActivationGeneration = 0
		if _activePluginInstance is not self or windowHandle != self._conversationWindowHandle:
			return
		if selectorRequested:
			if not mode:
				self._announceConversationModeNotice(
					_("The Claude Chat, Cowork and Code mode switch is not available in this view"),
				)
				log.debugWarning("Claude Desktop Access could not find the mode-switch control")
				return
			if not selectorOpened:
				self._announceConversationModeNotice(
					_("The Claude Chat, Cowork and Code mode menu could not be opened"),
				)
				log.debugWarning("Claude Desktop Access could not expand the mode-switch control")
				return
			self._setConversationMode(mode, reason, authoritative=True)
			modeName = _("Code") if mode == "code" else _("Claude")
			self._announceConversationModeNotice(
				_("{mode} mode. Mode selector open. Use Up or Down Arrow and Enter to choose a mode.").format(
					mode=modeName,
				),
			)
			return
		if not mode:
			log.debug("Claude Desktop Access mode-switch control was not available during verification")
			return
		if self._setConversationMode(mode, reason, authoritative=True):
			self._schedulePoll(delay=50, requestInspection=True)

	def _announceConversationModeNotice(self, message):
		"""Send a mode-switch result through the add-on's enabled output channels."""
		self._latestMessage = self._latestFullMessage = message
		self._speakOnce(
			message, "other", "other", brailleMessage=message, protectBrailleReading=False,
		)

	def _openClaudeNavigator(self):
		focus = api.getFocusObject()
		if not _isClaudeObject(focus):
			ui.message(_("Move to Claude before opening navigation"))
			return
		self._rememberBuffer(focus)
		root = getattr(self._buffer, "rootNVDAObject", None)
		if root is None:
			ui.message(_("Claude has not exposed a conversation document. Try browse mode, then try again."))
			return
		if self._claudeNavigationScan:
			self._claudeNavigationScan.cancel()
		window = self._conversationWindowHandle
		def valid():
			return _activePluginInstance is self and _isClaudeObject(api.getFocusObject()) and window == self._conversationWindowHandle
		def completed(items, truncated):
			self._claudeNavigationScan = None
			if not valid():
				return
			if not items:
				ui.message(_("No recognized Claude navigation controls were exposed. Use native Tab navigation and include this result in beta feedback."))
				return
			def closed():
				self._claudeNavigationDialog = None
				gui.mainFrame.postPopup()
			def action(obj, kind):
				if not valid() or not _isClaudeObject(obj) or _isDefunctObject(obj):
					ui.message(_("The Claude view changed. Reopen navigation."))
					return
				try:
					obj.setFocus()
					if kind == "activate":
						obj.doAction()
					else:
						api.setNavigatorObject(obj)
				except Exception:
					ui.message(_("This Claude control could not be reached. Try native Tab navigation."))
			gui.mainFrame.prePopup()
			try:
				self._claudeNavigationDialog = ClaudeNavigator(items, action, closed, truncated)
				self._claudeNavigationDialog.Show()
			except Exception:
				gui.mainFrame.postPopup()
				raise
		ui.message(_("Scanning Claude navigation"))
		self._claudeNavigationScan = NavigationScan(root, valid, completed)
		self._claudeNavigationScan.step()

	def _openConversationModeSelector(self):
		self._openClaudeNavigator()

	def _observeConversationModeControl(self, obj, reason):
		if not _isClaudeObject(obj):
			return False
		mode = modeFromTab(getattr(obj, "name", ""), getattr(obj, "role", None) == Role.TAB, State.SELECTED in getattr(obj, "states", set()))
		if mode and self._eventBelongsToRetainedConversationBuffer(obj):
			return self._setConversationMode(mode, reason, authoritative=True)
		return False

	def _eventBelongsToRetainedConversationBuffer(self, obj):
		"""Require an event to use the exact retained buffer, not stale ancestry."""
		if self._buffer is None:
			return False
		seen = set()
		current = obj
		for _ in range(24):
			if current is None or id(current) in seen:
				break
			seen.add(id(current))
			try:
				buffer = getattr(current, "treeInterceptor", None)
				if buffer is not None:
					return buffer is self._buffer
				current = getattr(current, "parent", None)
			except Exception:
				return False
		return False

	def _eventUsesConversationBuffer(self, obj):
		"""Exclude embedded-browser and unrelated Claude events from conversation scans."""
		if not _isClaudeObject(obj):
			return False
		# A live region can retain a newly rebuilt Chromium tree interceptor while
		# ``self._buffer`` still points to the preceding instance. Document ancestry
		# is authoritative in that interval. Nested browser documents have no
		# conversation mode and therefore continue to be excluded below.
		if _isConversationObject(obj) or _isCodePromptObject(obj):
			return True
		if self._buffer is None:
			return False
		seen = set()
		current = obj
		for _ in range(24):
			if current is None or id(current) in seen:
				break
			seen.add(id(current))
			try:
				buffer = getattr(current, "treeInterceptor", None)
				if buffer is not None:
					return buffer is self._buffer
				current = getattr(current, "parent", None)
			except Exception:
				return False
		return _isConversationObject(obj) or _isCodePromptObject(obj)

	def _conversationBrowseModeActive(self):
		"""Return the mode of the conversation being read, not a transient event buffer."""
		try:
			return bool(self._buffer is not None and not getattr(self._buffer, "passThrough", True))
		except Exception:
			return False

	def _conversationWindowHandleFrom(self, obj, buffer):
		"""Return the outer Claude window, not Chromium's replaceable renderer child."""
		root = getattr(buffer, "rootNVDAObject", None)
		# The event object can belong to a temporary mode-menu popup. Prefer the
		# conversation document root so closing the main window cannot leave the
		# popup handle looking like a new Claude session.
		for candidate in (root, obj):
			try:
				handle = int(getattr(candidate, "windowHandle", 0) or 0)
			except Exception:
				continue
			if not handle:
				continue
			try:
				return int(winUser.getAncestor(handle, winUser.GA_ROOT) or handle)
			except Exception:
				return handle
		return 0

	def _conversationWindowIsAvailable(self, handle):
		"""Conservatively accept only a living, visible outer Claude window."""
		if not handle:
			return False
		try:
			return bool(winUser.isWindow(handle) and winUser.isWindowVisible(handle))
		except Exception:
			# Attachment is reversible and event-driven. If Windows cannot validate a
			# candidate, wait for a later event instead of reviving a closed session.
			return False

	def _detachConversationIfWindowClosed(self, now):
		"""Stop retained activity after the real Claude window closes or hides to the tray."""
		handle = self._conversationWindowHandle
		if not handle:
			self._conversationWindowUnavailableAt = 0.0
			return False
		try:
			windowExists = bool(winUser.isWindow(handle))
			windowVisible = bool(windowExists and winUser.isWindowVisible(handle))
		except Exception:
			# Unknown window state must not interrupt legitimate background work.
			self._conversationWindowUnavailableAt = 0.0
			return False
		if windowExists and windowVisible:
			self._conversationWindowUnavailableAt = 0.0
			return False
		if not self._conversationWindowUnavailableAt:
			self._conversationWindowUnavailableAt = now
		if not conversationWindowShouldDetach(
			True, windowExists, windowVisible,
			now - self._conversationWindowUnavailableAt,
			CONVERSATION_WINDOW_CLOSE_GRACE_SECONDS,
		):
			return False
		self._nativeTaskObserver.detach()
		self._nativeTaskDocument = ""
		self._nativeTaskState = None
		self._nativeTaskStartedAt = None
		self._nativeFallbackClock = None
		self._updateNativeTaskTimer(None)
		self._buffer = None
		self._conversationWindowHandle = 0
		self._conversationWindowUnavailableAt = 0.0
		self._conversationMode = ""
		self._conversationModeObserved = False
		self._conversationModeObservedAt = 0.0
		self._conversationModeChangedAt = 0.0
		self._lastConversationModeProbeAt = 0.0
		self._conversationModeProbeGeneration += 1
		self._conversationModeProbePendingGeneration = 0
		self._conversationModeProbeActivationGeneration = 0
		self._chatHistoryCacheCurrent = {"claude": False, "code": False, "cowork": False}
		self._pendingChatHistorySnapshots = {"claude": None, "code": None, "cowork": None}
		self._pendingChatHistorySnapshotAt = {"claude": 0.0, "code": 0.0, "cowork": 0.0}
		self._chatHistoryMoreAvailable = {"claude": False, "code": False, "cowork": False}
		self._recentHistoryShowMoreOrdinals = {"claude": 0, "code": 0, "cowork": 0}
		self._unifiedRecentCounts = {"claude": 0, "code": 0, "cowork": 0}
		self._chatHistoryScanGenerations = {"claude": 0, "code": 0, "cowork": 0}
		self._cancelChatHistoryExpansion()
		self._monitoringAnnounced = False
		self._cancelEmbeddedBrowserScan()
		if self._browserActionTimer:
			self._browserActionTimer.Stop()
			self._browserActionTimer = None
		self._pendingBrowserAction = None
		if self._browserNavigatorDialog:
			self._browserNavigatorDialog.Close()
		self._browserNavigatorResult = None
		self._lastEmbeddedBrowserObject = None
		self._embeddedBrowserBuffer = None
		self._embeddedBrowserPageTitle = ""
		self._embeddedBrowserAddress = ""
		self._resetEmbeddedBrowserProgress()
		self._browserSavedLocations.clear()
		self._resetTaskState("Claude window closed")
		log.info("Claude Desktop Access detached after the Claude window closed")
		return True

	def _setConversationMode(self, mode, reason, authoritative=False):
		"""Update the active mode without letting Claude's host document override its switch."""
		mode = str(mode or "").casefold()
		if mode not in ("claude", "code", "cowork"):
			return False
		if authoritative:
			# An exact accessibility event is newer than any worker query already in
			# flight. Invalidate that result so it cannot restore the preceding mode.
			pendingProbe = getattr(self, "_conversationModeProbePendingGeneration", 0)
			activationProbe = getattr(self, "_conversationModeProbeActivationGeneration", 0)
			if pendingProbe and pendingProbe != activationProbe:
				self._conversationModeProbeGeneration += 1
				self._conversationModeProbePendingGeneration = 0
			self._conversationModeObserved = True
			self._conversationModeObservedAt = time.monotonic()
		previousMode = self._conversationMode
		if mode == previousMode:
			return False
		if previousMode:
			self._cancelChatHistoryExpansion()
			self._pendingChatHistoryAction = None
			if self._chatHistoryActionTimer:
				self._chatHistoryActionTimer.Stop()
				self._chatHistoryActionTimer = None
			if self._chatHistoryDialog:
				self._chatHistoryDialog.Close()
			self._resetTaskState("conversation mode changed")
		self._conversationMode = mode
		self._conversationModeChangedAt = time.monotonic()
		self._chatHistoryCacheCurrent[mode] = False
		self._pendingChatHistorySnapshots[mode] = None
		self._pendingChatHistorySnapshotAt[mode] = 0.0
		self._chatHistoryMoreAvailable[mode] = False
		self._recentHistoryShowMoreOrdinals[mode] = 0
		self._unifiedRecentCounts[mode] = 0
		self._chatHistoryScanGenerations[mode] = 0
		log.info(
			"Claude Desktop Access conversation mode changed from %s to %s (%s)",
			previousMode or "unknown", mode, reason,
		)
		return True

	def _chatHistoryTitles(self, mode=None):
		"""Return only the recent titles cached for one conversation mode."""
		mode = mode or self._conversationMode
		return self._chatHistoryCaches.get(mode, ())

	def _activeCodeThreadTitles(self):
		"""Claude history comes from exposed controls, never unrelated local indexes."""
		return ()

	def _modeSpecificRecentChatTitles(self, mode, unifiedTitles):
		return tuple(dict.fromkeys(unifiedTitles))

	def _cacheChatHistoryScan(self, mode, recentTitles=None, archivedTitles=None):
		"""Store sidebar results without allowing one conversation mode to replace another."""
		if mode not in self._chatHistoryCaches:
			return
		if recentTitles is not None:
			recentTitles = tuple(recentTitles)
			wasCurrent = self._chatHistoryCacheCurrent[mode]
			changed = recentTitles != self._chatHistoryCaches[mode]
			self._chatHistoryCaches[mode] = recentTitles
			self._chatHistoryCacheCurrent[mode] = True
			if changed or not wasCurrent:
				otherMode = "code" if mode == "claude" else "claude"
				overlap = len(set(recentTitles).intersection(self._chatHistoryCaches[otherMode]))
				log.info(
					"Claude Desktop Access cached %d settled recent %s chats; overlap with %s: %d",
					len(recentTitles), mode, otherMode, overlap,
				)
		if archivedTitles is not None:
			self._archivedChatHistoryCaches[mode] = tuple(archivedTitles)
			self._archivedChatHistoryLoaded[mode] = True

	def _refreshChatHistoryData(self, mode):
		if mode != self._conversationMode:
			return (), (), False
		archivedTitles, archivedLoaded = self._loadArchivedChatHistory(mode)
		return self._chatHistoryTitles(mode), archivedTitles, archivedLoaded

	def _cancelChatHistoryExpansion(self):
		if self._chatHistoryExpansionTimer:
			self._chatHistoryExpansionTimer.Stop()
			self._chatHistoryExpansionTimer = None
		self._pendingChatHistoryExpansion = None

	def _scheduleChatHistoryExpansion(self, delay):
		if self._chatHistoryExpansionTimer:
			self._chatHistoryExpansionTimer.Stop()
		self._chatHistoryExpansionTimer = wx.CallLater(delay, self._continueChatHistoryExpansion)

	def _startChatHistoryExpansion(self, mode):
		"""Load bounded native Recents pages before presenting the history dialog."""
		if self._pendingChatHistoryExpansion:
			ui.message(_("Recent chat history is already loading"))
			return True
		if not self._chatHistoryMoreAvailable.get(mode, False):
			return False
		agentName = modeDisplayName(mode)
		self._pendingChatHistoryExpansion = {
			"mode": mode,
			"pages": 0,
			"lastCount": self._unifiedRecentCounts.get(mode, 0),
			"lastGeneration": self._chatHistoryScanGenerations.get(mode, 0),
			"awaitingGrowth": False,
			"staleScans": 0,
			"settleScans": 0,
		}
		ui.message(_("Loading additional {agent} recent chats").format(agent=agentName))
		self._scheduleChatHistoryExpansion(50)
		return True

	def _finishChatHistoryExpansion(self, mode, limitReached=False, failed=False):
		state = self._pendingChatHistoryExpansion or {}
		pages = state.get("pages", 0)
		self._cancelChatHistoryExpansion()
		agentName = modeDisplayName(mode)
		count = len(self._chatHistoryTitles(mode))
		moreAvailable = self._chatHistoryMoreAvailable.get(mode, False)
		if failed:
			ui.message(_(
				"More recent chats could not be loaded. Showing the {count} currently available {agent} chats"
			).format(count=count, agent=agentName))
		elif limitReached:
			ui.message(_(
				"Loaded {count} {agent} recent chats. More are available; open history again to continue loading"
			).format(count=count, agent=agentName))
		else:
			ui.message(_("Loaded {count} currently available {agent} recent chats").format(
				count=count, agent=agentName,
			))
		log.info(
			"Claude Desktop Access finished %s recent-history expansion after %d pages; "
			"kept %d mode-specific chats; more available: %s; failed: %s",
			mode, pages, count, moreAvailable, bool(failed),
		)
		if mode == self._conversationMode and _isClaudeObject(api.getFocusObject()):
			self._showChatHistoryDialog(mode)

	def _continueChatHistoryExpansion(self):
		"""Advance native Show more one page at a time without an unbounded UI loop."""
		self._chatHistoryExpansionTimer = None
		state = self._pendingChatHistoryExpansion
		if not state:
			return
		mode = state["mode"]
		if mode != self._conversationMode or self._buffer is None or not _isClaudeObject(api.getFocusObject()):
			self._cancelChatHistoryExpansion()
			ui.message(_("Recent chat history loading stopped because Claude is no longer focused"))
			return
		currentCount = self._unifiedRecentCounts.get(mode, 0)
		currentGeneration = self._chatHistoryScanGenerations.get(mode, 0)
		moreAvailable = self._chatHistoryMoreAvailable.get(mode, False)
		if state["awaitingGrowth"]:
			if currentGeneration <= state["lastGeneration"] or currentCount <= state["lastCount"]:
				state["staleScans"] += 1
				if state["staleScans"] <= CHAT_HISTORY_EXPANSION_MAX_STALE_SCANS:
					self._schedulePoll(delay=150, requestInspection=True)
					self._scheduleChatHistoryExpansion(CHAT_HISTORY_EXPANSION_RETRY_MILLISECONDS)
					return
				self._finishChatHistoryExpansion(mode, failed=True)
				return
			state["awaitingGrowth"] = False
			state["staleScans"] = 0
			state["lastCount"] = currentCount
			state["lastGeneration"] = currentGeneration
		limitReached = state["pages"] >= CHAT_HISTORY_EXPANSION_MAX_PAGES and moreAvailable
		if not moreAvailable or limitReached:
			if not self._chatHistoryCacheCurrent.get(mode, False):
				state["settleScans"] += 1
				if state["settleScans"] <= CHAT_HISTORY_EXPANSION_MAX_STALE_SCANS:
					self._schedulePoll(delay=150, requestInspection=True)
					self._scheduleChatHistoryExpansion(CHAT_HISTORY_EXPANSION_RETRY_MILLISECONDS)
					return
			self._finishChatHistoryExpansion(
				mode,
				limitReached=limitReached,
				failed=not self._chatHistoryCacheCurrent.get(mode, False),
			)
			return
		try:
			button = self._recentHistoryShowMoreButton(mode)
			if button is None:
				raise LookupError("Recents Show more button not found")
			button.doAction()
		except Exception:
			log.debugWarning("Claude Desktop Access could not activate Recents Show more", exc_info=True)
			self._finishChatHistoryExpansion(mode, failed=True)
			return
		state["pages"] += 1
		state["lastCount"] = currentCount
		state["lastGeneration"] = currentGeneration
		state["awaitingGrowth"] = True
		state["staleScans"] = 0
		self._chatHistoryCacheCurrent[mode] = False
		self._pendingChatHistorySnapshots[mode] = None
		self._pendingChatHistorySnapshotAt[mode] = 0.0
		self._chatHistoryMoreAvailable[mode] = False
		self._recentHistoryShowMoreOrdinals[mode] = 0
		self._bufferDirty = True
		self._schedulePoll(delay=150, requestInspection=True)
		log.info(
			"Claude Desktop Access requested recent-history page %d for %s; "
			"%d unified entries were visible",
			state["pages"], mode, currentCount,
		)
		self._scheduleChatHistoryExpansion(CHAT_HISTORY_EXPANSION_DELAY_MILLISECONDS)

	def _loadArchivedChatHistory(self, mode=None):
		mode = mode or self._conversationMode
		return (self._archivedChatHistoryCaches.get(mode, ()), self._archivedChatHistoryLoaded.get(mode, False))

	def _chatButtonObject(self, title):
		position = self._buffer.makeTextInfo(textInfos.POSITION_FIRST)
		if not position.find(title, reverse=False, caseSensitive=True):
			return None
		obj = getattr(position, "NVDAObjectAtStart", None)
		for _ in range(8):
			if obj is None:
				break
			if getattr(obj, "role", None) in (Role.BUTTON, Role.LINK):
				return obj if chatTitleMatches(title, getattr(obj, "name", ""), titleFoundInsideButton=True) else None
			obj = getattr(obj, "parent", None)
		return None

	def _exactNamedButtonObject(self, name, ordinal=1):
		"""Resolve one exact button occurrence without walking Chromium's full object tree."""
		if self._buffer is None or ordinal < 1:
			return None
		wantedName = " ".join(str(name or "").casefold().split())
		if not wantedName:
			return None
		position = self._buffer.makeTextInfo(textInfos.POSITION_FIRST)
		found = 0
		seen = set()
		for _ in range(64):
			if not position.find(name, reverse=False, caseSensitive=False):
				break
			obj = getattr(position, "NVDAObjectAtStart", None)
			for _ in range(8):
				if obj is None or getattr(obj, "role", None) == Role.BUTTON:
					break
				obj = getattr(obj, "parent", None)
			if getattr(obj, "role", None) == Role.BUTTON and (
				" ".join(str(getattr(obj, "name", "") or "").casefold().split()) == wantedName
			):
				windowHandle = getattr(obj, "windowHandle", 0)
				uniqueId = getattr(obj, "IA2UniqueID", 0)
				identity = (windowHandle, uniqueId) if uniqueId else id(obj)
				if identity not in seen:
					seen.add(identity)
					found += 1
					if found == ordinal:
						return obj
			try:
				position.collapse(end=True)
				if position.move(textInfos.UNIT_CHARACTER, 1) == 0:
					break
			except Exception:
				break
		return None

	def _recentHistoryShowMoreButton(self, mode):
		"""Return the Show more button proven by the latest Recents-region scan."""
		if not self._chatHistoryMoreAvailable.get(mode, False):
			return None
		ordinal = self._recentHistoryShowMoreOrdinals.get(mode, 0)
		return self._exactNamedButtonObject("Show more", ordinal)

	def _namedChatActionButton(self, chatButton, action):
		"""Resolve the action exposed beside the focused chat, not matching transcript text."""
		container = getattr(chatButton, "parent", None)
		for _ in range(2):
			if container is None:
				break
			pending = [getattr(container, "firstChild", None)]
			seen = set()
			while pending and len(seen) < 32:
				obj = pending.pop()
				if obj is None or id(obj) in seen:
					continue
				seen.add(id(obj))
				if obj is not chatButton and getattr(obj, "role", None) == Role.BUTTON and chatActionMatches(
					action, getattr(obj, "name", ""),
				):
					return obj
				nextObject = getattr(obj, "next", None)
				firstChild = getattr(obj, "firstChild", None)
				if nextObject is not None:
					pending.append(nextObject)
				if firstChild is not None:
					pending.append(firstChild)
			container = getattr(container, "parent", None)
		return None

	def _voiceControlFromObject(self, obj, wantedKinds):
		"""Return an exact voice control from an object or one of its ancestors."""
		wantedKinds = set(wantedKinds)
		for _ in range(8):
			if obj is None:
				break
			kind = voiceControlKind(getattr(obj, "name", ""))
			roleName = _roleName(obj)
			if kind and roleName in ("button", "togglebutton"):
				# Claude currently exposes Mute microphone as a toggle button.
				# Some builds retain that name when pressed instead of renaming it
				# Unmute microphone, so the pressed state determines the next action.
				if kind == "mute" and roleName == "togglebutton":
					states = getattr(obj, "states", ()) or ()
					if State.PRESSED in states or State.CHECKED in states:
						kind = "unmute"
				if kind in wantedKinds:
					return obj, kind
			obj = getattr(obj, "parent", None)
		return None, ""

	def _voiceControlObject(self, wantedKinds):
		"""Find a native voice control without scanning the full Chromium object tree."""
		wantedKinds = tuple(wantedKinds)
		focus = api.getFocusObject()
		for candidate in (focus, *(api.getFocusAncestors() or ())):
			control, kind = self._voiceControlFromObject(candidate, wantedKinds)
			if control is not None:
				return control, kind
		self._rememberBuffer(focus)
		if self._buffer is None:
			return None, ""
		for expectedKind, label in VOICE_CONTROL_SEARCH_LABELS:
			if expectedKind not in wantedKinds:
				continue
			try:
				position = self._buffer.makeTextInfo(textInfos.POSITION_LAST)
				if not position.find(label, reverse=True, caseSensitive=False):
					continue
				control, kind = self._voiceControlFromObject(
					getattr(position, "NVDAObjectAtStart", None), wantedKinds,
				)
				if control is not None:
					return control, kind
			except Exception:
				continue
		return None, ""

	def _cancelVoiceControlConfirmation(self):
		if self._voiceControlConfirmationTimer:
			self._voiceControlConfirmationTimer.Stop()
			self._voiceControlConfirmationTimer = None
		self._pendingVoiceControlConfirmation = None

	def _scheduleVoiceControlConfirmation(self, actionKind):
		self._cancelVoiceControlConfirmation()
		self._pendingVoiceControlConfirmation = (actionKind, 0)
		self._voiceControlConfirmationTimer = wx.CallLater(
			VOICE_CONTROL_CONFIRMATION_DELAY_MS, self._confirmVoiceControlAction,
		)

	def _confirmVoiceControlAction(self):
		"""Confirm the resulting native button state before reporting success."""
		self._voiceControlConfirmationTimer = None
		pending = self._pendingVoiceControlConfirmation
		if not pending:
			return
		actionKind, attempt = pending
		expectedKinds = {
			"start": ("stop",),
			"stop": ("start",),
			"mute": ("unmute",),
			"unmute": ("mute",),
		}
		try:
			control, resultingKind = self._voiceControlObject(expectedKinds[actionKind])
		except Exception:
			control, resultingKind = None, ""
		if control is not None and resultingKind in expectedKinds[actionKind]:
			self._pendingVoiceControlConfirmation = None
			messages = {
				"start": _("Voice mode started"),
				"stop": _("Voice mode ended"),
				"mute": _("Microphone muted"),
				"unmute": _("Microphone unmuted"),
			}
			ui.message(messages[actionKind])
			log.info("Claude Desktop Access confirmed Claude voice control: %s", actionKind)
			return
		attempt += 1
		if attempt < VOICE_CONTROL_CONFIRMATION_ATTEMPTS and _isClaudeObject(api.getFocusObject()):
			self._pendingVoiceControlConfirmation = (actionKind, attempt)
			self._voiceControlConfirmationTimer = wx.CallLater(
				VOICE_CONTROL_CONFIRMATION_DELAY_MS, self._confirmVoiceControlAction,
			)
			return
		self._pendingVoiceControlConfirmation = None
		failure = (
			_("Microphone state could not be confirmed")
			if actionKind in ("mute", "unmute")
			else _("Voice mode state could not be confirmed")
		)
		ui.message(failure)
		log.debugWarning("Claude Desktop Access could not confirm Claude voice control: %s", actionKind)

	def _activateVoiceControl(self, wantedKinds):
		"""Activate an exact native control and verify the resulting state."""
		try:
			self._cancelVoiceControlConfirmation()
			control, kind = self._voiceControlObject(wantedKinds)
			if control is None:
				if set(wantedKinds) == {"mute", "unmute"}:
					ui.message(_("Microphone control is unavailable. Start voice mode first"))
				else:
					ui.message(_("Voice mode control is not available in this Claude view"))
				return
			control.doAction()
			messages = {
				"start": _("Starting voice mode"),
				"stop": _("Ending voice mode"),
				"mute": _("Muting microphone"),
				"unmute": _("Unmuting microphone"),
			}
			ui.message(messages[kind])
			self._scheduleVoiceControlConfirmation(kind)
			log.info("Claude Desktop Access requested Claude voice control: %s", kind)
		except Exception:
			log.debugWarning("Claude Desktop Access could not activate a Claude voice control", exc_info=True)
			ui.message(_("The Claude voice control could not be activated"))

	def _startDirectChatAction(self, title, action):
		if self._chatActionRetryTimer:
			self._chatActionRetryTimer.Stop()
			self._chatActionRetryTimer = None
		self._pendingDirectChatAction = (title, action, 0)
		self._retryDirectChatAction()

	def _retryDirectChatAction(self):
		self._chatActionRetryTimer = None
		pending = self._pendingDirectChatAction
		if not pending:
			return
		title, action, attempt = pending
		try:
			chatButton = self._chatButtonObject(title)
			if chatButton is None:
				raise LookupError("selected chat button not found")
			chatButton.setFocus()
			if action == "focusActions":
				actionButton = self._namedChatActionButton(chatButton, "pin")
				if actionButton is None:
					actionButton = self._namedChatActionButton(chatButton, "archive")
			else:
				actionButton = self._namedChatActionButton(chatButton, action)
			if actionButton is not None:
				if action == "focusActions":
					actionButton.setFocus()
				else:
					actionButton.doAction()
				self._pendingDirectChatAction = None
				if action == "focusActions":
					focusedAction = " ".join(str(getattr(actionButton, "name", "") or "").split())
					log.info("Claude Desktop Access focused selected chat action: %s", focusedAction)
				else:
					ui.message(_("Chat action opened"))
					log.info("Claude Desktop Access activated the selected chat action: %s", action)
				return
		except Exception:
			if attempt >= 11:
				self._pendingDirectChatAction = None
				if action == "focusActions":
					log.debugWarning("Claude Desktop Access could not focus Pin, Unpin, or Archive", exc_info=True)
					ui.message(_("The selected chat's Pin or Archive button could not be focused"))
				else:
					log.debugWarning("Claude Desktop Access could not activate the selected chat action", exc_info=True)
					ui.message(_("The selected chat action could not be opened"))
				return
		# A missing action control is a normal transient state while Chromium updates
		# the selected sidebar row, so it does not raise above. Apply the same retry
		# limit here; otherwise this path can schedule a main-thread timer forever.
		if attempt >= 11:
			self._pendingDirectChatAction = None
			if action == "focusActions":
				log.debugWarning("Claude Desktop Access could not find Pin, Unpin, or Archive after retrying")
				ui.message(_("The selected chat's Pin or Archive button could not be focused"))
			else:
				log.debugWarning("Claude Desktop Access could not find the selected chat action after retrying")
				ui.message(_("The selected chat action could not be opened"))
			return
		self._pendingDirectChatAction = (title, action, attempt + 1)
		self._chatActionRetryTimer = wx.CallLater(100, self._retryDirectChatAction)

	def _scheduleUnarchiveButtonFocus(self):
		self._unarchiveFocusAttempts = 0
		if self._unarchiveFocusTimer:
			self._unarchiveFocusTimer.Stop()
		self._unarchiveFocusTimer = wx.CallLater(100, self._focusUnarchiveButton)

	def _focusUnarchiveButton(self):
		"""Focus Code's confirmation after its new document becomes accessible."""
		self._unarchiveFocusTimer = None
		self._unarchiveFocusAttempts += 1
		try:
			if self._buffer:
				position = self._buffer.makeTextInfo(textInfos.POSITION_FIRST)
				if position.find("Unarchive and open", reverse=False, caseSensitive=False):
					obj = getattr(position, "NVDAObjectAtStart", None)
					for _ in range(8):
						if obj is None or getattr(obj, "role", None) == Role.BUTTON:
							break
						obj = getattr(obj, "parent", None)
					if getattr(obj, "role", None) == Role.BUTTON and " ".join(
						str(getattr(obj, "name", "") or "").casefold().split()
					) == "unarchive and open":
						obj.setFocus()
						log.info("Claude Desktop Access focused the Unarchive and open button")
						return
		except Exception:
			log.debugWarning("Claude Desktop Access could not yet focus the unarchive confirmation", exc_info=True)
		if self._unarchiveFocusAttempts < 25:
			self._unarchiveFocusTimer = wx.CallLater(150, self._focusUnarchiveButton)
		else:
			ui.message(_("Unarchive confirmation opened; move to the Unarchive and open button"))

	def _usageLimitTextFromObject(self, obj):
		"""Collect only a small Claude alert subtree when its own text is incomplete."""
		if not _isClaudeObject(obj):
			return ""
		parts = []
		seenText = set()

		def addObjectText(candidate):
			for attribute in ("name", "value", "description"):
				try:
					value = " ".join(str(getattr(candidate, attribute, "") or "").split())
				except Exception:
					continue
				if value and value not in seenText:
					seenText.add(value)
					parts.append(value[:2000])

		container = None
		current = obj
		seenObjects = set()
		for _ in range(10):
			if current is None or id(current) in seenObjects:
				break
			seenObjects.add(id(current))
			addObjectText(current)
			if _roleName(current) in ("alert", "dialog"):
				container = current
				break
			try:
				current = getattr(current, "parent", None)
			except Exception:
				break
		if container is None:
			return " ".join(parts)

		# Usage pop-overs are small, but Chromium can split the message and its
		# choices across siblings. Bound this rare traversal so an accessibility
		# provider problem can never stall NVDA's main thread.
		pending = [container]
		seenObjects.clear()
		while pending and len(seenObjects) < 80 and sum(map(len, parts)) < 6000:
			current = pending.pop()
			if current is None or id(current) in seenObjects:
				continue
			seenObjects.add(id(current))
			addObjectText(current)
			try:
				nextObject = getattr(current, "next", None) if current is not container else None
				firstChild = getattr(current, "firstChild", None)
			except Exception:
				continue
			if nextObject is not None:
				pending.append(nextObject)
			if firstChild is not None:
				pending.append(firstChild)
		return " ".join(parts)

	def _usageLimitObjectIsPopup(self, obj):
		"""Return whether an object is within an ARIA alert or dialog."""
		seen = set()
		current = obj
		for _ in range(10):
			if current is None or id(current) in seen:
				return False
			seen.add(id(current))
			if _roleName(current) in ("alert", "dialog"):
				return True
			try:
				current = getattr(current, "parent", None)
			except Exception:
				return False
		return False

	def _announceUsageLimit(self, obj, eventText=""):
		"""End local activity and announce an exhausted usage allowance once."""
		if not _isClaudeObject(obj):
			return False
		objectRole = _roleName(obj)
		if objectRole == "editabletext":
			return False
		text = " ".join(str(eventText or "").split())
		if not text:
			try:
				text = " ".join(str(getattr(obj, "name", "") or "").split())
			except Exception:
				text = ""
		notice = usageLimitNotice(text, _)
		lower = text.casefold()
		inPopup = self._usageLimitObjectIsPopup(obj) if notice or any(
			marker in lower for marker in ("usage", "limit", "credit", "upgrade", "try again")
		) or objectRole in ("alert", "dialog") else False
		if not notice and not inPopup:
			# Most events in the Claude window are unrelated and can return after
			# reading only the local accessible name.
			if not any(
				marker in lower for marker in ("usage", "limit", "credit", "upgrade", "try again")
			):
				return False
		combinedText = self._usageLimitTextFromObject(obj)
		combinedNotice = usageLimitNotice(combinedText, _)
		if combinedNotice:
			text, notice = combinedText, combinedNotice
		if not notice:
			return False
		# Outside a semantically exposed pop-over, require the distinctive full
		# Claude error. This prevents a user's prompt or an assistant response
		# discussing usage limits from being mistaken for the account state.
		lower = text.casefold()
		detailCount = sum((
			bool(re.search(r"\bupgrade(?:\s+to\s+pro|\s+(?:your\s+)?plan)?\b", lower)),
			bool(re.search(r"\b(?:add|buy|purchase)(?:\s+some)?(?:\s+more)?\s+credits?\b", lower)),
			bool("try again" in lower or "next reset" in lower),
		))
		if not inPopup and not (
			"claude.ai/settings/usage" in lower or detailCount >= 2
		):
			return False
		return self._applyUsageLimitNotice(notice)

	def _applyUsageLimitNotice(self, notice):
		"""Apply a terminal usage-limit state independently of its event source."""
		self._pluginProgressOwnedBusy.clear()
		self._pendingResponseCompletionAt = 0.0
		self._pendingUserMessageIncrease = False
		self._stopControlVisible = False
		self._promptHadText = False
		self._lastScannedLabel = ""
		self._lastLabel = ""
		self._latestResponseMarker = None
		self._responseMarkerInitialized = False
		self._setBusy(False, "usage limit reached")
		self._active = False
		self._activeCategory = "attention"
		if self._usageLimitActive and notice == self._lastUsageLimitNotice:
			return True
		self._usageLimitActive = True
		self._lastUsageLimitNotice = notice
		self._latestMessage = notice
		self._latestFullMessage = notice
		self._speakOnce(
			notice, "attention", "attention", priority="urgent", brailleMessage=notice,
		)
		log.info("Claude Desktop Access detected a terminal usage-limit notice")
		return True

	def _popupDialogFromObject(self, obj):
		for _ in range(10):
			if obj is None or getattr(obj, "role", None) == Role.DIALOG:
				return obj
			obj = getattr(obj, "parent", None)
		return None

	def _schedulePopupDialogFocus(self, obj):
		if not _isClaudeObject(obj):
			return
		try:
			dialog = self._popupDialogFromObject(obj)
		except Exception:
			log.debugWarning("Claude Desktop Access could not inspect a possible Claude pop-up", exc_info=True)
			return
		if dialog is None or dialog is self._pendingPopupDialog or dialog is self._lastFocusedPopupDialog:
			return
		self._pendingPopupDialog = dialog
		if self._popupFocusTimer:
			self._popupFocusTimer.Stop()
		self._popupFocusTimer = wx.CallLater(50, self._focusPopupDialog)

	def _focusPopupDialog(self):
		"""Move focus into a newly displayed Claude dialog without activating a control."""
		self._popupFocusTimer = None
		dialog, self._pendingPopupDialog = self._pendingPopupDialog, None
		if dialog is None:
			return
		try:
			focused = api.getFocusObject()
			current = focused
			for _ in range(12):
				if current is dialog:
					self._lastFocusedPopupDialog = dialog
					return
				current = getattr(current, "parent", None) if current is not None else None
			pending = [dialog]
			seen = set()
			objects = []
			while pending and len(seen) < 100:
				obj = pending.pop()
				if obj is None or id(obj) in seen:
					continue
				seen.add(id(obj))
				objects.append(obj)
				nextObject = getattr(obj, "next", None) if obj is not dialog else None
				firstChild = getattr(obj, "firstChild", None)
				if nextObject is not None:
					pending.append(nextObject)
				if firstChild is not None:
					pending.append(firstChild)
			text = " ".join(str(getattr(obj, "name", "") or "") for obj in objects)
			permissionPrompt = isPermissionPromptText(text)
			interactiveRoles = (
				Role.EDITABLETEXT, Role.COMBOBOX, Role.LIST, Role.TREEVIEW,
				Role.CHECKBOX, Role.RADIOBUTTON, Role.BUTTON,
			)
			candidates = [obj for obj in objects if getattr(obj, "role", None) in interactiveRoles]
			if permissionPrompt:
				decisions = [obj for obj in candidates if isPermissionDecisionLabel(getattr(obj, "name", ""))]
				candidates = decisions or candidates
			else:
				useful = [obj for obj in candidates if " ".join(
					str(getattr(obj, "name", "") or "").casefold().split()
				) not in ("close", "cancel", "dismiss")]
				candidates = useful or candidates
			for obj in candidates:
				try:
					obj.setFocus()
					self._lastFocusedPopupDialog = dialog
					log.info("Claude Desktop Access focused a Claude pop-up dialog control")
					return
				except Exception:
					continue
			dialog.setFocus()
			self._lastFocusedPopupDialog = dialog
			log.info("Claude Desktop Access focused a Claude pop-up dialog")
		except Exception:
			log.debugWarning("Claude Desktop Access could not focus the Claude pop-up dialog", exc_info=True)

	def _announcePluginInstallProgress(self, obj):
		try:
			if getattr(obj, "role", None) != Role.PROGRESSBAR or not _isClaudeObject(obj):
				return False
			parts = []
			current = obj
			for _ in range(7):
				if current is None:
					break
				for attribute in ("name", "value", "description"):
					value = " ".join(str(getattr(current, attribute, "") or "").split())
					if value and value not in parts:
						parts.append(value)
				current = getattr(current, "parent", None)
			parsed = pluginInstallProgress(" ".join(parts))
		except Exception:
			log.debugWarning("Claude Desktop Access could not inspect a plug-in progress event", exc_info=True)
			return False
		if parsed is None:
			return False
		identity, percent, bucket = parsed
		if self._pluginProgressBuckets.get(identity, object()) == bucket:
			return True
		if len(self._pluginProgressBuckets) >= 32 and identity not in self._pluginProgressBuckets:
			expiredIdentity = next(iter(self._pluginProgressBuckets))
			self._pluginProgressBuckets.pop(expiredIdentity)
			self._pluginProgressOwnedBusy.discard(expiredIdentity)
		self._pluginProgressBuckets[identity] = bucket
		if percent is None:
			message = _("Plugin installation in progress")
		elif percent >= 100:
			message = _("Plugin installation complete")
		else:
			message = _("Plugin installation {percent} percent").format(percent=percent)
		complete = percent is not None and percent >= 100
		busy, ownsBusy = pluginProgressBusyTransition(
			self._busy, identity in self._pluginProgressOwnedBusy, complete,
		)
		if ownsBusy:
			self._pluginProgressOwnedBusy.add(identity)
		else:
			self._pluginProgressOwnedBusy.discard(identity)
		self._setBusy(busy, "plugin installation progress")
		self._activeCategory = "tool"
		self._latestMessage = self._latestFullMessage = message
		self._speakOnce(message, "tool", "tool", brailleMessage=message)
		log.info("Claude Desktop Access announced plug-in installation progress")
		return True

	def _rememberEmbeddedBrowserObject(self, obj):
		"""Retain a browser object and its virtual buffer without changing navigation."""
		try:
			if _isDefunctObject(obj) or not _isEmbeddedBrowserObject(obj):
				return False
			self._lastEmbeddedBrowserObject = obj
			buffer = getattr(obj, "treeInterceptor", None)
			if buffer is not None:
				self._embeddedBrowserBuffer = buffer
			if _roleName(obj) == "document":
				title = embeddedBrowserTitle(getattr(obj, "name", ""))
				if title:
					self._embeddedBrowserPageTitle = title
			return True
		except Exception:
			return False

	def _resetEmbeddedBrowserProgress(self):
		"""Discard page-specific loading state after browser exit or app shutdown."""
		if self._embeddedBrowserLoadTimer:
			self._embeddedBrowserLoadTimer.Stop()
			self._embeddedBrowserLoadTimer = None
		self._embeddedBrowserLoadGeneration += 1
		self._embeddedBrowserLoadingPercent = None
		self._embeddedBrowserLoading = False
		self._embeddedBrowserBusySeen = False
		self._embeddedBrowserLoadIdentity = ""
		self._embeddedBrowserCompletedIdentity = ""
		self._embeddedBrowserProgressBuckets.clear()

	def _embeddedBrowserDocumentIdentity(self, obj):
		"""Return a stable-enough identity without walking or reading the page."""
		try:
			title = embeddedBrowserTitle(getattr(obj, "name", ""))
			windowHandle = int(getattr(obj, "windowHandle", 0) or 0)
			uniqueId = int(getattr(obj, "IA2UniqueID", 0) or 0)
		except Exception:
			title = ""
			windowHandle = 0
			uniqueId = 0
		return "{window}:{unique}:{title}".format(
			window=windowHandle, unique=uniqueId, title=title.casefold(),
		), title

	def _scheduleEmbeddedBrowserLoadComplete(self, busy=False):
		if self._embeddedBrowserLoadTimer:
			self._embeddedBrowserLoadTimer.Stop()
		self._embeddedBrowserLoadGeneration += 1
		generation = self._embeddedBrowserLoadGeneration
		self._embeddedBrowserLoadTimer = wx.CallLater(
			BROWSER_BUSY_FALLBACK_MILLISECONDS if busy else BROWSER_LOAD_SETTLE_MILLISECONDS,
			self._completeEmbeddedBrowserLoading, generation,
		)

	def _startEmbeddedBrowserLoading(self, identity, title="", force=False, busy=False):
		"""Announce one load start and schedule a quiet fallback completion."""
		if not _settings()["announceEmbeddedBrowserProgress"]:
			return False
		identity = str(identity or "embedded browser")[:400]
		if title:
			self._embeddedBrowserPageTitle = title
		if busy:
			self._embeddedBrowserBusySeen = True
		if self._embeddedBrowserLoading:
			if identity != self._embeddedBrowserLoadIdentity:
				self._embeddedBrowserLoadIdentity = identity
				self._embeddedBrowserCompletedIdentity = ""
			self._scheduleEmbeddedBrowserLoadComplete(busy=self._embeddedBrowserBusySeen)
			return True
		if not force and identity == self._embeddedBrowserCompletedIdentity:
			return False
		self._embeddedBrowserLoading = True
		self._embeddedBrowserLoadingPercent = 0
		self._embeddedBrowserLoadIdentity = identity
		self._embeddedBrowserCompletedIdentity = ""
		self._embeddedBrowserNotice(_("Loading page"))
		self._scheduleEmbeddedBrowserLoadComplete(busy=self._embeddedBrowserBusySeen)
		log.info("Claude Desktop Access announced embedded browser load start")
		return True

	def _completeEmbeddedBrowserLoading(self, generation=None):
		"""Report completion from a native busy-state change, progress event, or settle timer."""
		if generation is not None and generation != self._embeddedBrowserLoadGeneration:
			return False
		if generation is None and self._embeddedBrowserLoadTimer:
			self._embeddedBrowserLoadTimer.Stop()
		self._embeddedBrowserLoadTimer = None
		if not self._embeddedBrowserLoading:
			return False
		self._embeddedBrowserLoading = False
		self._embeddedBrowserBusySeen = False
		self._embeddedBrowserLoadingPercent = 100
		self._embeddedBrowserCompletedIdentity = self._embeddedBrowserLoadIdentity
		if _settings()["announceEmbeddedBrowserProgress"]:
			self._embeddedBrowserNotice(_("Loading complete"))
			log.info("Claude Desktop Access announced embedded browser load completion")
		return True

	def _noteEmbeddedBrowserDocument(self, obj, force=False):
		"""Observe a nested document without altering focus, actions, or browse mode."""
		if _roleName(obj) != "document" or not _isEmbeddedBrowserObject(obj):
			return False
		identity, title = self._embeddedBrowserDocumentIdentity(obj)
		try:
			busy = State.BUSY in (getattr(obj, "states", ()) or ())
		except Exception:
			busy = False
		return self._startEmbeddedBrowserLoading(identity, title, force=force, busy=busy)

	def _updateEmbeddedBrowserDocumentBusyState(self, obj):
		"""Use Chromium's native busy document state when it is exposed."""
		if _roleName(obj) != "document" or not _isEmbeddedBrowserObject(obj):
			return False
		identity, title = self._embeddedBrowserDocumentIdentity(obj)
		try:
			busy = State.BUSY in (getattr(obj, "states", ()) or ())
		except Exception:
			busy = False
		if busy:
			return self._startEmbeddedBrowserLoading(identity, title, force=True, busy=True)
		if self._embeddedBrowserLoading and self._embeddedBrowserBusySeen:
			return self._completeEmbeddedBrowserLoading()
		return False

	def _embeddedBrowserTraversalStart(self):
		"""Return one explicit scan root and whether that root is already in the browser."""
		try:
			focus = api.getFocusObject()
		except Exception:
			return None, False
		candidates = []
		if _isClaudeObject(focus):
			candidates.append(focus)
		if self._lastEmbeddedBrowserObject is not None:
			candidates.append(self._lastEmbeddedBrowserObject)
		for candidate in candidates:
			try:
				unavailable = _isDefunctObject(candidate) or (
					"invisible" in self._browserObjectStateNames(candidate)
				)
				if unavailable:
					if candidate is self._lastEmbeddedBrowserObject:
						self._lastEmbeddedBrowserObject = None
						self._embeddedBrowserBuffer = None
					continue
				if not _isEmbeddedBrowserObject(candidate):
					continue
				buffer = getattr(candidate, "treeInterceptor", None)
				root = getattr(buffer, "rootNVDAObject", None)
				if root is not None and _isClaudeObject(root) and _isEmbeddedBrowserObject(root):
					self._embeddedBrowserBuffer = buffer
					return root, True
				top = candidate
				for _ in range(18):
					parent = getattr(top, "parent", None)
					if parent is None or not _isEmbeddedBrowserObject(parent):
						break
					top = parent
				return top, True
			except Exception:
				continue
		if not _isClaudeObject(focus):
			return None, False
		root = focus
		for _ in range(24):
			try:
				parent = getattr(root, "parent", None)
			except Exception:
				break
			if parent is None or not _isClaudeObject(parent):
				break
			root = parent
		return root, False

	def _browserObjectStateNames(self, obj):
		result = []
		try:
			states = getattr(obj, "states", ()) or ()
		except Exception:
			states = ()
		for state in states:
			name = str(getattr(state, "name", "") or str(state).rsplit(".", 1)[-1]).casefold()
			if name:
				result.append(name)
		return tuple(result)

	def _browserObjectLevel(self, obj):
		try:
			positionInfo = getattr(obj, "positionInfo", {}) or {}
			return positionInfo.get("level") or positionInfo.get("headingLevel")
		except Exception:
			return None

	def _cancelEmbeddedBrowserScan(self):
		if self._browserScanTimer:
			self._browserScanTimer.Stop()
			self._browserScanTimer = None
		self._browserScanState = None
		self._browserScanPurpose = ""

	def _startEmbeddedBrowserScan(self, purpose):
		"""Start a user-requested, time-sliced accessibility-tree scan."""
		self._cancelEmbeddedBrowserScan()
		root, rootInBrowser = self._embeddedBrowserTraversalStart()
		if root is None:
			if self._browserNavigatorDialog:
				self._browserNavigatorDialog.refreshFinished()
			ui.message(_("No embedded browser is available in the current Claude window"))
			return
		self._browserScanPurpose = purpose
		self._browserScanState = {
			"stack": [(root, rootInBrowser, 0, False)],
			"seen": set(),
			"retained": [],
			"found": False,
			"firstBrowserObject": None,
			"items": [],
			"signatureCounts": {},
			"snapshotLines": [],
			"title": "",
			"address": "",
			"objects": 0,
			"truncated": False,
		}
		if purpose != "navigatorRefresh":
			ui.message(_("Scanning the embedded browser"))
		self._browserScanTimer = wx.CallLater(
			BROWSER_SCAN_YIELD_MILLISECONDS, self._continueEmbeddedBrowserScan,
		)

	def _continueEmbeddedBrowserScan(self):
		"""Inspect a small slice and yield before NVDA speech or Braille can stall."""
		self._browserScanTimer = None
		state = self._browserScanState
		if not state:
			return
		started = time.monotonic()
		processed = 0
		while state["stack"] and state["objects"] < BROWSER_SCAN_MAX_OBJECTS:
			if processed >= BROWSER_SCAN_SLICE_OBJECTS or time.monotonic() - started >= BROWSER_SCAN_SLICE_SECONDS:
				break
			obj, parentInBrowser, parentDocumentCount, allowNext = state["stack"].pop()
			objectId = id(obj)
			if objectId in state["seen"]:
				continue
			state["seen"].add(objectId)
			state["retained"].append(obj)
			state["objects"] += 1
			processed += 1
			try:
				roleName = _roleName(obj)
			except Exception:
				roleName = ""
			fields = []
			for attribute in ("name", "description", "value"):
				try:
					fields.append(" ".join(str(getattr(obj, attribute, "") or "").split()))
				except Exception:
					fields.append("")
			name, description, value = fields
			documentCount = parentDocumentCount + (1 if roleName == "document" else 0)
			explicitContainer = isEmbeddedBrowserContainerText(name, description) and isEmbeddedBrowserContainerRole(roleName)
			inBrowser = bool(parentInBrowser or explicitContainer or documentCount >= 2)
			try:
				nextObject = getattr(obj, "next", None) if allowNext else None
			except Exception:
				nextObject = None
			if nextObject is not None:
				state["stack"].append((nextObject, parentInBrowser, parentDocumentCount, True))
			states = self._browserObjectStateNames(obj)
			if "defunct" in states or "invisible" in states:
				continue
			try:
				firstChild = getattr(obj, "firstChild", None)
			except Exception:
				firstChild = None
			if firstChild is not None:
				state["stack"].append((firstChild, inBrowser, documentCount, True))
			if not inBrowser:
				continue
			state["found"] = True
			if state["firstBrowserObject"] is None:
				state["firstBrowserObject"] = obj
			kind = embeddedBrowserControlKind(name, roleName)
			if roleName == "document" and not state["title"]:
				state["title"] = embeddedBrowserTitle(name)
			if not state["address"] and kind == "address":
				state["address"] = browserPageAddress(value, description, name)
			level = self._browserObjectLevel(obj)
			category = browserNavigatorCategory(roleName, kind)
			if category:
				if len(state["items"]) < BROWSER_SCAN_MAX_ITEMS:
					baseSignature = browserNavigatorSignature(category, roleName, name)
					occurrence = state["signatureCounts"].get(baseSignature, 0) + 1
					state["signatureCounts"][baseSignature] = occurrence
					label = browserNavigatorItemLabel(
						category, name, roleName, value, level, states, _,
					)
					state["items"].append({
						"label": label,
						"category": category,
						"role": roleName,
						"kind": kind,
						"signature": browserNavigatorSignature(category, roleName, name, occurrence),
						"object": obj,
						"actionable": bool(
							category in ("links", "buttons")
							or roleName in ("checkbox", "combobox", "listbox", "radiobutton", "switch")
							or kind in ("back", "forward", "reload", "stop", "external", "close")
						),
					})
				else:
					state["truncated"] = True
			line = browserSnapshotLine(roleName, name, value, level, _)
			if line:
				if len(state["snapshotLines"]) < BROWSER_SNAPSHOT_MAX_LINES:
					state["snapshotLines"].append(line)
				else:
					state["truncated"] = True
		if state["stack"] and state["objects"] < BROWSER_SCAN_MAX_OBJECTS:
			self._browserScanTimer = wx.CallLater(
				BROWSER_SCAN_YIELD_MILLISECONDS, self._continueEmbeddedBrowserScan,
			)
			return
		if state["stack"]:
			state["truncated"] = True
		self._completeEmbeddedBrowserScan()

	def _completeEmbeddedBrowserScan(self):
		state, purpose = self._browserScanState, self._browserScanPurpose
		self._browserScanState = None
		self._browserScanPurpose = ""
		if not state:
			return
		self._browserScanCount += 1
		self._lastBrowserScanObjects = state["objects"]
		if state["truncated"]:
			self._browserScanLimitCount += 1
		firstBrowserObject = state["firstBrowserObject"]
		browserStillAvailable = bool(
			firstBrowserObject is not None
			and not _isDefunctObject(firstBrowserObject)
			and "invisible" not in self._browserObjectStateNames(firstBrowserObject)
		)
		if browserStillAvailable:
			self._lastEmbeddedBrowserObject = firstBrowserObject
		elif state["found"]:
			# Chromium can close or replace the browser while a time-sliced scan is
			# running. Never present retained objects from the disappeared page.
			state["found"] = False
			state["items"] = []
			state["snapshotLines"] = []
		title = state["title"] or self._embeddedBrowserPageTitle
		address = state["address"]
		if title:
			self._embeddedBrowserPageTitle = title
		self._embeddedBrowserAddress = address
		pageKey = browserPageIdentity(title, address)
		items = tuple(state["items"])
		result = {
			"found": state["found"], "title": title, "address": address,
			"pageKey": pageKey, "items": items, "snapshotLines": tuple(state["snapshotLines"]),
			"truncated": state["truncated"], "objects": state["objects"],
		}
		summaryTitle = redactSensitive(title) if _settings()["redactSensitive"] else title
		result["summary"] = browserPageSummary(
			summaryTitle, address, items, self._embeddedBrowserLoadingPercent, state["truncated"], _,
		)
		result["savedSignature"] = self._browserSavedLocations.get(pageKey, "")
		self._browserNavigatorResult = result
		try:
			self._dispatchEmbeddedBrowserScan(purpose, result)
		except Exception:
			log.debugWarning("Claude Desktop Access could not present embedded-browser scan results", exc_info=True)
			if self._browserNavigatorDialog:
				self._browserNavigatorDialog.refreshFinished()
			ui.message(_("Embedded-browser page information could not be presented"))

	def _dispatchEmbeddedBrowserScan(self, purpose, result):
		if not result["found"]:
			if self._browserNavigatorDialog:
				self._browserNavigatorDialog.refreshFinished()
			ui.message(_("Claude did not expose an accessible embedded-browser page"))
			return
		if purpose in ("navigator", "navigatorRefresh"):
			self._showOrUpdateBrowserNavigator(result)
		elif purpose == "summary":
			ui.message(result["summary"])
		elif purpose == "snapshot":
			self._showEmbeddedBrowserSnapshot(result)
		elif purpose == "external":
			self._openEmbeddedBrowserExternallyFromResult(result)

	def _displayBrowserText(self, text):
		return redactSensitive(text) if _settings()["redactSensitive"] else text

	def _showOrUpdateBrowserNavigator(self, result):
		redact = _settings()["redactSensitive"]
		title = self._displayBrowserText(result["title"] or _("Untitled page"))
		address = (
			browserAddressDomain(result["address"])
			if redact else result["address"]
		)
		items = result["items"]
		if redact:
			items = tuple({**item, "label": redactSensitive(item.get("label", ""))} for item in items)
		if self._browserNavigatorDialog:
			self._browserNavigatorDialog.updateSnapshot(
				title, address, result["summary"], items, result["truncated"], result["savedSignature"],
			)
			self._browserNavigatorDialog.refreshFinished()
			ui.message(_("Browser Navigator refreshed"))
			return
		gui.mainFrame.prePopup()
		try:
			self._browserNavigatorDialog = BrowserNavigatorDialog(
				gui.mainFrame, title, address, result["summary"], items,
				result["truncated"], result["savedSignature"], self._browserNavigatorAction,
				self._refreshEmbeddedBrowserNavigator, self._browserNavigatorClosed,
			)
			self._browserNavigatorDialog.Show()
		except Exception:
			self._browserNavigatorDialog = None
			gui.mainFrame.postPopup()
			raise
		log.info(
			"Claude Desktop Access opened Browser Navigator with %d items from %d objects",
			len(result["items"]), result["objects"],
		)

	def _refreshEmbeddedBrowserNavigator(self):
		self._startEmbeddedBrowserScan("navigatorRefresh")

	def _browserNavigatorClosed(self):
		if self._browserScanPurpose == "navigatorRefresh":
			# Closing a modeless navigator must also cancel its pending refresh;
			# otherwise the completed refresh would recreate the dialog.
			self._cancelEmbeddedBrowserScan()
		self._browserNavigatorDialog = None
		gui.mainFrame.postPopup()

	def _browserNavigatorAction(self, action, item):
		result = self._browserNavigatorResult
		if not result:
			ui.message(_("Browser Navigator page information is no longer available"))
			return
		if action == "summary":
			ui.message(result["summary"])
			return
		if action == "copyAddress":
			self._copyEmbeddedBrowserAddress(result.get("address", ""))
			return
		if self._browserActionTimer:
			self._browserActionTimer.Stop()
		self._pendingBrowserAction = (action, item, result)
		self._browserActionTimer = wx.CallLater(75, self._executeBrowserNavigatorAction)

	def _executeBrowserNavigatorAction(self):
		self._browserActionTimer = None
		pending, self._pendingBrowserAction = self._pendingBrowserAction, None
		if not pending:
			return
		action, item, result = pending
		if action == "snapshot":
			self._showEmbeddedBrowserSnapshot(result)
		elif action == "external":
			self._openEmbeddedBrowserExternallyFromResult(result)
		elif action == "returnPrompt":
			self._returnToClaudePrompt()
		elif action == "restore":
			signature = self._browserSavedLocations.get(result["pageKey"], "")
			restoredItem = next((entry for entry in result["items"] if entry["signature"] == signature), None)
			if restoredItem is None:
				ui.message(_("No remembered location is available for this browser page"))
			else:
				self._focusEmbeddedBrowserItem(restoredItem)
		elif action in ("move", "activate") and item is not None:
			self._focusEmbeddedBrowserItem(item, activate=action == "activate")

	def _rememberBrowserNavigatorLocation(self, item):
		if not _settings()["rememberEmbeddedBrowserLocations"]:
			return
		result = self._browserNavigatorResult
		if not result or not result.get("pageKey"):
			return
		pageKey = result["pageKey"]
		self._browserSavedLocations.pop(pageKey, None)
		self._browserSavedLocations[pageKey] = item.get("signature", "")
		while len(self._browserSavedLocations) > 16:
			self._browserSavedLocations.pop(next(iter(self._browserSavedLocations)))

	def _focusEmbeddedBrowserItem(self, item, activate=False):
		obj = item.get("object")
		try:
			if obj is None or _isDefunctObject(obj) or not _isClaudeObject(obj):
				raise LookupError("stale browser object")
			self._rememberBrowserNavigatorLocation(item)
			if activate:
				obj.doAction()
				ui.message(_("Activated {item}").format(item=item["label"]))
				return
			roleName = item.get("role", "")
			if roleName in (
				"button", "checkbutton", "checkbox", "combobox", "edit", "editabletext",
				"link", "listbox", "menuitem", "radiobutton", "slider", "spinbutton", "switch", "togglebutton",
			):
				obj.setFocus()
			else:
				buffer = getattr(obj, "treeInterceptor", None) or self._embeddedBrowserBuffer
				if buffer is not None:
					position = buffer.makeTextInfo(obj)
					position.collapse()
					position.updateCaret()
				api.setNavigatorObject(obj)
			ui.message(_("Moved to {item}").format(item=item["label"]))
		except Exception:
			log.debugWarning("Claude Desktop Access could not move to a Browser Navigator item", exc_info=True)
			ui.message(_("That browser item changed. Refresh Browser Navigator and try again"))

	def _showEmbeddedBrowserSnapshot(self, result):
		lines = result["snapshotLines"]
		title = result["title"]
		if _settings()["redactSensitive"]:
			lines = tuple(redactSensitive(line) for line in lines)
			title = redactSensitive(title)
		message = browserSnapshotText(title, result["address"], lines, result["truncated"], _)
		_showBrowseableMessageAtTop(message, _("Claude embedded browser — accessible snapshot"))

	def _copyEmbeddedBrowserAddress(self, address):
		if not address:
			ui.message(_("The embedded browser did not expose its current address"))
			return
		if not wx.TheClipboard.Open():
			ui.message(_("Could not open the clipboard"))
			return
		try:
			wx.TheClipboard.SetData(wx.TextDataObject(address))
			wx.TheClipboard.Flush()
		finally:
			wx.TheClipboard.Close()
		ui.message(_("Browser page address copied"))

	def _openEmbeddedBrowserExternallyFromResult(self, result):
		address = result.get("address", "")
		try:
			if address and wx.LaunchDefaultBrowser(address):
				ui.message(_("Opened the page in the default browser"))
				return
			externalItem = next((item for item in result["items"] if item.get("kind") == "external"), None)
			if externalItem is not None:
				externalItem["object"].doAction()
				ui.message(_("Requested the native Open in browser action"))
				return
		except Exception:
			log.debugWarning("Claude Desktop Access could not open the embedded page externally", exc_info=True)
		ui.message(_("The embedded browser did not expose a safe page address or external-browser control"))

	def _findClaudePromptObject(self):
		candidates = [self._lastPromptObject, self._pendingPromptObject]
		try:
			candidates.append(api.getFocusObject())
		except Exception:
			pass
		for candidate in tuple(candidates):
			current = candidate
			for _ in range(8):
				if current is None:
					break
				try:
					if _isDefunctObject(current):
						break
					if _isCodePromptObject(current):
						return current
					current = getattr(current, "parent", None)
				except Exception:
					break
		if self._buffer is not None:
			try:
				position = self._buffer.makeTextInfo(textInfos.POSITION_LAST)
				current = getattr(position, "NVDAObjectAtStart", None)
				for _ in range(10):
					if current is None:
						break
					if _isDefunctObject(current):
						break
					if _isCodePromptObject(current):
						return current
					current = getattr(current, "parent", None)
			except Exception:
				pass
		return None

	def _returnToClaudePrompt(self):
		try:
			prompt = self._findClaudePromptObject()
			if prompt is None:
				raise LookupError("prompt not found")
			prompt.setFocus()
			api.setNavigatorObject(prompt)
			self._lastPromptObject = prompt
			ui.message(_("Returned to the Claude prompt"))
		except Exception:
			log.debugWarning("Claude Desktop Access could not return to the Claude prompt", exc_info=True)
			ui.message(_("The Claude prompt could not be focused in this view"))

	def _openEmbeddedBrowserNavigator(self):
		if self._browserNavigatorDialog:
			self._browserNavigatorDialog.Raise()
			self._browserNavigatorDialog.search.SetFocus()
			return
		self._startEmbeddedBrowserScan("navigator")

	def _announceEmbeddedBrowserPageSummary(self):
		self._startEmbeddedBrowserScan("summary")

	def _requestEmbeddedBrowserSnapshot(self):
		self._startEmbeddedBrowserScan("snapshot")

	def _requestOpenEmbeddedBrowserExternally(self):
		self._startEmbeddedBrowserScan("external")

	def _embeddedBrowserNotice(self, message):
		now = time.monotonic()
		if shouldSuppressSemanticDuplicate(
			message, self._lastEmbeddedBrowserNotice,
			now - self._lastEmbeddedBrowserNoticeAt,
		):
			return
		self._lastEmbeddedBrowserNotice = message
		self._lastEmbeddedBrowserNoticeAt = now
		conf = _settings()
		_send(message, conf["speech"], conf["braille"], None, False, brailleMessage=message)

	def _updateEmbeddedBrowserFocus(self, obj):
		inBrowser = _isEmbeddedBrowserObject(obj)
		if inBrowser == self._embeddedBrowserFocused:
			return
		wasInBrowser = self._embeddedBrowserFocused
		self._embeddedBrowserFocused = inBrowser
		if wasInBrowser and not inBrowser:
			self._resetEmbeddedBrowserProgress()

	def _announceEmbeddedBrowserProgress(self, obj):
		if not _settings()["announceEmbeddedBrowserProgress"]:
			return
		if getattr(obj, "role", None) != Role.PROGRESSBAR or not _isEmbeddedBrowserObject(obj):
			return
		parsed = embeddedBrowserProgress(
			getattr(obj, "name", ""), getattr(obj, "value", ""), getattr(obj, "description", ""),
		)
		if parsed is None:
			return
		identity, percent, _bucket = parsed
		self._embeddedBrowserLoadingPercent = percent
		progressIdentity = "progress:{identity}".format(identity=identity)
		if percent is not None and percent >= 100:
			if not self._embeddedBrowserLoading:
				self._embeddedBrowserLoadIdentity = progressIdentity
				self._embeddedBrowserLoading = True
			self._completeEmbeddedBrowserLoading()
		else:
			self._startEmbeddedBrowserLoading(progressIdentity, force=True)

	def _performChatHistoryAction(self, title, action, source="recent", mode=None):
		mode = mode or self._conversationMode
		agentName = modeDisplayName(mode)
		if mode not in ("claude", "code", "cowork") or mode != self._conversationMode:
			ui.message(_("The chat-history mode changed. Open chat history again"))
			return

		try:
			if action in ("focusActions", "pin", "archive"):
				self._startDirectChatAction(title, action)
				return
			button = self._chatButtonObject(title)
			if button is None:
				raise LookupError("selected chat button not found")
			self._pendingOpenedChatTitle = title
			self._pendingOpenedChatAt = time.monotonic()
			button.doAction()
			log.info("Claude Desktop Access performed chat history action: %s", action)
		except Exception:
			log.debugWarning("Claude Desktop Access could not act on the selected chat", exc_info=True)
			ui.message(_("The selected {agent} chat could not be opened").format(agent=agentName))

	def _queueChatHistoryAction(self, title, action, source, mode):
		self._pendingChatHistoryAction = (title, action, source, mode)

	def _chatHistoryClosed(self):
		self._chatHistoryDialog = None
		self._chatHistoryDialogMode = ""
		gui.mainFrame.postPopup()
		pending, self._pendingChatHistoryAction = self._pendingChatHistoryAction, None
		if pending:
			self._chatHistoryActionTimer = wx.CallLater(
				100, self._runChatHistoryAction, *pending,
			)

	def _runChatHistoryAction(self, title, action, source, mode):
		self._chatHistoryActionTimer = None
		self._performChatHistoryAction(title, action, source, mode)

	def _rememberBuffer(self, obj):
		if not _isClaudeObject(obj):
			return
		explicitMode = conversationModeFromSwitchLabel(getattr(obj, "name", ""))
		mode = _conversationModeForObject(obj)
		isPrompt = _isCodePromptObject(obj)
		isEmbeddedBrowser = False if isPrompt else _isEmbeddedBrowserObject(obj)
		for current in self._bufferCandidates(obj):
			candidateMode = _conversationModeForObject(current)
			if not (mode or candidateMode or isPrompt):
				continue
			buffer = getattr(current, "treeInterceptor", None)
			if not buffer:
				continue
			# The embedded browser has its own Chromium tree interceptor. Only run the
			# ancestry check once, skip its nested document, and continue until the
			# outer Claude/Code conversation document is found.
			if isEmbeddedBrowser and not candidateMode:
				continue
			resolvedMode = mode or candidateMode
			candidateWindowHandle = self._conversationWindowHandleFrom(obj, buffer)
			if not self._conversationWindowIsAvailable(candidateWindowHandle):
				now = time.monotonic()
				if now - self._lastRejectedBufferLogAt >= 30.0:
					self._lastRejectedBufferLogAt = now
					log.debug("Claude Desktop Access ignored a buffer from a closed or hidden window")
				continue
			self._lastRejectedBufferLogAt = 0.0
			if isCodeDocument(getattr(buffer, "rootNVDAObject", None)):
				explicitMode = "code"
			if explicitMode:
				self._setConversationMode(explicitMode, "mode switch control event", authoritative=True)
			differentWindow = bool(
				self._conversationWindowHandle and candidateWindowHandle
				and candidateWindowHandle != self._conversationWindowHandle
			)
			if differentWindow and not explicitMode:
				# A different top-level application window needs a fresh authoritative
				# mode observation. Within one Claude window, its document remains named
				# Claude in both modes and therefore cannot override the switch control.
				self._conversationModeObserved = False
				self._conversationModeObservedAt = 0.0
			if resolvedMode and not self._conversationModeObserved:
				self._setConversationMode(resolvedMode, "conversation document", authoritative=True)
			wasMissing = self._buffer is None
			bufferChanged = self._buffer is not None and buffer is not self._buffer
			if bufferChanged:
				title = pendingChatTitle(
					self._pendingOpenedChatTitle,
					time.monotonic() - self._pendingOpenedChatAt if self._pendingOpenedChatAt else float("inf"),
				)
				self._pendingOpenedChatTitle = ""
				self._pendingOpenedChatAt = 0.0
				bufferSampleComplete = False
				try:
					# The end of the document contains the prompt and newest turns. Reading
					# only a bounded tail is sufficient to distinguish a blank chat and avoids
					# copying an entire large transcript on NVDA's main thread merely because
					# Chromium rebuilt its virtual-buffer object.
					position = buffer.makeTextInfo(textInfos.POSITION_LAST)
					moved = position.move(
						textInfos.UNIT_CHARACTER, -BUFFER_TAIL_SCAN_CHARACTERS, endPoint="start",
					)
					bufferText = position.text
					# Absence of message markers proves the chat is blank only when this
					# bounded range reached the document start. A truncated long response
					# may legitimately have its speaker heading outside the sampled tail.
					bufferSampleComplete = abs(moved) < BUFFER_TAIL_SCAN_CHARACTERS
				except Exception:
					bufferText = ""
				conversationChanged = bool(
					title or (bufferSampleComplete and looksLikeBlankCodeConversation(bufferText))
				)
				if conversationChanged:
					self._documentSwitchCount += 1
					self._resetTaskState("document changed")
					message = _("Chat opened: {title}").format(title=title) if title else _("New chat opened")
					self._latestMessage = self._latestFullMessage = message
					self._speakOnce(message, "other", "other", brailleMessage=message)
					log.info("Claude Desktop Access detected a newly opened chat document")
				else:
					log.debug("Claude Desktop Access refreshed the Chromium virtual buffer without resetting task state")
			self._buffer = buffer
			document = codeDocumentUrl(getattr(buffer, "rootNVDAObject", None)) if resolvedMode == "code" else ""
			if wasMissing or bufferChanged or document != self._nativeTaskDocument:
				if document != self._nativeTaskDocument:
					self._nativeTaskStartedAt = None
				self._nativeTaskDocument = document
				self._nativeTaskState = None
				self._nativeFallbackClock = None
				self._updateNativeTaskTimer(None)
				self._nativeTaskObserver.attach(buffer if document else None)
			if wasMissing or bufferChanged:
				self._conversationWindowHandle = candidateWindowHandle
				self._conversationWindowUnavailableAt = 0.0
				self._bufferDirty = True
				self._lastBufferInspectionAt = 0.0
				self._lastScannedLabel = ""
				self._queueConversationModeProbe("mode switch UI Automation probe")
			if wasMissing:
				log.info("Claude Desktop Access attached to %s", type(buffer).__name__)
			if not self._monitoringAnnounced:
				self._monitoringAnnounced = True
				conf = _settings()
				_send(_("Activity monitoring active"), conf["speech"], conf["braille"], None, False)
			return

	def _updateAppFocusState(self, obj):
		appFocused = _isClaudeObject(obj)
		self._appFocusState, cue = focusStateTransition(self._appFocusState, appFocused)
		if cue and self._nativeTaskSeconds is None:
			self._nativeTaskState = None
			self._nativeFallbackClock = None
		if cue == "inactive":
			self._promptFocused = False
			self._brailleCompositionActive = False
			self._promptTypingUntil = 0.0
			self._conversationNavigationUntil = 0.0
			if self._promptInspectionTimer:
				self._promptInspectionTimer.Stop()
				self._promptInspectionTimer = None
			self._pendingPromptObject = None
		conf = _settings()
		if not cue or self._paused or not conf["monitoringFocusClicks"] or not conf["soundWhenSpeechUnavailable"]:
			return cue
		category = "monitoringActive" if cue == "active" else "monitoringInactive"
		_playProgressSound(category, cue, conf["progressSoundStyle"], conf["clickVolume"])
		return cue

	def _observeInputGesture(self, gesture):
		"""Observe prompt input and defer large scans during conversation navigation."""
		try:
			if not self._appFocusState:
				return True
			identifiers = getattr(gesture, "identifiers", ()) or ()
			if isinstance(identifiers, str):
				identifiers = (identifiers,)
			if not identifiers:
				identifier = getattr(gesture, "identifier", "")
				identifiers = (identifier,) if identifier else ()
			if not self._promptFocused:
				# Whole-buffer reads are the most expensive operation in a large
				# conversation. Any user gesture outside the prompt means navigation is
				# active, so leave the browse cursor and Braille viewport undisturbed until
				# the user pauses. The gesture always continues through NVDA unchanged.
				if identifiers:
					self._conversationNavigationUntil = max(
						self._conversationNavigationUntil,
						time.monotonic() + CONVERSATION_NAVIGATION_QUIET_SECONDS,
					)
				return True
			promptInFocusMode = bool(getattr(self._buffer, "passThrough", True))
			if any(isPromptSubmissionGestureIdentifier(identifier) for identifier in identifiers):
				promptTypingActive = time.monotonic() < self._promptTypingUntil
				if not promptSubmissionGestureShouldStart(
					promptInFocusMode, self._promptHadText, promptTypingActive,
				):
					# In browse mode, dot-8 activates the empty editor. It does not
					# submit anything and must not start clicks or elapsed messages.
					self._brailleCompositionActive = False
					self._promptTypingUntil = 0.0
					return True
				# Claude replaces its content-editable prompt as Enter is processed.
				# That can leave NVDA's normal text/caret script holding a stale IA2
				# object, so observe Enter before the replacement and queue only our
				# state transition. The gesture itself continues through NVDA unchanged.
				self._brailleCompositionActive = False
				self._promptTypingUntil = 0.0
				if not self._promptSubmissionGestureQueued:
					self._promptSubmissionGestureQueued = True
					try:
						queueHandler.queueFunction(
							queueHandler.eventQueue, self._beginPromptSubmissionFromGesture,
						)
					except Exception:
						# A transient queue failure must not disable all later Enter
						# observations for the lifetime of this NVDA session.
						self._promptSubmissionGestureQueued = False
						raise
				return True
			brailleIdentifiers = tuple(
				identifier for identifier in identifiers
				if isBrailleTypingGestureIdentifier(identifier)
			)
			if brailleIdentifiers:
				if not promptInFocusMode:
					# Braille dot chords are browse-mode navigation until the prompt
					# has actually entered focus mode; do not treat them as draft text.
					self._brailleCompositionActive = False
					self._promptTypingUntil = 0.0
					return True
				commitsText = any(
					brailleTypingGestureCommitsText(identifier) for identifier in brailleIdentifiers
				)
				self._brailleCompositionActive = not commitsText
				if commitsText:
					# Contracted Braille sends the completed word just after this
					# observer runs. Claude can report its resulting caret move only
					# after the first cell of the next word has already been entered.
					self._lastBrailleTextInjectionAt = time.monotonic()
				self._promptTypingUntil = max(
					self._promptTypingUntil,
					time.monotonic() + PROMPT_TYPING_QUIET_SECONDS,
				)
		except Exception:
			# This observer must never interfere with another add-on or NVDA gesture.
			pass
		return True

	def _beginPromptSubmissionFromGesture(self):
		"""Start feedback for an observed Enter after returning to NVDA's main queue."""
		global _activePluginInstance
		self._promptSubmissionGestureQueued = False
		if _activePluginInstance is not self or self._busy:
			return
		self._promptHadText = False
		self._beginPromptSubmission("unmodified Enter gesture")
		self._schedulePoll(50, requestInspection=True)

	def event_caret(self, obj, nextHandler):
		"""Preserve a new contracted word across Claude's delayed prior-word caret event."""
		try:
			if self._appFocusState and _isCodePromptObject(obj):
				try:
					from braille import input as brailleInputModule
				except ImportError:
					# Compatibility fallback for NVDA versions predating braille.input.
					import brailleInput as brailleInputModule
				handler = getattr(brailleInputModule, "handler", None)
				elapsed = (
					time.monotonic() - self._lastBrailleTextInjectionAt
					if self._lastBrailleTextInjectionAt else float("inf")
				)
				if handler is not None and shouldPreserveBrailleComposition(
					self._promptFocused,
					self._brailleCompositionActive,
					bool(getattr(handler, "bufferBraille", ())),
					elapsed,
					BRAILLE_CARET_GRACE_SECONDS,
				):
					# NVDA already ignores caret events generated by uncontracted
					# Braille for 0.3 seconds. Mark this one the same way instead of
					# replacing or bypassing the Braille input handler.
					handler._uncontSentTime = time.time()
					self._brailleCaretMoveSuppressions += 1
		except Exception:
			# Caret handling must always continue even if NVDA changes its
			# internal Braille input implementation in a future release.
			log.debugWarning("Claude Desktop Access Braille caret protection failed", exc_info=True)
		finally:
			nextHandler()

	def _trackPromptSubmission(self, obj, allowTextInfo=True):
		try:
			isEditable = obj.role == Role.EDITABLETEXT
		except Exception:
			return False
		if not isEditable or not _isCodePromptObject(obj):
			return False
		valueRead = False
		text = ""
		try:
			value = obj.value
			if value is not None:
				valueRead = True
				text = str(value)
		except Exception:
			pass
		# Chromium content-editable controls do not always expose a useful value.
		# Trust a non-empty value, and trust an empty value only after this prompt
		# was known to contain text. This avoids a redundant IA2 TextInfo read at
		# the exact moment Enter replaces the editor object.
		if not (valueRead and (text.strip() or self._promptHadText is True)):
			if not allowTextInfo:
				return False
			try:
				text = str(obj.makeTextInfo(textInfos.POSITION_ALL).text or "")
				valueRead = True
			except Exception:
				pass
		if not valueRead:
			return False
		self._promptHadText, submitted = promptSubmissionTransition(self._promptHadText, bool(text.strip()))
		if not submitted:
			return False
		self._beginPromptSubmission("prompt became empty")
		return True

	def _schedulePromptInspection(self, obj):
		"""Debounce prompt-local TextInfo reads until Braille or keyboard typing pauses."""
		self._pendingPromptObject = obj
		if self._promptInspectionTimer:
			self._promptInspectionTimer.Stop()
		self._promptInspectionTimer = wx.CallLater(
			PROMPT_INSPECTION_DELAY_MS, self._inspectPendingPrompt,
		)

	def _inspectPendingPrompt(self):
		self._promptInspectionTimer = None
		obj = self._pendingPromptObject
		self._pendingPromptObject = None
		try:
			if obj is None or not _isCodePromptObject(obj):
				return
			if self._trackPromptSubmission(obj, allowTextInfo=True):
				self._promptTypingUntil = 0.0
				self._schedulePoll(50, requestInspection=True)
		except Exception:
			log.debugWarning("Claude Desktop Access deferred prompt inspection failed", exc_info=True)

	def _notePromptTyping(self, obj):
		if not _isCodePromptObject(obj):
			return False
		self._lastPromptObject = obj
		self._promptTypingUntil = time.monotonic() + PROMPT_TYPING_QUIET_SECONDS
		return True

	def _beginPromptSubmission(self, reason):
		self._promptTypingUntil = 0.0
		self._brailleCompositionActive = False
		self._lastBrailleTextInjectionAt = 0.0
		if self._usageLimitActive:
			# A new explicit submission is a new attempt. It may succeed after the
			# reset time or expose a fresh limit notice that should be announced.
			self._usageLimitActive = False
			self._lastUsageLimitNotice = ""
			self._lastLabel = ""
			self._lastScannedLabel = ""
		if self._promptInspectionTimer:
			self._promptInspectionTimer.Stop()
			self._promptInspectionTimer = None
		self._pendingPromptObject = None
		if self._pluginProgressOwnedBusy:
			# A real task supersedes installation-owned background state. Otherwise a
			# later installation completion could incorrectly end the new task.
			self._pluginProgressOwnedBusy.clear()
			self._setBusy(False, "prompt superseded plugin installation")
		if self._busy:
			return
		self._latestMessage = ""
		self._latestFullMessage = ""
		self._lastMessage = ""
		self._lastMessageAt = 0.0
		self._pendingResponseCompletionAt = 0.0
		self._lastSubmissionSignal = reason
		self._active = True
		self._activeCategory = "working"
		self._setBusy(True, reason)
		conf = _settings()
		if conf["promptSubmissionClick"] and not self._paused:
			mode = conf[CATEGORY_OUTPUT_CONFIG["working"]]
			actions = categoryOutputActions(mode, conf["speech"], conf["braille"], conf["soundWhenSpeechUnavailable"])
			if actions["sound"]:
				_playProgressSound(
					"submission", _("Prompt submitted"), conf["progressSoundStyle"], conf["clickVolume"],
				)
		log.info("Claude Desktop Access submission detected: %s", reason)

	def _queueResponseCompletion(self):
		if self._busy and not self._pendingResponseCompletionAt:
			self._pendingResponseCompletionAt = time.monotonic()
			log.debug("Claude Desktop Access queued response completion candidate")

	def _latestButtonStatus(self, info):
		latest = ""
		latestUserMessageNumber = None
		stopControlVisible = False
		responseCompleteMarkerCount = 0
		latestDetailedResponseMarker = None
		buttonDepth = 0
		buttonText = []
		buttonName = ""
		buttonRole = None
		buttonInHistory = False
		unknown = []
		usageEvidence = []
		usageActionControls = set()
		usageBannerSeen = False
		inRecents = False
		recentsSeen = False
		recentTitles = []
		recentItemCount = 0
		inArchived = False
		archivedSeen = False
		archivedTitles = []
		showMoreButtonOrdinal = 0
		recentShowMoreButtonOrdinal = 0
		observedMode = ""
		for item in info.getTextWithFields():
			if isinstance(item, str):
				plainText = " ".join(item.split())
				usagePlainText = re.sub(r"(?<=[a-z0-9%])(?=[A-Z])", " ", plainText)
				if inRecents and re.search(
					r"\b(?:\d{1,3}(?:\.\d+)?\s*%\s*usage\s+(?:remaining|consumed)|no usage remaining)\b",
					usagePlainText,
					flags=re.IGNORECASE,
				):
					usageEvidence.append(usagePlainText[:256])
					usageBannerSeen = True
				elif usageBannerSeen and any(marker in usagePlainText.casefold() for marker in (
					"next reset", "resets every", "add credits", "buy credits", "purchase credits", "upgrade",
				)):
					usageEvidence.append(usagePlainText[:256])
				if not recentsSeen and plainText.casefold() in ("recents", "recent chats", "chats"):
					inRecents = recentsSeen = True
				if not archivedSeen and plainText.casefold() == "archived chats":
					inArchived = archivedSeen = True
				if not buttonDepth and inRecents and plainText.casefold() in ("pinned", "projects", "agents"):
					inRecents = False
				if isChatHistoryConversationBoundary(plainText):
					inRecents = inArchived = False
				if isResponseCompletionMarkerText(plainText):
					responseCompleteMarkerCount += 1
					if plainText.casefold().startswith("response complete:"):
						# Python's per-process hash avoids retaining or logging response text.
						latestDetailedResponseMarker = hash(plainText)
				if buttonDepth:
					buttonText.append(item)
				continue
			command = getattr(item, "command", "")
			field = getattr(item, "field", {}) or {}
			if command == "controlStart":
				role = field.get("role")
				fieldName = " ".join(str(field.get("name", "") or "").split())
				fieldMode = modeFromTab(fieldName, role == Role.TAB, State.SELECTED in field.get("states", set()))
				if fieldMode:
					observedMode = fieldMode
				landmarkName = " ".join(str(field.get("landmark", "") or "").casefold().split())
				isMainLandmark = landmarkName == "main" or (
					role == Role.LANDMARK and fieldName.casefold() in ("main", "main content")
				)
				isFollowingSectionHeading = inRecents and role == getattr(Role, "HEADING", None) and (
					fieldName.casefold() not in ("", "recents", "recent chats", "chats")
				)
				if inRecents and isMainLandmark:
					inRecents = False
				if isFollowingSectionHeading:
					inRecents = False
				if inArchived and isMainLandmark:
					inArchived = False
				if buttonDepth:
					buttonDepth += 1
				elif role in (Role.BUTTON, Role.LINK):
					buttonDepth, buttonText, buttonName = 1, [], field.get("name", "")
					buttonRole = role
					buttonInHistory = inRecents or inArchived
			elif command == "controlEnd" and buttonDepth:
				buttonDepth -= 1
				if buttonDepth == 0:
					textLabel = " ".join("".join(buttonText).split())
					historyLabel = textLabel or " ".join(str(buttonName or "").split())
					accountLabel = historyLabel.casefold()
					if usageBannerSeen and (
						accountLabel in ("upgrade", "upgrade plan", "upgrade to pro")
						or re.fullmatch(
							r"(?:add|buy|purchase)(?:\s+some)?(?:\s+more)?\s+credits?", accountLabel,
						)
					):
						usageEvidence.append(historyLabel[:256])
						usageActionControls.add(accountLabel)
					if historyLabel.casefold() == "show more":
						showMoreButtonOrdinal += 1
						if inRecents and not recentShowMoreButtonOrdinal:
							recentShowMoreButtonOrdinal = showMoreButtonOrdinal
					if any(isChatHistoryConversationBoundary(candidate) for candidate in (textLabel, buttonName)):
						inRecents = inArchived = False
					isRecentTitle = inRecents and historyLabel and historyLabel.casefold() not in (
						"recents", "open profile menu", "new chat", "view activity",
					) and not isChatHistoryInterfaceText(historyLabel)
					if isRecentTitle:
						recentItemCount += 1
						if historyLabel not in recentTitles:
							recentTitles.append(historyLabel)
					archivedKey = historyLabel.casefold()
					if inArchived and historyLabel and archivedKey not in (
						"archived chats", "close", "cancel", "done", "delete", "unarchive",
					) and not archivedKey.startswith(("delete ", "unarchive ")) and not isChatHistoryInterfaceText(
						historyLabel
					) and historyLabel not in archivedTitles:
						archivedTitles.append(historyLabel)
					# Links are collected for history only. A sidebar title or response
					# citation that starts with "Reading" or "Running" is not activity.
					if buttonRole != Role.BUTTON or buttonInHistory:
						continue
					for candidate in (textLabel, buttonName):
						if isStopControlLabel(candidate):
							stopControlVisible = True
						number = userMessageNumber(candidate)
						if number is not None:
							latestUserMessageNumber = max(latestUserMessageNumber or number, number)
					label = firstStatusLabel(textLabel, buttonName)
					if label:
						latest = label
					elif textLabel or buttonName:
						candidate = textLabel or buttonName
						if not isKnownNonStatusButton(candidate) and not isStopControlLabel(candidate):
							unknown.append(candidate)
		if observedMode:
			self._setConversationMode(observedMode, "mode switch control scan", authoritative=True)
		scanMode = observedMode or self._conversationMode
		recentSnapshot = tuple(recentTitles) if recentsSeen else None
		archivedSnapshot = tuple(archivedTitles) if archivedSeen else None
		if scanMode in ("claude", "code", "cowork") and recentSnapshot is not None:
			self._chatHistoryMoreAvailable[scanMode] = bool(recentShowMoreButtonOrdinal)
			self._recentHistoryShowMoreOrdinals[scanMode] = recentShowMoreButtonOrdinal
			self._unifiedRecentCounts[scanMode] = recentItemCount
			self._chatHistoryScanGenerations[scanMode] += 1
		if scanMode not in ("claude", "code", "cowork") or recentSnapshot is None:
			self._cacheChatHistoryScan(
				scanMode, recentSnapshot, archivedSnapshot,
			)
		else:
			now = time.monotonic()
			modeChangedAt = self._conversationModeChangedAt
			modeAge = now - modeChangedAt if modeChangedAt else float("inf")
			pendingSnapshot = self._pendingChatHistorySnapshots[scanMode]
			pendingAt = self._pendingChatHistorySnapshotAt[scanMode]
			pendingAge = now - pendingAt if pendingSnapshot is not None and pendingAt else 0.0
			otherMode = "code" if scanMode == "claude" else "claude"
			decision = chatHistorySnapshotDecision(
				modeAge, CHAT_HISTORY_MODE_SETTLE_SECONDS,
				recentSnapshot, self._chatHistoryCaches[otherMode],
				False,  # Claude may expose the same recent chats in more than one mode.
				pendingSnapshot, pendingAge, CHAT_HISTORY_SNAPSHOT_CONFIRM_SECONDS,
				currentTitles=self._chatHistoryCaches[scanMode],
				current=self._chatHistoryCacheCurrent[scanMode],
			)
			if decision == "publish":
				self._pendingChatHistorySnapshots[scanMode] = None
				self._pendingChatHistorySnapshotAt[scanMode] = 0.0
				self._lastDeferredHistoryLog = ()
				self._lastDeferredHistoryLogAt = 0.0
				self._cacheChatHistoryScan(
					scanMode,
					self._modeSpecificRecentChatTitles(scanMode, recentSnapshot),
					archivedSnapshot,
				)
			else:
				if decision == "confirm" and pendingSnapshot != recentSnapshot:
					self._pendingChatHistorySnapshots[scanMode] = recentSnapshot
					self._pendingChatHistorySnapshotAt[scanMode] = now
				elif decision == "otherMode":
					self._pendingChatHistorySnapshots[scanMode] = None
					self._pendingChatHistorySnapshotAt[scanMode] = 0.0
				delay = CHAT_HISTORY_RETRY_MILLISECONDS
				if decision == "settle":
					delay = max(150, int(
						(CHAT_HISTORY_MODE_SETTLE_SECONDS - modeAge) * 1000
					) + 1)
				self._schedulePoll(delay=delay, requestInspection=True)
				logSnapshot = (scanMode, decision)
				if shouldLogDiagnosticSnapshot(
					logSnapshot, self._lastDeferredHistoryLog,
					now - self._lastDeferredHistoryLogAt,
				):
					log.debug(
						"Claude Desktop Access deferred %s history caching: %s",
						scanMode, decision,
					)
					self._lastDeferredHistoryLog = logSnapshot
					self._lastDeferredHistoryLogAt = now
		if _settings()["diagnosticLogging"] and unknown:
			now = time.monotonic()
			# Arbitrary button labels can contain private task titles. Keep only
			# ephemeral hashes for change detection and log non-content metadata.
			snapshot = tuple((len(x), hash(x)) for x in unknown[-5:])
			if shouldLogDiagnosticSnapshot(snapshot, self._lastUnknownButtons, now - self._lastUnknownButtonsAt):
				log.debug(
					"Claude Desktop Access unrecognized buttons: count=%d, lengths=%s",
					len(unknown), [len(x) for x in unknown[-5:]],
				)
				self._lastUnknownButtons = snapshot
				self._lastUnknownButtonsAt = now
		usageNotice = usageLimitNotice(" ".join(usageEvidence), _) if usageActionControls else ""
		if usageNotice:
			# Some Chromium builds expose the account banner in the virtual buffer
			# without firing an alert event. End the task here before stale Stop or
			# progress controls later in this same scan can restart Working feedback.
			self._applyUsageLimitNotice(usageNotice)
			return ""
		self._latestUserMessageNumber, submitted = userMessageSubmissionTransition(
			self._latestUserMessageNumber, latestUserMessageNumber,
		)
		self._pendingUserMessageIncrease, confirmedSubmission = confirmedUserMessageSubmission(
			self._pendingUserMessageIncrease, submitted, stopControlVisible,
		)
		if confirmedSubmission:
			self._beginPromptSubmission("new user message detected")
		if stopControlVisible and not self._busy:
			self._promptHadText = False
			self._beginPromptSubmission("Send button activated")
		self._stopControlVisible, stopped = stopControlTransition(self._stopControlVisible, stopControlVisible)
		if stopControlVisible:
			# A new generating phase invalidates any earlier quiet-window timer.
			self._pendingResponseCompletionAt = 0.0
		if stopped and self._busy:
			# Completed tool controls can remain visible after generation stops.
			# The finalization guard checks whether the remaining label is quiet.
			self._queueResponseCompletion()
		latestResponseMarker = responseCompletionScanMarker(
			responseCompleteMarkerCount, latestDetailedResponseMarker,
		)
		self._latestResponseMarker, self._responseMarkerInitialized, responseCompleted = responseCompletionTransition(
			self._latestResponseMarker, self._responseMarkerInitialized, latestResponseMarker, self._busy,
		)
		if responseCompleted:
			self._queueResponseCompletion()
		return latest

	def _shouldAnnounce(self, label, category):
		conf = _settings()
		if not conf[CATEGORY_SETTING[category]] or conf[CATEGORY_OUTPUT_CONFIG.get(category, "outputOther")] == "off":
			return False
		seconds = elapsedSeconds(label)
		if category == "working" and seconds is not None:
			interval = conf["workingIntervalSeconds"]
			return seconds == 0 or seconds % interval == 0
		return True

	def _announceLabel(self, label):
		category, safeMessage = statusDetails(label)
		if not category:
			return
		if self._usageLimitActive:
			# Stale progress and completion labels can remain beneath the pop-over.
			# Do not resume output until the user explicitly submits again.
			return
		# Explicit Claude activity owns the busy state from this point onward.
		self._pluginProgressOwnedBusy.clear()
		# New work supersedes a tentative virtual-buffer completion. Intermediate
		# completion labels must preserve it so trailing Chromium events cannot
		# leave the continuous Working sound active indefinitely.
		if supersedesResponseCompletionCandidate(label):
			self._pendingResponseCompletionAt = 0.0
		stateCategory = category if category != "completion" or isTaskCompletionLabel(label) else ""
		self._setBusy(nextBusyState(self._busy, stateCategory), category)
		if category != "completion":
			self._activeCategory = category
		elif not isTaskCompletionLabel(label):
			self._activeCategory = intermediateCompletionCategory(label) or self._activeCategory
		if not self._shouldAnnounce(label, category):
			return
		conf = _settings()
		message = statusMessage(
			label, _, conf["verbosity"], conf["redactSensitive"], conf["fullSpeechProfile"],
			conf["minimalSpeechProfile"],
		)
		brailleMessage = brailleStatusMessage(label, _, conf["brailleDetail"], conf["redactSensitive"])
		self._latestFullMessage = brailleMessage
		if category == "command" and conf["verbosity"] == "full":
			message, shortened = formatCommandSpeech(
				message, conf["commandPunctuation"], conf["maximumSpokenCommandCharacters"],
			)
			if shortened:
				message += _(" Complete command available with Copy latest full Claude progress.")
		priority = announcementPriority(category, message)
		action = soundKey(category, message) if category == "completion" else category
		message = _customizeAnnouncement(message, action)
		log.info("Claude Desktop Access detected activity: %s", safeMessage)
		self._latestMessage = message
		fallbackPlayed = self._speakOnce(message, category, action, priority, brailleMessage)
		completionMode = conf[CATEGORY_OUTPUT_CONFIG["completion"]]
		if category == "completion" and conf["completionSound"] and completionMode in ("all", "sound") and not fallbackPlayed:
				_safeBeep(880, 80)

	def _applyScannedLabel(self, label, now):
		"""Apply one successful compatibility scan to the task state machine."""
		self._lastScannedLabel = label
		if label and label != self._lastLabel and supersedesResponseCompletionCandidate(label):
			self._pendingResponseCompletionAt = 0.0
		if not label:
			if not self._haveBaseline:
				self._haveBaseline, self._lastLabel = True, ""
				log.info("Claude Desktop Access baseline established: no activity")
			elif self._lastLabel:
				self._lastLabel = ""
				log.debug("Claude Desktop Access activity cleared")
			if now - self._lastNoStatusLogAt >= 30.0:
				self._lastNoStatusLogAt = now
				log.debug("Claude Desktop Access scanned buffer; no activity button found")
			return
		if not self._haveBaseline:
			self._lastLabel, self._haveBaseline = label, True
			baselineCategory = statusDetails(label)[0]
			stateCategory = baselineCategory if baselineCategory != "completion" or isTaskCompletionLabel(label) else ""
			self._setBusy(nextBusyState(self._busy, stateCategory), "baseline")
			return
		if label != self._lastLabel:
			self._lastLabel = label
			self._announceLabel(label)

	def _poll(self):
		pollTimer = self._timer
		try:
			self._nextPollAt = 0.0
			now = time.monotonic()
			self._lastPollAt = now
			conversationDetached = False
			if self._buffer is not None:
				conversationDetached = self._detachConversationIfWindowClosed(now)
			if self._buffer is None and not conversationDetached:
				self._rememberBuffer(api.getFocusObject())
			if self._busy and self._busyWatchdogAt and now - self._busyWatchdogAt >= _settings()["maximumBusyMinutes"] * 60:
				self._setBusy(False, "maximum activity timeout")
			if self._buffer:
				if not self._conversationModeObserved and (
					not self._lastConversationModeProbeAt
					or now - self._lastConversationModeProbeAt >= MODE_CONTROL_RETRY_SECONDS
				):
					self._queueConversationModeProbe("mode switch UI Automation retry")
				elapsed = now - self._lastBufferInspectionAt if self._lastBufferInspectionAt else float("inf")
				promptTyping = bool(
					self._brailleCompositionActive
					or (self._appFocusState and now < self._promptTypingUntil)
					or (self._appFocusState and now < self._conversationNavigationUntil)
				)
				if bufferInspectionDue(
					self._bufferDirty, elapsed, self._active or self._busy,
					self._appFocusState, promptTyping,
				):
					# Clear the dirty flag before inspection. A concurrent relevant event
					# can set it again, while a failed provider call backs off to fallback
					# cadence instead of hammering the same stale IA2 object.
					self._bufferDirty = False
					self._lastBufferInspectionAt = now
					try:
						label = self._latestButtonStatus(
							self._buffer.makeTextInfo(textInfos.POSITION_ALL),
						)
					except Exception:
						self._lastInspectionError = "virtual buffer inspection failed"
						log.debugWarning(
							"Claude Desktop Access could not inspect the virtual buffer; preserving task state",
							exc_info=True,
						)
					else:
						self._bufferInspectionCount += 1
						self._lastInspectionError = "none"
						self._applyScannedLabel(label, now)
				else:
					self._skippedBufferInspectionCount += 1
			label = self._lastScannedLabel
			if shouldFinalizeResponseCompletion(
				self._pendingResponseCompletionAt,
				now - self._pendingResponseCompletionAt if self._pendingResponseCompletionAt else 0.0,
				RESPONSE_COMPLETION_SETTLE_SECONDS,
				self._busy, self._stopControlVisible, label,
			):
				self._pendingResponseCompletionAt = 0.0
				self._lastScannedLabel = ""
				self._haveBaseline, self._lastLabel = True, "Response complete"
				self._announceLabel("Response complete")
			self._announceNativeFallbackProgress(now)
			self._active = bool(self._lastScannedLabel) or self._busy or (
				self._appFocusState and self._nativeTaskState is True and self._nativeTaskSeconds is None
			)
		except Exception:
			log.debugWarning("Claude Desktop Access polling housekeeping failed", exc_info=True)
			self._lastInspectionError = "polling housekeeping failed"
		finally:
			if self._timer is not None:
				if self._timer is pollTimer:
					delay = pollDelay(self._active, _settings()["idlePollMs"])
					self._timer = wx.CallLater(delay, self._poll)
					self._nextPollAt = time.monotonic() + delay / 1000.0

	def _speakOnce(
		self, message, category="other", soundCategory=None, priority=None,
		brailleMessage=None, protectBrailleReading=True,
	):
		if self._paused:
			return False
		now = time.monotonic()
		brailleOutput = brailleMessage if brailleMessage is not None else message
		comparisonMessage = brailleOutput or message or category
		soundDuplicate = shouldSuppressSemanticDuplicate(comparisonMessage, self._lastMessage, now - self._lastMessageAt)
		channelDuplicates = duplicateChannelActions(
			message, brailleOutput, self._lastSpeechMessage, self._lastBrailleMessage,
			now - self._lastSpeechMessageAt, now - self._lastBrailleMessageAt,
		)
		speechDuplicate = channelDuplicates["speech"]
		brailleDuplicate = channelDuplicates["braille"]
		self._lastMessage, self._lastMessageAt = comparisonMessage, now
		conf = _settings()
		mode = conf[CATEGORY_OUTPUT_CONFIG.get(category, "outputOther")]
		actions = categoryOutputActions(mode, conf["speech"], conf["braille"], conf["soundWhenSpeechUnavailable"])
		effectivePriority = priority or announcementPriority(category, message)
		if protectBrailleReading and shouldSuppressRoutineBraille(
			conf["protectBrailleReading"], self._appFocusState, category, effectivePriority,
			self._conversationBrowseModeActive(),
		):
			actions["braille"] = False
		if category not in ("backgroundPulse1", "backgroundPulse2"):
			self._recordHistory(message, brailleOutput)
		if actions["speech"] and message and not speechDuplicate:
			self._lastSpeechMessage, self._lastSpeechMessageAt = message, now
		if actions["braille"] and brailleOutput and not brailleDuplicate:
			self._lastBrailleMessage, self._lastBrailleMessageAt = brailleOutput, now
		if conf["diagnosticLogging"] and speechDuplicate and brailleDuplicate and soundDuplicate:
			log.debug("Claude Desktop Access suppressed duplicate %s event on all enabled channels", category)
		return _send(
			message, actions["speech"] and bool(message) and not speechDuplicate,
			actions["braille"] and bool(brailleOutput) and not brailleDuplicate,
			soundCategory or category, actions["sound"] and not soundDuplicate,
			priority=effectivePriority, brailleMessage=brailleOutput,
		)

	def _setBusy(self, busy, reason):
		busy = bool(busy)
		if busy == self._busy:
			self._lastStateReason = reason
			return
		self._busy = busy
		self._lastStateReason = reason
		if busy:
			self._busyWatchdogAt = time.monotonic()
		log.info(
			"Claude Desktop Access background state: %s (%s)",
			"active" if busy else "idle", reason,
		)
		if not busy:
			self._busyWatchdogAt = 0.0

	def _announceStatus(self, obj):
		if getattr(obj, "role", None) != Role.BUTTON or not _isConversationObject(obj):
			return False
		label = getattr(obj, "name", "")
		if statusDetails(label)[0]:
			self._lastScannedLabel = label
			self._haveBaseline, self._lastLabel = True, label
			self._announceLabel(label)
			return True
		return False

	def _announceCommentary(self, obj):
		if not _isConversationObject(obj):
			return False
		if getattr(obj, "role", None) in (Role.BUTTON, Role.EDITABLETEXT):
			return False
		if self._usageLimitActive:
			return True
		text = " ".join(str(getattr(obj, "name", "") or getattr(obj, "value", "") or "").split())
		if not text:
			return False
		category = statusDetails(text)[0]
		if category:
			# Chromium can expose completion and progress as a non-button live region.
			# Route it through the normal state machine instead of discarding it as
			# status-like commentary. Avoid repeating response text in Full mode.
			label = "Response complete" if text.lower().startswith("response complete") else text
			if label == "Response complete":
				self._lastScannedLabel = ""
				self._queueResponseCompletion()
				return True
			if category == "completion" and self._haveBaseline and label == self._lastLabel:
				return True
			self._lastScannedLabel = label
			self._haveBaseline, self._lastLabel = True, label
			self._announceLabel(label)
			return True
		if not _settings()["announceCommentary"]:
			return True
		key = id(obj)
		if key not in self._commentaryOffsets and len(self._commentaryOffsets) >= 256:
			self._commentaryOffsets.pop(next(iter(self._commentaryOffsets)))
		previousText, offset = self._commentaryOffsets.get(key, ("", 0))
		if previousText and not text.startswith(previousText[:offset]):
			offset = 0
		message, newOffset = completedTextDelta(text, offset)
		self._commentaryOffsets[key] = (text, newOffset)
		if message:
			# Final-response commentary can arrive after the completion control.
			# It may refresh an active task, but must never restart one.
			self._pluginProgressOwnedBusy.clear()
			self._setBusy(nextBusyState(self._busy, commentary=True), "commentary")
			log.info("Claude Desktop Access detected activity: Commentary update")
			conf = _settings()
			fullMessage = redactSensitive(message) if conf["redactSensitive"] else message
			message = fullMessage
			if conf["verbosity"] == "minimal":
				profile = conf["minimalSpeechProfile"]
				if profile == "essential":
					message = ""
				else:
					wordLimit = 18 if profile == "balanced" else 30
					words = message.split()
					message = " ".join(words[:wordLimit]) + ("…" if len(words) > wordLimit else "")
			if message:
				message = _customizeAnnouncement(message, "commentary")
			self._latestMessage = message or fullMessage
			self._latestFullMessage = fullMessage
			self._speakOnce(message, "commentary", brailleMessage=fullMessage)
		return True

	def _readNativeTaskProgress(self, buffer, focus=None):
		root = getattr(buffer, "rootNVDAObject", None)
		if not isCodeDocument(root):
			return None, None
		if getattr(root, "UIAElement", None) is not None:
			return nativeCodeFeedTaskProgress(root, focus)
		info = buffer.makeTextInfo(textInfos.POSITION_ALL)
		return codeFeedTaskProgress(info.getTextWithFields())

	def _recordNativeTaskState(self, state, now):
		self._nativeTaskState = state
		if state is not True:
			self._nativeTaskStartedAt = None
		elif self._nativeTaskStartedAt is None:
			self._nativeTaskStartedAt = now

	def _estimatedNativeTaskSeconds(self, now):
		if self._nativeTaskState is not True or self._nativeTaskStartedAt is None:
			return None
		return max(0, int(now - self._nativeTaskStartedAt))

	def _observeNativeTaskState(self, buffer):
		if buffer is not self._buffer:
			return
		now = self._lastNativeTaskSampleAt = time.monotonic()
		if not self._conversationWindowIsAvailable(self._conversationWindowHandle):
			self._recordNativeTaskState(None, now)
			self._updateNativeTaskTimer(None)
			return
		document = codeDocumentUrl(buffer.rootNVDAObject)
		if document != self._nativeTaskDocument:
			self._nativeTaskDocument = document
			self._recordNativeTaskState(None, now)
			self._nativeFallbackClock = None
			self._updateNativeTaskTimer(None)
		if not document:
			self._nativeTaskObserver.detach()
			return
		focus = api.getFocusObject()
		try:
			state, seconds = self._readNativeTaskProgress(buffer, focus if _isClaudeObject(focus) else None)
		except Exception:
			self._recordNativeTaskState(None, now)
			self._updateNativeTaskTimer(None)
			raise
		self._recordNativeTaskState(state, now)
		if state is not True or seconds is not None:
			self._nativeFallbackClock = None
		elif self._appFocusState and self._nativeFallbackClock is None:
			self._nativeFallbackClock = now, None, now
			self._nativePulseCount = 0
		self._updateNativeTaskTimer(seconds)

	def _updateNativeTaskTimer(self, seconds):
		previous, self._nativeTaskSeconds = self._nativeTaskSeconds, seconds
		if seconds == previous:
			return
		if seconds is None or previous is None or seconds < previous:
			self._nativeLastClick = self._nativeLastPulse = seconds
			self._nativePulseCount = 0
			return
		conf = _settings()
		if self._paused or not conf["announceWorking"] or seconds >= conf["maximumBusyMinutes"] * 60:
			return
		mode = conf[CATEGORY_OUTPUT_CONFIG["working"]]
		actions = categoryOutputActions(mode, conf["speech"], conf["braille"], conf["soundWhenSpeechUnavailable"])
		if conf["announceHeartbeat"] and seconds - self._nativeLastPulse >= conf["workingIntervalSeconds"]:
			self._nativeLastPulse = seconds
			if self._emitNativeProgressPulse(seconds, conf, actions):
				self._nativeLastClick = seconds
		if (
			conf["continuousWorkingClicks"] and actions["sound"]
			and seconds * 1000 >= conf["workingClickStartDelayMs"]
			and (seconds - self._nativeLastClick) * 1000 >= conf["workingClickIntervalMs"]
		):
			self._nativeLastClick = seconds
			_playProgressSound("working", _("Working"), conf["progressSoundStyle"], conf["clickVolume"])

	def _emitNativeProgressPulse(self, seconds, conf, actions, estimated=False):
		self._nativePulseCount += 1
		category = "backgroundPulse1" if self._nativePulseCount % 2 else "backgroundPulse2"
		activity = _(backgroundActivityName(self._activeCategory, self._latestFullMessage))
		if seconds is None:
			fullMessage = _("Claude is still working")
		else:
			duration = formatElapsedDuration(seconds, _)
			if estimated:
				fullMessage = _("Claude is still working, about {duration} elapsed").format(duration=duration)
			else:
				fullMessage = _("{activity} still running, {duration}").format(activity=activity, duration=duration)
		message = _customizeAnnouncement(fullMessage, category, activity, seconds)
		speechAllowed = actions["speech"] and self._appFocusState
		brailleAllowed = actions["braille"] and self._appFocusState and not shouldSuppressRoutineBraille(
			conf["protectBrailleReading"], self._appFocusState, category, "low", self._conversationBrowseModeActive(),
		)
		if conf["verbosity"] == "minimal" and conf["minimalSpeechProfile"] == "essential":
			speechAllowed = False
		return _send(message, speechAllowed, brailleAllowed, category, actions["sound"], priority="low", brailleMessage=fullMessage)

	def _announceNativeFallbackProgress(self, now):
		# The fallback clock schedules sounds. The feed supplies the activity state.
		if (
			self._nativeTaskState is not True or self._nativeTaskSeconds is not None
			or not self._appFocusState or self._paused
			or not self._conversationWindowIsAvailable(self._conversationWindowHandle)
			or self._conversationWindowHandleFrom(api.getForegroundObject(), None) != self._conversationWindowHandle
		):
			self._nativeFallbackClock = None
			return
		root = getattr(self._buffer, "rootNVDAObject", None)
		if codeDocumentUrl(root) != self._nativeTaskDocument:
			self._recordNativeTaskState(None, now)
			self._nativeFallbackClock = None
			self._nativeTaskObserver.request()
			return
		# UIA can miss a busy-state event. Recheck an active UIA feed at a low rate.
		if getattr(root, "UIAElement", None) is not None and now - self._lastNativeTaskSampleAt >= 5:
			self._nativeTaskObserver.request()
			return
		conf = _settings()
		if not conf["announceWorking"]:
			return
		if self._nativeFallbackClock is None:
			self._nativeFallbackClock = now, None, now
			self._nativePulseCount = 0
		started, lastClick, lastPulse = self._nativeFallbackClock
		if now - started >= conf["maximumBusyMinutes"] * 60:
			return
		mode = conf[CATEGORY_OUTPUT_CONFIG["working"]]
		actions = categoryOutputActions(mode, conf["speech"], conf["braille"], conf["soundWhenSpeechUnavailable"])
		if conf["announceHeartbeat"] and now - lastPulse >= conf["workingIntervalSeconds"]:
			lastPulse = now
			if self._emitNativeProgressPulse(self._estimatedNativeTaskSeconds(now), conf, actions, estimated=True):
				lastClick = now
		if (
			conf["continuousWorkingClicks"] and actions["sound"]
			and (now - started) * 1000 >= conf["workingClickStartDelayMs"]
			and (lastClick is None or (now - lastClick) * 1000 >= conf["workingClickIntervalMs"])
		):
			lastClick = now
			_playProgressSound("working", _("Working"), conf["progressSoundStyle"], conf["clickVolume"])
		self._nativeFallbackClock = started, lastClick, lastPulse

	def _reportNativeTaskStatus(self):
		focus = api.getFocusObject()
		buffer = None
		try:
			buffer = self._rememberBuffer(focus)
			state, seconds = self._readNativeTaskProgress(buffer, focus) if buffer else (None, None)
		except Exception:
			log.debugWarning("Claude Desktop Access could not read the native task status", exc_info=True)
			state, seconds = None, None
		now = time.monotonic()
		if buffer is not None:
			self._recordNativeTaskState(state, now)
		if seconds is not None:
			ui.message(formatElapsedDuration(seconds, _))
		elif state is True:
			duration = formatElapsedDuration(self._estimatedNativeTaskSeconds(now), _)
			ui.message(_("Estimated elapsed time is {duration}").format(duration=duration))
		elif state is False:
			ui.message(_("No active Claude task"))
		else:
			ui.message(_("Claude's native task status is unavailable"))

	@script(description=_("Report current Claude activity or repeat the latest message"))
	def script_repeatLatestStatus(self, gesture):
		agentName = modeDisplayName(self._conversationMode)
		message = currentActivitySummary(
			self._nativeTaskState is True if self._nativeTaskDocument else self._busy,
			self._activeCategory, self._latestMessage, self._nativeTaskSeconds, _, agentName,
		)
		conf = _settings()
		_send(
			message, conf["speech"], conf["braille"], "other", conf["soundWhenSpeechUnavailable"],
			brailleMessage=self._latestFullMessage or message,
		)

	@script(description=_("Toggle Minimal and Full Claude announcements"))
	def script_toggleVerbosity(self, gesture):
		conf = _settings()
		conf["verbosity"] = "minimal" if conf["verbosity"] == "full" else "full"
		message = _("Claude announcements: {mode}").format(mode=conf["verbosity"])
		_send(message, conf["speech"], conf["braille"], "other", conf["soundWhenSpeechUnavailable"])

	@script(description=_("Pause or resume Claude announcements"))
	def script_togglePause(self, gesture):
		self._paused = not self._paused
		ui.message(_("Claude announcements paused") if self._paused else _("Claude announcements resumed"))

	@script(description=_("Read the previous Claude announcement"))
	def script_previousHistory(self, gesture):
		self._historyMessage(-1)

	@script(description=_("Read the next Claude announcement"))
	def script_nextHistory(self, gesture):
		self._historyMessage(1)

	@script(description=_("Show Claude announcement history"))
	def script_showHistory(self, gesture):
		if not self._speechHistory and not self._brailleHistory:
			ui.message(_("No activity announcement history is available"))
			return
		sections = []
		if self._speechHistory:
			sections.append(_("Speech history") + "\n" + "\n".join(self._speechHistory.items()))
		if self._brailleHistory and self._brailleHistory.items() != self._speechHistory.items():
			sections.append(_("Braille history") + "\n" + "\n".join(self._brailleHistory.items()))
		ui.browseableMessage("\n\n".join(sections), title=_("Claude Desktop Access announcement history"))

	@script(description=_("Clear Claude announcement history"))
	def script_clearHistory(self, gesture):
		self._speechHistory.clear()
		self._brailleHistory.clear()
		ui.message(_("Claude announcement history cleared"))

	@script(description=_("Toggle Claude privacy redaction"))
	def script_togglePrivacy(self, gesture):
		conf = _settings()
		conf["redactSensitive"] = not conf["redactSensitive"]
		ui.message(_("Claude privacy redaction on") if conf["redactSensitive"] else _("Claude privacy redaction off"))

	@script(description=_("Show sanitized Claude Desktop Access diagnostics"))
	def script_showDiagnostics(self, gesture):
		ui.browseableMessage(self._diagnosticReport(), title=_("Claude Desktop Access diagnostics"))

	@script(description=_("Copy sanitized Claude Desktop Access diagnostics"))
	def script_copyDiagnostics(self, gesture):
		if not wx.TheClipboard.Open():
			ui.message(_("Could not open the clipboard"))
			return
		try:
			wx.TheClipboard.SetData(wx.TextDataObject(self._diagnosticReport()))
			wx.TheClipboard.Flush()
		finally:
			wx.TheClipboard.Close()
		ui.message(_("Sanitized Claude diagnostics copied"))

	@script(description=_("Save a sanitized Claude Desktop Access support report"))
	def script_saveSupportReport(self, gesture):
		_saveSupportReport(gui.mainFrame, self._diagnosticReport())

	@script(description=_("Copy latest full Claude progress"))
	def script_copyLatestFullProgress(self, gesture):
		if not self._latestFullMessage:
			ui.message(_("No complete Claude progress message is available"))
			return
		if not wx.TheClipboard.Open():
			ui.message(_("Could not open the clipboard"))
			return
		try:
			wx.TheClipboard.SetData(wx.TextDataObject(self._latestFullMessage))
			wx.TheClipboard.Flush()
		finally:
			wx.TheClipboard.Close()
		ui.message(_("Latest full Claude progress copied"))

	@script(description=_("Run Claude Desktop Access compatibility self-test"))
	def script_runCompatibilitySelfTest(self, gesture):
		checks = [
			_("Global plugin loaded: yes"),
			_("Claude monitoring attached: {value}").format(value=_("yes") if self._buffer else _("no")),
			_("Speech enabled: {value}").format(value=_("yes") if _settings()["speech"] else _("no")),
			_("Braille enabled: {value}").format(value=_("yes") if _settings()["braille"] else _("no")),
			_("Sound inventory: {count} files").format(count=len(list((Path(__file__).parent / "sounds").rglob("*.wav")))),
			_("Recent chats cached: {count}").format(count=len(self._chatHistoryTitles())),
			_("Archived chats cached: {count}").format(count=len(self._loadArchivedChatHistory()[0])),
			_("Native embedded browser navigation: yes"),
			_("Embedded browser loading announcements: {value}").format(
				value=_("yes") if _settings()["announceEmbeddedBrowserProgress"] else _("no"),
			),
			_("Embedded browser focus detected: {value}").format(
				value=_("yes") if self._embeddedBrowserFocused else _("no"),
			),
			_("Last inspection error: {value}").format(value=self._lastInspectionError),
		]
		_showBrowseableMessageAtTop("\n".join(checks), _("Claude Desktop Access — compatibility self-test"))

	@script(description=_("Open Claude usage settings"))
	def script_openUsageStatistics(self, gesture):
		_openUsageDashboard(_("Opening Claude usage settings"))

	@script(description=_("Open Claude help"))
	def script_openUsageCredits(self, gesture):
		wx.LaunchDefaultBrowser("https://support.claude.com/")

	def _showChatHistoryDialog(self, mode):
		"""Present the settled mode-specific history without starting another expansion."""
		agentName = modeDisplayName(mode)
		if mode != self._conversationMode or mode not in ("claude", "code", "cowork"):
			ui.message(_("The chat-history mode changed. Open chat history again"))
			return False
		if not self._chatHistoryCacheCurrent.get(mode, False):
			self._schedulePoll(delay=150, requestInspection=True)
			ui.message(_("{agent} chat history is refreshing. Try again in a moment").format(agent=agentName))
			log.info("Claude Desktop Access deferred opening unsettled %s chat history", mode)
			return False
		recentTitles = self._chatHistoryTitles(mode)
		archivedTitles, archivedLoaded = self._loadArchivedChatHistory(mode)
		if not recentTitles and not archivedTitles:
			ui.message(_("No {agent} chats are cached yet. Wait a moment and try again").format(agent=agentName))
			return False
		if self._chatHistoryDialog:
			if self._chatHistoryDialogMode == mode:
				self._chatHistoryDialog.Raise()
				self._chatHistoryDialog.search.SetFocus()
				return True
			self._chatHistoryDialog.Close()
		gui.mainFrame.prePopup()
		try:
			self._chatHistoryDialog = ChatHistoryDialog(
				gui.mainFrame, mode, agentName, recentTitles, archivedTitles, archivedLoaded,
				lambda: self._refreshChatHistoryData(mode),
				self._queueChatHistoryAction, self._chatHistoryClosed,
			)
			self._chatHistoryDialogMode = mode
			self._chatHistoryDialog.Show()
		except Exception:
			self._chatHistoryDialog = None
			gui.mainFrame.postPopup()
			raise
		log.info(
			"Claude Desktop Access displayed %d recent and %d archived %s chats",
			len(recentTitles), len(archivedTitles), mode,
		)
		return True

	@script(description=_("Open searchable and arrow-navigable Claude chat history"))
	def script_openChatHistory(self, gesture):
		"""Expand native Recents, then show searchable Recent and Archived lists."""
		focus = api.getFocusObject()
		if not _isClaudeObject(focus):
			ui.message(_("Move to Claude before opening chat history"))
			return
		try:
			self._rememberBuffer(focus)
			if not self._conversationModeObserved:
				self._queueConversationModeProbe("history mode verification")
				ui.message(_("Claude mode is being detected. Try history again in a moment"))
				return
			mode = self._conversationMode
			agentName = modeDisplayName(mode)
			if not self._buffer or mode not in ("claude", "code", "cowork"):
				ui.message(_("Chat history is not available in the current view"))
				return
			if self._pendingChatHistoryExpansion:
				ui.message(_("Recent chat history is already loading"))
				return
			if not self._chatHistoryCacheCurrent.get(mode, False):
				self._schedulePoll(delay=150, requestInspection=True)
				ui.message(_("{agent} chat history is refreshing. Try again in a moment").format(agent=agentName))
				log.info("Claude Desktop Access deferred opening unsettled %s chat history", mode)
				return
			if self._startChatHistoryExpansion(mode):
				return
			self._showChatHistoryDialog(mode)
		except Exception:
			log.debugWarning("Claude Desktop Access could not display chat history", exc_info=True)
			ui.message(_("Chat history could not be opened"))

	def event_gainFocus(self, obj, nextHandler):
		nextHandler()
		try:
			focusCue = self._updateAppFocusState(obj)
			self._updateEmbeddedBrowserFocus(obj)
			self._rememberBuffer(obj)
			self._schedulePopupDialogFocus(obj)
			if self._announceUsageLimit(obj):
				return
			isPrompt = _isCodePromptObject(obj)
			self._promptFocused = isPrompt
			if isPrompt:
				self._lastPromptObject = obj
			if not isPrompt:
				self._brailleCompositionActive = False
			if isPrompt:
				self._trackPromptSubmission(obj)
			# Claude briefly focuses an intermediate section after Enter and before
			# returning to the now-empty prompt. Preserve draft/submission state across
			# those in-app focus events; _resetTaskState handles real task switches.
			if _isClaudeObject(obj):
				if focusCue == "active":
					self._nativeTaskObserver.request()
				# Moving among controls does not change task status. Inspect once when
				# returning to Claude; a newly attached buffer is already marked dirty.
				self._schedulePoll(requestInspection=focusCue == "active")
		except Exception:
			log.debugWarning("Claude Desktop Access focus-event handling failed", exc_info=True)

	def event_foreground(self, obj, nextHandler):
		nextHandler()
		try:
			focusCue = self._updateAppFocusState(obj)
			self._updateEmbeddedBrowserFocus(obj)
			self._rememberBuffer(obj)
			if self._announceUsageLimit(obj):
				return
			if _isClaudeObject(obj):
				if focusCue == "active":
					self._nativeTaskObserver.request()
				self._schedulePoll(requestInspection=focusCue == "active")
		except Exception:
			log.debugWarning("Claude Desktop Access foreground-event handling failed", exc_info=True)

	def _requestUIATaskTimerUpdate(self, obj):
		if (
			self._nativeTaskDocument and getattr(obj, "UIAElement", None) is not None
			and _roleName(obj) in ("grouping", "section", "statictext", "statusbar", "textframe", "timer")
			and _isClaudeObject(obj) and isTaskTimerObject(obj)
			and self._eventBelongsToRetainedConversationBuffer(obj)
		):
			self._nativeTaskObserver.request()

	def event_nameChange(self, obj, nextHandler):
		nextHandler()
		try:
			self._requestUIATaskTimerUpdate(obj)
			self._noteEmbeddedBrowserDocument(obj)
			self._rememberBuffer(obj)
			self._schedulePopupDialogFocus(obj)
			if self._announceUsageLimit(obj):
				return
			self._announceEmbeddedBrowserProgress(obj)
			statusHandled = self._announceStatus(obj)
			if getattr(obj, "role", None) == Role.BUTTON and self._eventUsesConversationBuffer(obj):
				self._schedulePoll(requestInspection=not statusHandled)
		except Exception:
			log.debugWarning("Claude Desktop Access name-change handling failed", exc_info=True)

	def event_valueChange(self, obj, nextHandler):
		nextHandler()
		try:
			self._requestUIATaskTimerUpdate(obj)
			if self._announceUsageLimit(obj):
				return
			isPrompt = self._notePromptTyping(obj)
			submitted = self._trackPromptSubmission(obj, allowTextInfo=not isPrompt)
			if isPrompt and not submitted:
				self._schedulePromptInspection(obj)
			elif submitted:
				self._promptTypingUntil = 0.0
			pluginHandled = self._announcePluginInstallProgress(obj)
			self._announceEmbeddedBrowserProgress(obj)
			statusHandled = self._announceStatus(obj)
			if submitted or (
				getattr(obj, "role", None) == Role.BUTTON and self._eventUsesConversationBuffer(obj)
			):
				self._schedulePoll(requestInspection=submitted or not (pluginHandled or statusHandled))
		except Exception:
			log.debugWarning("Claude Desktop Access value-change handling failed", exc_info=True)

	def event_stateChange(self, obj, nextHandler):
		nextHandler()
		try:
			if self._observeConversationModeControl(obj, "mode switch state event"):
				self._schedulePoll(requestInspection=True)
			if (
				self._nativeTaskDocument and _roleName(obj) in ("grouping", "section", "feed")
				and _isClaudeObject(obj) and isCodeTaskFeed(obj)
				and self._eventBelongsToRetainedConversationBuffer(obj)
			):
				self._nativeTaskObserver.request()
			if self._announceUsageLimit(obj):
				return
			self._updateEmbeddedBrowserDocumentBusyState(obj)
		except Exception:
			log.debugWarning("Claude Desktop Access state-change handling failed", exc_info=True)

	def event_liveRegionChange(self, obj, nextHandler):
		suppressNative = False
		text = ""
		limitHandled = False
		try:
			text = " ".join(str(
				getattr(obj, "name", "") or getattr(obj, "value", "") or ""
			).split())
			if (
				self._nativeTaskDocument and getattr(obj, "UIAElement", None) is not None
				and getattr(obj, "role", None) in (Role.STATUSBAR, Role.ALERT)
				and self._eventBelongsToRetainedConversationBuffer(obj)
			):
				self._nativeTaskObserver.request()
			limitHandled = self._announceUsageLimit(obj, text)
			# Chromium can rebuild the event object's tree interceptor while the user
			# remains in the same conversation buffer. Determine reading mode from the
			# retained conversation buffer so a replacement live-region object cannot
			# bypass protection and relocate speech or the Braille viewport.
			browseMode = self._conversationBrowseModeActive()
			suppressNative = limitHandled or shouldSuppressNativeConversationUpdate(
				_settings()["protectBrailleReading"], self._appFocusState, browseMode,
				self._eventUsesConversationBuffer(obj), self._popupDialogFromObject(obj) is not None,
				text,
			)
		except Exception:
			log.debugWarning("Claude Desktop Access could not classify a conversation live update", exc_info=True)
		if suppressNative:
			self._suppressedConversationUpdates += 1
			log.debug("Claude Desktop Access preserved browse-mode reading across a streamed response update")
		else:
			nextHandler()
		try:
			self._schedulePopupDialogFocus(obj)
			if limitHandled or self._announceUsageLimit(obj, text):
				return
			statusHandled = self._announceStatus(obj)
			# Ordinary Response text was intentionally withheld from NVDA's native
			# live-region handler above, so do not reintroduce the same interruption
			# through add-on commentary. Completion still reaches the state machine.
			if suppressNative and not statusDetails(text)[0]:
				commentaryHandled = True
			else:
				commentaryHandled = self._announceCommentary(obj)
			if getattr(obj, "role", None) == Role.BUTTON and self._eventUsesConversationBuffer(obj):
				self._schedulePoll(requestInspection=not (statusHandled or commentaryHandled))
		except Exception:
			log.debugWarning("Claude Desktop Access live-region handling failed", exc_info=True)

	def event_show(self, obj, nextHandler):
		nextHandler()
		try:
			if self._observeConversationModeControl(obj, "mode switch show event"):
				self._schedulePoll(requestInspection=True)
			self._noteEmbeddedBrowserDocument(obj, force=True)
			self._schedulePopupDialogFocus(obj)
			if self._announceUsageLimit(obj):
				return
			pluginHandled = self._announcePluginInstallProgress(obj)
			self._announceEmbeddedBrowserProgress(obj)
			statusHandled = self._announceStatus(obj)
			if getattr(obj, "role", None) == Role.BUTTON and self._eventUsesConversationBuffer(obj):
				self._schedulePoll(requestInspection=not (pluginHandled or statusHandled))
		except Exception:
			log.debugWarning("Claude Desktop Access show-event handling failed", exc_info=True)

	def event_alert(self, obj, nextHandler):
		nextHandler()
		try:
			self._schedulePopupDialogFocus(obj)
			self._announceUsageLimit(obj)
		except Exception:
			log.debugWarning("Claude Desktop Access alert-event handling failed", exc_info=True)

	def event_textChange(self, obj, nextHandler):
		nextHandler()
		try:
			isPrompt = self._notePromptTyping(obj)
			submitted = self._trackPromptSubmission(obj, allowTextInfo=not isPrompt)
			if isPrompt and not submitted:
				self._schedulePromptInspection(obj)
			elif submitted:
				self._promptTypingUntil = 0.0
			if submitted:
				self._schedulePoll()
		except Exception:
			log.debugWarning("Claude Desktop Access text-change handling failed", exc_info=True)
