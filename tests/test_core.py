import importlib.util
import ast
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import unittest
import wave


CORE_PATH = Path(__file__).parents[1] / "globalPlugins" / "claudeDesktopAccess" / "core.py"
PROJECT_ROOT = Path(__file__).parents[1]
PLUGIN_PATH = CORE_PATH.parent / "__init__.py"
CHAT_DIALOG_PATH = CORE_PATH.parent / "chatHistoryDialog.py"
SOUND_OUTPUT_PATH = CORE_PATH.parent / "soundOutput.py"
CLICK_GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_click_sounds.py"
ACCESSIBILITY_FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "claude_accessibility_snapshots.json"
ADDON_STORE_METADATA_PATH = PROJECT_ROOT / "tools" / "addon_store_metadata.py"
AUDIT_PATH = PROJECT_ROOT / "tools" / "audit_addon.py"
BUILD_PATH = PROJECT_ROOT / "tools" / "build_addon.py"
RELEASE_WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "release.yml"
TRANSLATION_TEMPLATE_PATH = PROJECT_ROOT / "locale" / "claudeDesktopAccess.pot"
BROWSER_ACCESS_PATH = CORE_PATH.parent / "browserAccess.py"
BROWSER_NAVIGATOR_DIALOG_PATH = CORE_PATH.parent / "browserNavigatorDialog.py"
CLAUDE_APP_MODULE_PATH = PROJECT_ROOT / "appModules" / "claude.py"
CODE_APP_MODULE_PATH = PROJECT_ROOT / "appModules" / "code.py"
SPEC = importlib.util.spec_from_file_location("code_status_core", CORE_PATH)
core = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(core)
STORE_SPEC = importlib.util.spec_from_file_location("code_store_metadata", ADDON_STORE_METADATA_PATH)
storeMetadata = importlib.util.module_from_spec(STORE_SPEC)
STORE_SPEC.loader.exec_module(storeMetadata)
BUILD_SPEC = importlib.util.spec_from_file_location("code_package_builder", BUILD_PATH)
packageBuilder = importlib.util.module_from_spec(BUILD_SPEC)
BUILD_SPEC.loader.exec_module(packageBuilder)
BROWSER_ACCESS_SPEC = importlib.util.spec_from_file_location("code_browser_access", BROWSER_ACCESS_PATH)
browserAccess = importlib.util.module_from_spec(BROWSER_ACCESS_SPEC)
BROWSER_ACCESS_SPEC.loader.exec_module(browserAccess)
AnnouncementHistory = core.AnnouncementHistory
firstStatusLabel = core.firstStatusLabel
statusMessage = core.statusMessage
brailleStatusMessage = core.brailleStatusMessage
statusDetails = core.statusDetails
redactSensitive = core.redactSensitive
elapsedSeconds = core.elapsedSeconds
formatElapsedDuration = core.formatElapsedDuration
completedTextDelta = core.completedTextDelta
outputActions = core.outputActions
tonePattern = core.tonePattern
nextBusyState = core.nextBusyState
pollDelay = core.pollDelay
bufferInspectionDue = core.bufferInspectionDue
conversationWindowShouldDetach = core.conversationWindowShouldDetach
brailleTypingGestureCommitsText = core.brailleTypingGestureCommitsText
isBrailleTypingGestureIdentifier = core.isBrailleTypingGestureIdentifier
isPromptSubmissionGestureIdentifier = core.isPromptSubmissionGestureIdentifier
promptSubmissionGestureShouldStart = core.promptSubmissionGestureShouldStart
shouldPreserveBrailleComposition = core.shouldPreserveBrailleComposition
coalescedPollDelay = core.coalescedPollDelay
shouldReplaceScheduledPoll = core.shouldReplaceScheduledPoll
shouldPlayContinuousWorkingClick = core.shouldPlayContinuousWorkingClick
shouldSuppressRoutineBraille = core.shouldSuppressRoutineBraille
shouldSuppressNativeConversationUpdate = core.shouldSuppressNativeConversationUpdate
focusStateTransition = core.focusStateTransition
promptSubmissionTransition = core.promptSubmissionTransition
isCodePromptLabel = core.isCodePromptLabel
userMessageNumber = core.userMessageNumber
userMessageSubmissionTransition = core.userMessageSubmissionTransition
confirmedUserMessageSubmission = core.confirmedUserMessageSubmission
isStopControlLabel = core.isStopControlLabel
stopControlTransition = core.stopControlTransition
shouldSuppressDuplicate = core.shouldSuppressDuplicate
shouldLogDiagnosticSnapshot = core.shouldLogDiagnosticSnapshot
responseCompletionTransition = core.responseCompletionTransition
isResponseCompletionMarkerText = core.isResponseCompletionMarkerText
responseCompletionScanMarker = core.responseCompletionScanMarker
shouldFinalizeResponseCompletion = core.shouldFinalizeResponseCompletion
isTaskCompletionLabel = core.isTaskCompletionLabel
intermediateCompletionCategory = core.intermediateCompletionCategory
isKnownNonStatusButton = core.isKnownNonStatusButton
isChatHistoryInterfaceText = core.isChatHistoryInterfaceText
isChatHistoryConversationBoundary = core.isChatHistoryConversationBoundary
soundKey = core.soundKey
categoryOutputActions = core.categoryOutputActions
announcementPriority = core.announcementPriority
changelogForDisplay = core.changelogForDisplay
viewerTitleMatches = core.viewerTitleMatches
previewSelection = core.previewSelection
formatCustomAnnouncement = core.formatCustomAnnouncement
uniqueThreadLabels = core.uniqueThreadLabels
semanticStatusKey = core.semanticStatusKey
shouldSuppressSemanticDuplicate = core.shouldSuppressSemanticDuplicate
duplicateChannelActions = core.duplicateChannelActions
formatCommandSpeech = core.formatCommandSpeech
promptControlKind = core.promptControlKind
repairConfigurationValues = core.repairConfigurationValues
mergeSupportedAppNames = core.mergeSupportedAppNames
conversationModeFromDocumentNames = core.conversationModeFromDocumentNames
conversationModeFromSwitchLabel = core.conversationModeFromSwitchLabel
chatHistorySnapshotDecision = core.chatHistorySnapshotDecision
modeSpecificRecentChatTitles = core.modeSpecificRecentChatTitles
chatTitleMatches = core.chatTitleMatches
chatActionMatches = core.chatActionMatches
voiceControlKind = core.voiceControlKind
chatMessageShortcutIndex = core.chatMessageShortcutIndex
chatMessagesFromTokens = core.chatMessagesFromTokens
isChatMessageTrailingUiText = core.isChatMessageTrailingUiText
isChatOptionsLabel = core.isChatOptionsLabel
isPermissionDecisionLabel = core.isPermissionDecisionLabel
isPermissionPromptText = core.isPermissionPromptText
usageLimitNotice = core.usageLimitNotice
pluginInstallProgress = core.pluginInstallProgress
currentActivitySummary = core.currentActivitySummary
backgroundActivityName = core.backgroundActivityName
looksLikeCodeConversation = core.looksLikeCodeConversation
looksLikeBlankCodeConversation = core.looksLikeBlankCodeConversation
pendingChatTitle = core.pendingChatTitle
pluginProgressBusyTransition = core.pluginProgressBusyTransition
supersedesResponseCompletionCandidate = core.supersedesResponseCompletionCandidate


class StatusMessageTests(unittest.TestCase):

	def test_embedded_browser_accessibility_classification_is_conservative(self):
		self.assertTrue(browserAccess.isEmbeddedBrowserContainerText("Browser", ""))
		self.assertTrue(browserAccess.isEmbeddedBrowserContainerText("", "WebView preview"))
		self.assertFalse(browserAccess.isEmbeddedBrowserContainerText("Code", "main conversation"))
		self.assertTrue(browserAccess.isEmbeddedBrowserContainerRole("pane"))
		self.assertFalse(browserAccess.isEmbeddedBrowserContainerRole("button"))
		self.assertFalse(browserAccess.isEmbeddedBrowserContainerRole("menu"))
		self.assertFalse(browserAccess.isEmbeddedBrowserDocumentStructure("menu", "document"))
		self.assertTrue(browserAccess.isEmbeddedBrowserDocumentStructure("heading", "document", "document"))
		self.assertEqual("back", browserAccess.embeddedBrowserControlKind("Go back", "button"))
		self.assertEqual("address", browserAccess.embeddedBrowserControlKind("Address and search bar", "edit"))
		self.assertEqual("content", browserAccess.embeddedBrowserControlKind("Example page", "document"))
		self.assertEqual("", browserAccess.embeddedBrowserControlKind("Approve permission", "button"))
		self.assertEqual("Example page", browserAccess.embeddedBrowserTitle("  Example   page  "))
		self.assertEqual("", browserAccess.embeddedBrowserTitle("Embedded browser"))
		self.assertEqual("", browserAccess.browserNavigatorCategory("document", "content"))

	def test_browser_navigator_safe_address_summary_and_snapshot_helpers(self):
		self.assertEqual(
			"https://example.com/account?secret=one#section",
			browserAccess.browserPageAddress(
				"Address: https://example.com/account?secret=one#section",
			),
		)
		self.assertEqual("http://localhost:3000/page", browserAccess.browserPageAddress(
			"http://localhost:3000/page",
		))
		self.assertEqual("", browserAccess.browserPageAddress(
			"javascript:alert(1)", "data:text/html,private",
		))
		self.assertEqual("example.com", browserAccess.browserAddressDomain(
			"https://user:password@example.com/account?secret=one#section",
		))
		self.assertEqual(
			"account|example.com/account",
			browserAccess.browserPageIdentity(
				"Account", "https://user:password@example.com/account?secret=one#section",
			),
		)
		self.assertEqual("account|localhost:3000/page", browserAccess.browserPageIdentity(
			"Account", "http://localhost:3000/page?secret=one",
		))
		self.assertEqual("", browserAccess.browserPageIdentity("", ""))
		items = (
			{"category": "headings"}, {"category": "links"},
			{"category": "links"}, {"category": "formFields"},
		)
		summary = browserAccess.browserPageSummary(
			"Account", "https://example.com/private?token=secret", items, 70, True,
		)
		self.assertIn("Domain: example.com", summary)
		self.assertIn("1 headings", summary)
		self.assertIn("2 links", summary)
		self.assertIn("loading, 70 percent", summary)
		self.assertIn("scan limit reached", summary)
		self.assertNotIn("token", summary)
		snapshot = browserAccess.browserSnapshotText(
			"Account", "https://example.com/private?token=secret",
			("Welcome", "Welcome", "Sign in, button"), True,
		)
		self.assertEqual(1, snapshot.count("Welcome"))
		self.assertIn("Domain: example.com", snapshot)
		self.assertNotIn("token", snapshot)
		self.assertIn("safe scan limit", snapshot)

	def test_browser_navigator_categories_labels_and_search(self):
		self.assertEqual("headings", browserAccess.browserNavigatorCategory("heading"))
		self.assertEqual("landmarks", browserAccess.browserNavigatorCategory("navigation"))
		self.assertEqual("links", browserAccess.browserNavigatorCategory("link"))
		self.assertEqual("buttons", browserAccess.browserNavigatorCategory("button"))
		self.assertEqual("formFields", browserAccess.browserNavigatorCategory("edit"))
		self.assertEqual("tables", browserAccess.browserNavigatorCategory("table"))
		self.assertEqual("controls", browserAccess.browserNavigatorCategory("button", "reload"))
		label = browserAccess.browserNavigatorItemLabel(
			"headings", "Account settings", "heading", level=2, states=("expanded",),
		)
		self.assertEqual("Account settings, heading level 2, expanded", label)
		item = {"category": "headings", "label": label}
		self.assertTrue(browserAccess.browserNavigatorMatches(item, "all", "ACCOUNT"))
		self.assertTrue(browserAccess.browserNavigatorMatches(item, "headings", "level 2"))
		self.assertFalse(browserAccess.browserNavigatorMatches(item, "links", "account"))
		self.assertNotEqual(
			browserAccess.browserNavigatorSignature("links", "link", "Learn more"),
			browserAccess.browserNavigatorSignature("links", "link", "Learn more", 2),
		)
		longName = "A" * 900
		secondLongSignature = browserAccess.browserNavigatorSignature("links", "link", longName, 2)
		self.assertLessEqual(len(secondLongSignature), 600)
		self.assertTrue(secondLongSignature.endswith("|2"))









	def test_embedded_browser_progress_is_bucketed_and_scoped(self):
		self.assertEqual(
			("loading page", 47, 40),
			browserAccess.embeddedBrowserProgress("Loading page", "47%"),
		)
		self.assertEqual(
			("loading page", 100, 100),
			browserAccess.embeddedBrowserProgress("Loading page", "100 percent"),
		)
		self.assertEqual(("loading page", None, None), browserAccess.embeddedBrowserProgress("Loading page"))
		self.assertEqual(("loading page", 5, 10), browserAccess.embeddedBrowserProgress("Loading page", "5"))
		self.assertIsNone(browserAccess.embeddedBrowserProgress("Downloading model"))



	def test_package_builder_normalizes_text_but_preserves_binary_data(self):
		with tempfile.TemporaryDirectory() as tempDir:
			textPath = Path(tempDir) / "module.py"
			binaryPath = Path(tempDir) / "sound.wav"
			textPath.write_bytes(b"first\r\nsecond\rthird\n")
			binary = b"RIFF\r\n\x00\rdata"
			binaryPath.write_bytes(binary)
			self.assertEqual(b"first\nsecond\nthird\n", packageBuilder.packageData(textPath))
			self.assertEqual(binary, packageBuilder.packageData(binaryPath))

	def test_package_builder_includes_docs_and_only_current_tiered_sounds(self):
		paths = tuple(path.relative_to(PROJECT_ROOT).as_posix() for path in packageBuilder.packageFiles(PROJECT_ROOT))
		for required in ("manifest.ini", "readme.md", "changelog.md", "LICENSE.txt"):
			self.assertIn(required, paths)
		self.assertEqual(len(paths), len(set(paths)))
		self.assertIn("appModules/claude.py", paths)
		self.assertNotIn("appModules/code.py", paths)
		self.assertEqual(51, sum(path.endswith(".wav") for path in paths))
		self.assertIn("globalPlugins/claudeDesktopAccess/browserNavigatorDialog.py", paths)
		self.assertFalse(any(path.startswith("globalPlugins/claudeDesktopAccess/sounds/") and path.count("/") == 3 for path in paths))
		self.assertFalse(any(path.endswith(".pot") for path in paths))










	def test_voice_control_labels_are_exact_and_do_not_match_speaker_controls(self):
		for label, expected in (
			("Start voice chat", "start"), ("Start voice mode", "start"),
			("Stop voice chat", "stop"), ("End voice chat", "stop"),
			("Leave voice mode", "stop"), ("Exit voice mode", "stop"),
			("Mute microphone", "mute"), ("Mute mic", "mute"),
			("Unmute microphone", "unmute"), ("Unmute mic", "unmute"),
		):
			self.assertEqual(expected, voiceControlKind(label), label)
			self.assertTrue(isKnownNonStatusButton(label), label)
		for label in ("Mute speakers", "Unmute speakers", "Voice chat", "Microphone", "Mute"):
			self.assertEqual("", voiceControlKind(label), label)




	def test_restricted_nvda_runtime_does_not_require_known_optional_modules(self):
		source = "\n".join(
			path.read_text(encoding="utf-8")
			for path in CORE_PATH.parent.glob("*.py")
		)
		for forbiddenImport in ("import sqlite3", "import requests", "import numpy", "import yaml"):
			self.assertNotIn(forbiddenImport, source)

	def test_semantic_duplicate_suppression_ignores_cosmetic_wording_changes(self):
		self.assertEqual("editing code", semanticStatusKey("Editing file"))
		self.assertEqual("editing code", semanticStatusKey("Editing code"))
		self.assertTrue(shouldSuppressSemanticDuplicate("Editing file", "Editing code", 0.5))
		self.assertFalse(shouldSuppressSemanticDuplicate("Running tests", "Editing code", 0.5))
		self.assertFalse(shouldSuppressSemanticDuplicate("Editing file", "Editing code", 1.5))

	def test_braille_detail_is_independent_of_speech_verbosity(self):
		label = "Running shell command: rg -n status globalPlugins"
		self.assertEqual("Running command", brailleStatusMessage(label, detail="concise"))
		self.assertEqual("Running command", brailleStatusMessage(label, detail="informative"))
		self.assertEqual(label, brailleStatusMessage(label, detail="full"))
		self.assertEqual(label, brailleStatusMessage(label, detail="invalid"))

	def test_speech_duplicate_does_not_hide_distinct_braille_detail(self):
		result = duplicateChannelActions(
			"Running command", "Running shell command: rg one", "Running command",
			"Running shell command: rg two", 0.2, 0.2,
		)
		self.assertEqual({"speech": True, "braille": False}, result)


	def test_command_speech_punctuation_and_length_controls(self):
		self.assertEqual(
			("rg files pipe sort redirect to output.txt", False),
			formatCommandSpeech("rg files | sort > output.txt", "enhanced", 240),
		)
		literal, shortened = formatCommandSpeech("one && two", "literal", 240)
		self.assertEqual("one ampersand ampersand two", literal)
		self.assertFalse(shortened)
		short, shortened = formatCommandSpeech("x" * 100, "normal", 40)
		self.assertTrue(shortened)
		self.assertLessEqual(len(short), 41)

	def test_prompt_toolbar_control_names_are_classified_without_conversation_search(self):
		self.assertEqual("files", promptControlKind("Add files and more"))
		self.assertEqual("files", promptControlKind("Attach files"))
		self.assertEqual("permissions", promptControlKind("Change permissions"))
		self.assertEqual("model", promptControlKind("Select model"))
		self.assertEqual("model", promptControlKind("GPT-5.6 Developer"))
		self.assertEqual("model", promptControlKind("o4-mini"))
		self.assertEqual("", promptControlKind("Send"))

	def test_configuration_repair_covers_choices_numbers_booleans_and_strings(self):
		values = {
			"outputCommands": "invalid", "workingClickStartDelayMs": -1,
			"maximumBusyMinutes": "bad", "speech": "false", "braille": "invalid",
			"supportedAppNames": 42,
		}
		repaired = repairConfigurationValues(
			values,
			{"outputCommands": (("all", "off"), "all")},
			{"workingClickStartDelayMs": (0, 10000, 750), "maximumBusyMinutes": (1, 240, 60)},
			(("speech", True), ("braille", True)),
			(("supportedAppNames", "claude"),),
		)
		self.assertEqual("all", values["outputCommands"])
		self.assertEqual(750, values["workingClickStartDelayMs"])
		self.assertEqual(60, values["maximumBusyMinutes"])
		self.assertFalse(values["speech"])
		self.assertTrue(values["braille"])
		self.assertEqual("claude", values["supportedAppNames"])
		self.assertEqual(len(repaired), len(set(repaired)))

	def test_only_claude_is_required_and_other_products_are_excluded(self):
		self.assertEqual("claude", mergeSupportedAppNames("claude,chatgpt,codex,code"))
		self.assertEqual("claude,customhost", mergeSupportedAppNames("CustomHost,CLAUDE"))

	def test_conversation_document_modes_exclude_nested_browser_documents(self):
		self.assertEqual("claude", conversationModeFromDocumentNames(("Claude",)))
		self.assertEqual("code", conversationModeFromDocumentNames(("Code",)))
		self.assertEqual("", conversationModeFromDocumentNames(("Purchase credits", "Claude")))
		self.assertEqual("", conversationModeFromDocumentNames(("Settings",)))
		self.assertEqual("code", conversationModeFromSwitchLabel("Switch mode, current mode: Code"))
		self.assertEqual("claude", conversationModeFromSwitchLabel("Switch mode, current mode: Claude"))
		self.assertEqual("", conversationModeFromSwitchLabel("Claude"))
		self.assertEqual("", conversationModeFromSwitchLabel("Switch mode"))




	def test_chat_action_requires_exact_normalized_accessible_title(self):
		self.assertTrue(chatTitleMatches(" My   task ", "my task"))
		self.assertTrue(chatTitleMatches("My task", "", titleFoundInsideButton=True))
		self.assertFalse(chatTitleMatches("My task", ""))
		self.assertFalse(chatTitleMatches("My task", "Open My task menu"))
		self.assertFalse(chatTitleMatches("", ""))

	def test_chat_options_button_labels_are_specific(self):
		self.assertTrue(isChatOptionsLabel("Open conversation options"))
		self.assertTrue(isChatOptionsLabel("Project chat options"))
		self.assertTrue(isChatOptionsLabel("More"))
		self.assertFalse(isChatOptionsLabel("Add files and more"))
		self.assertFalse(isChatOptionsLabel("Change permissions"))

	def test_direct_chat_actions_match_only_pin_and_archive_controls(self):
		self.assertTrue(chatActionMatches("pin", "Pin chat"))
		self.assertTrue(chatActionMatches("pin", "Unpin chat"))
		self.assertTrue(chatActionMatches("archive", "Archive chat"))
		self.assertFalse(chatActionMatches("archive", "Archive project"))
		self.assertFalse(chatActionMatches("pin", "Pin message"))



	def test_permission_prompt_and_decision_labels_are_narrow(self):
		self.assertTrue(isPermissionPromptText("Permission required. Allow this command? Deny"))
		self.assertTrue(isPermissionPromptText("This action requires your approval"))
		self.assertFalse(isPermissionPromptText("Change permissions"))
		self.assertTrue(isPermissionDecisionLabel("Allow once"))
		self.assertTrue(isPermissionDecisionLabel("Deny and tell Code what to do"))
		self.assertFalse(isPermissionDecisionLabel("Change permissions"))




	def test_plugin_install_progress_is_scoped_parsed_and_bucketed(self):
		self.assertEqual(
			("plugin", 37, 30),
			pluginInstallProgress("Installing plugin 37%"),
		)
		self.assertEqual(
			("connector", 100, 100),
			pluginInstallProgress("Connector installation 100 percent"),
		)
		self.assertEqual(
			("plugin", None, None),
			pluginInstallProgress("Plugin installation in progress"),
		)
		self.assertEqual(
			("plugin", 100, 100),
			pluginInstallProgress("Plugin installation complete"),
		)
		self.assertIsNone(pluginInstallProgress("Downloading model 50%"))

	def test_current_activity_summary_covers_silent_background_periods(self):
		self.assertEqual("Running Outlook test", currentActivitySummary(True, "tool", "Running Outlook test", 45))
		self.assertEqual("Code is still using tools, 45 seconds", currentActivitySummary(True, "tool", "", 45))
		self.assertEqual("Code is still running commands", currentActivitySummary(True, "command", "", 0))
		self.assertEqual("Code is idle", currentActivitySummary(False, "other", "", 0))
		self.assertEqual("Code is still working, 3 minutes 20 seconds", currentActivitySummary(True, "working", "", 200))
		self.assertEqual(
			"Claude is still thinking, 12 seconds",
			currentActivitySummary(True, "thinking", "", 12, agentName="Claude"),
		)

	def test_elapsed_duration_uses_speech_friendly_units(self):
		self.assertEqual("0 seconds", formatElapsedDuration(0))
		self.assertEqual("59 seconds", formatElapsedDuration(59))
		self.assertEqual("1 minute", formatElapsedDuration(60))
		self.assertEqual("1 minute 25 seconds", formatElapsedDuration(85))
		self.assertEqual("3 minutes 20 seconds", formatElapsedDuration(200))
		self.assertEqual("1 hour 1 minute 1 second", formatElapsedDuration(3661))

	def test_background_activity_names_preserve_file_work_without_claiming_finished_work_continues(self):
		self.assertEqual("Editing code", backgroundActivityName("file", "Editing code: core.py"))
		self.assertEqual("Checking files", backgroundActivityName("file", "Checking files"))
		self.assertEqual("Processing", backgroundActivityName("file", "Reading finished"))
		self.assertEqual("Command", backgroundActivityName("command", "Running command"))
		self.assertEqual("Checking files", backgroundActivityName("command", "Reading file core.py"))
		self.assertEqual("File operations", backgroundActivityName("file", ""))

	def test_conversation_detection_excludes_settings_documents(self):
		self.assertTrue(looksLikeCodeConversation("Main landmark Reply to Claude multiline edit"))
		self.assertTrue(looksLikeCodeConversation("Ask Claude"))
		self.assertTrue(looksLikeCodeConversation("Message Claude"))
		self.assertTrue(looksLikeCodeConversation("Send a message"))
		self.assertFalse(looksLikeCodeConversation("Settings Account Archived chats"))

	def test_blank_chat_detection_ignores_existing_conversation_buffer_refreshes(self):
		self.assertTrue(looksLikeBlankCodeConversation("Main landmark Reply to Claude New chat"))
		self.assertFalse(looksLikeBlankCodeConversation("Reply to Claude User message 3 Response complete: done"))
		self.assertFalse(looksLikeBlankCodeConversation("Reply to Claude Claude said: existing answer"))
		self.assertFalse(looksLikeBlankCodeConversation("Settings General Archived chats"))

	def test_chat_history_snapshot_requires_settle_and_confirmation(self):
		self.assertEqual(
			"settle",
			chatHistorySnapshotDecision(0.1, 0.75, ("Chat",), (), False, None, 0.0, 0.25),
		)
		self.assertEqual(
			"otherMode",
			chatHistorySnapshotDecision(1.0, 0.75, ("Chat",), ("Chat",), True, None, 0.0, 0.25),
		)
		self.assertEqual(
			"confirm",
			chatHistorySnapshotDecision(1.0, 0.75, ("Chat",), (), False, None, 0.0, 0.25),
		)
		self.assertEqual(
			"confirm",
			chatHistorySnapshotDecision(1.0, 0.75, ("Chat",), (), False, ("Chat",), 0.1, 0.25),
		)
		self.assertEqual(
			"publish",
			chatHistorySnapshotDecision(1.0, 0.75, ("Chat",), (), False, ("Chat",), 0.3, 0.25),
		)

	def test_unified_recents_are_partitioned_by_active_code_titles(self):
		unified = ("Claude only", "Shared title", "Another Code task")
		code = (" shared   title ", "Another Code task")
		self.assertEqual(
			("Claude only",),
			modeSpecificRecentChatTitles("claude", unified, code),
		)
		self.assertEqual(
			("Shared title", "Another Code task"),
			modeSpecificRecentChatTitles("code", unified, code),
		)
		self.assertEqual((), modeSpecificRecentChatTitles("unknown", unified, code))








	def test_plugin_progress_only_releases_busy_state_it_started(self):
		self.assertEqual((True, True), pluginProgressBusyTransition(False, False, False))
		self.assertEqual((False, False), pluginProgressBusyTransition(True, True, True))
		self.assertEqual((True, False), pluginProgressBusyTransition(True, False, True))

	def test_stale_pending_chat_titles_are_discarded(self):
		self.assertEqual("My chat", pendingChatTitle(" My  chat ", 2.0))
		self.assertEqual("", pendingChatTitle("My chat", 11.0))
		self.assertEqual("", pendingChatTitle("", 1.0))




	def test_duplicate_archived_titles_keep_every_native_thread_id(self):
		self.assertEqual(
			(
				("00000000-0000-0000-0000-000000000001", "Repeated title"),
				("00000000-0000-0000-0000-000000000002", "Repeated title (2)"),
				("00000000-0000-0000-0000-000000000003", "Repeated title (3)"),
			),
			uniqueThreadLabels((
				("00000000-0000-0000-0000-000000000001", "Repeated title"),
				("00000000-0000-0000-0000-000000000002", "Repeated title"),
				("00000000-0000-0000-0000-000000000003", "Repeated title"),
			)),
		)
		labels = [label for threadId, label in uniqueThreadLabels((
			("1", "Repeated title"), ("2", "Repeated title"), ("3", "Repeated title (2)"),
		))]
		self.assertEqual(len(labels), len(set(labels)))

	def test_every_click_tier_has_the_complete_valid_sound_inventory(self):
		sounds = CORE_PATH.parent / "sounds"
		expected = set(core.TONE_PATTERNS)
		for level in ("soft", "normal", "loud"):
			paths = sorted((sounds / level).glob("*.wav"))
			self.assertEqual(expected, {path.stem for path in paths}, level)
			for path in paths:
				with wave.open(str(path), "rb") as audio:
					self.assertEqual(1, audio.getnchannels(), path)
					self.assertEqual(2, audio.getsampwidth(), path)
					self.assertEqual(44100, audio.getframerate(), path)
					self.assertGreater(audio.getnframes(), 0, path)

	def test_click_designs_use_distinct_patterns_and_percussive_characters(self):
		tree = ast.parse(CLICK_GENERATOR_PATH.read_text(encoding="utf-8"))
		patterns = ast.literal_eval(next(
			node.value for node in tree.body
			if isinstance(node, ast.Assign) and any(
				isinstance(target, ast.Name) and target.id == "PATTERNS" for target in node.targets
			)
		))
		self.assertEqual(17, len(patterns))
		self.assertEqual(17, len({tuple(pattern) for pattern in patterns.values()}))
		characters = {character for pattern in patterns.values() for offset, frequency, character in pattern}
		self.assertGreaterEqual(len(characters), 6)
		self.assertNotEqual(patterns["command"], patterns["file"])
		self.assertNotEqual(patterns["completion"], patterns["failure"])

	def test_click_volume_levels_are_clearly_separated(self):
		sounds = CORE_PATH.parent / "sounds"
		for soundPath in sorted((sounds / "normal").glob("*.wav")):
			levels = []
			for level in ("soft", "normal", "loud"):
				with wave.open(str(sounds / level / soundPath.name), "rb") as audio:
					raw = audio.readframes(audio.getnframes())
				samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
				levels.append(math.sqrt(sum(sample * sample for sample in samples) / len(samples)))
			with self.subTest(sound=soundPath.name):
				self.assertLess(levels[0], levels[1] * 0.45)
				self.assertLess(levels[1], levels[2] * 0.65)

	def test_preview_selection_returns_only_requested_item(self):
		items = (("thinking", "Thinking"), ("command", "Running command"))
		self.assertEqual(items[1], previewSelection(items, 1))
		self.assertEqual(items[0], previewSelection(items, -1))
		self.assertEqual(items[0], previewSelection(items, 99))
		self.assertIsNone(previewSelection((), 0))

	def test_custom_announcement_placeholders_and_safe_fallbacks(self):
		self.assertEqual(
			"Still running Build after 12 seconds: Running tests",
			formatCustomAnnouncement(
				"Still running {activity} after {seconds} seconds: {message}",
				"Running tests", "Build", 12,
			),
		)
		self.assertEqual("Running tests", formatCustomAnnouncement("", "Running tests"))
		self.assertEqual("Keep {unknown}", formatCustomAnnouncement("Keep {unknown}", "Running tests"))
		self.assertEqual("Keep {message.missing}", formatCustomAnnouncement("Keep {message.missing}", "Running tests"))
		self.assertEqual(
			"File operations still running for 1 minute 25 seconds",
			formatCustomAnnouncement("{activity} still running for {duration}", "Working", "File operations", 85),
		)

	def test_bounded_announcement_history_and_navigation(self):
		history = AnnouncementHistory(3)
		self.assertFalse(history.add(""))
		self.assertTrue(history.add("one"))
		self.assertFalse(history.add("one"))
		history.add("two")
		history.add("three")
		history.add("four")
		self.assertEqual(("two", "three", "four"), history.items())
		self.assertEqual("three", history.move(-1))
		self.assertEqual("two", history.move(-20))
		self.assertEqual("four", history.move(20))
		history.clear()
		self.assertEqual(0, len(history))
		self.assertEqual("", history.move(-1))

	def test_chat_message_shortcuts_and_accessibility_token_extraction(self):
		self.assertEqual(tuple(range(1, 11)), tuple(
			chatMessageShortcutIndex(key) for key in "1234567890"
		))
		self.assertIsNone(chatMessageShortcutIndex("numpad1"))
		self.assertIsNone(chatMessageShortcutIndex(""))
		tokens = [
			("text", "sidebar title"),
			("speaker", "user"), ("speaker", "user"), ("text", " First question "),
			("text", "with a second line"),
			("speaker", "assistant"), ("text", "Response complete"), ("text", "First answer"),
			("speaker", "assistant"), ("text", "First answer"),
			("speaker", "user"), ("text", "Second question"), ("end", "prompt"),
			("text", "Do anything"),
		]
		self.assertEqual(
			(("user", "First question with a second line"), ("assistant", "First answer"), ("user", "Second question")),
			chatMessagesFromTokens(tokens),
		)


	def test_chat_message_extraction_is_bounded_and_tolerates_bad_tokens(self):
		tokens = []
		for index in range(12):
			tokens.extend((
				("speaker", "user" if index % 2 == 0 else "assistant"),
				("text", f"message {index}"),
			))
		tokens.extend((None, ("bad",), ("speaker", "unknown")))
		messages = chatMessagesFromTokens(tokens, 10)
		self.assertEqual(10, len(messages))
		self.assertEqual(("user", "message 2"), messages[0])
		self.assertEqual(("assistant", "message 11"), messages[-1])

	def test_chat_message_extraction_removes_trailing_claude_interface_text(self):
		for text in (
			"3:07 PM", "Today 3:19 PM", "13:45", "Working for 17s", "Working for 4m 4s",
			"Edited 7 files", "Good response", "Bad response", "Change permissions",
			"Review changed files", "Copy message", "Thinking", "Step 1 / 5",
			"Add files and more", "Full access",
		):
			self.assertTrue(isChatMessageTrailingUiText(text), text)
		for text in ("Meet at 3:07 PM tomorrow", "I edited 7 files", "This is a good response"):
			self.assertFalse(isChatMessageTrailingUiText(text), text)
		tokens = (
			("speaker", "assistant"), ("text", "Actual answer"), ("text", "Edited 7 files"),
			("text", "+21 -20"), ("text", "Good response"), ("text", "3:02 PM"),
			("speaker", "user"), ("text", "Actual question"), ("text", "3:07 PM"),
			("text", "Working for 17s"),
			("speaker", "assistant"), ("text", "Latest answer"), ("text", "Change permissions"),
		)
		self.assertEqual(
			(("assistant", "Actual answer"), ("user", "Actual question"), ("assistant", "Latest answer")),
			chatMessagesFromTokens(tokens),
		)

	def test_chat_message_extraction_skips_hidden_response_copy_and_preserves_split_words(self):
		tokens = (
			("speaker", "user"), ("text", "L"), ("text", "ooks like this works. "),
			("speaker", "assistant"),
			("text", "Response complete: Real answer. Real answer. Thinking Step 1 / 5"),
			("text", "Real answer. "), ("text", "Second paragraph."),
			("text", "Thinking"), ("text", "Step 1 / 5"),
		)
		self.assertEqual(
			(("user", "Looks like this works."), ("assistant", "Real answer. Second paragraph.")),
			chatMessagesFromTokens(tokens),
		)

	def test_changelog_is_clean_for_accessible_display(self):
		markdown = "# Changelog\n\nAll notable changes.\n\n## 2.2.0\n\n### What to test\n\n- Added **history**.\n- Uses `clicks`."
		self.assertEqual(
			"Complete release history\n\nAll notable changes.\n\nVersion 2.2.0\n\nWhat to test\n\nAdded history.\nUses clicks.",
			changelogForDisplay(markdown),
		)

	def test_release_notes_viewer_title_guard(self):
		self.assertTrue(viewerTitleMatches("Code — current release notes", "Code — current release notes"))
		self.assertTrue(viewerTitleMatches("Code — current release notes", "Code — CURRENT RELEASE NOTES dialog"))
		self.assertFalse(viewerTitleMatches("Code — current release notes", "NVDA Settings"))
		self.assertFalse(viewerTitleMatches("Code — current release notes", "Unrelated Code — current release notes"))
		self.assertFalse(viewerTitleMatches("", "NVDA Settings"))

	def test_output_actions_with_all_channels_available(self):
		self.assertEqual(
			{"speech": True, "braille": True, "tone": True},
			outputActions(True, False, True, True, "command"),
		)

	def test_output_actions_can_disable_tones_while_speech_is_available(self):
		self.assertEqual(
			{"speech": True, "braille": True, "tone": False},
			outputActions(True, False, True, False, "command"),
		)

	def test_output_actions_when_addon_speech_is_disabled(self):
		self.assertEqual(
			{"speech": False, "braille": True, "tone": True},
			outputActions(False, False, True, True, "command"),
		)

	def test_output_actions_when_nvda_speech_mode_is_off(self):
		self.assertEqual(
			{"speech": False, "braille": True, "tone": True},
			outputActions(True, True, True, True, "command"),
		)

	def test_output_actions_respect_disabled_fallback(self):
		self.assertEqual(
			{"speech": False, "braille": False, "tone": False},
			outputActions(True, True, False, False, "command"),
		)

	def test_output_actions_require_a_tone_category(self):
		self.assertFalse(outputActions(False, False, True, True, None)["tone"])

	def test_tone_patterns_are_short_and_category_specific(self):
		self.assertNotEqual(tonePattern("command"), tonePattern("search"))
		self.assertLessEqual(sum(duration for frequency, duration in tonePattern("completion")), 250)
		self.assertEqual(((392, 35), (523, 55)), tonePattern("backgroundPulse1"))
		self.assertNotEqual(tonePattern("backgroundPulse1"), tonePattern("backgroundPulse2"))

	def test_failure_uses_descending_tone_pattern(self):
		pattern = tonePattern("completion", "Command failed with exit code 1")
		frequencies = [frequency for frequency, duration in pattern]
		self.assertEqual(frequencies, sorted(frequencies, reverse=True))
		self.assertNotEqual(pattern, tonePattern("completion", "Command finished"))
		self.assertEqual("failure", soundKey("completion", "Command failed"))
		self.assertEqual("completion", soundKey("completion", "Command finished"))
		self.assertEqual("other", soundKey("unknown"))

	def test_final_commentary_cannot_restart_completed_task(self):
		self.assertTrue(nextBusyState(False, "command"))
		self.assertFalse(nextBusyState(True, "completion"))
		self.assertFalse(nextBusyState(False, commentary=True))
		self.assertTrue(nextBusyState(True, commentary=True))

	def test_active_polling_uses_lower_cost_fallback(self):
		self.assertEqual(500, pollDelay(True, 500))
		self.assertEqual(1000, pollDelay(False, 750))
		self.assertEqual(2000, pollDelay(False, 2000))

	def test_full_buffer_inspection_is_event_driven_and_typing_safe(self):
		# Dirty events are retained, but no whole-document read may interrupt typing.
		self.assertFalse(bufferInspectionDue(True, 0, False, False, True))
		self.assertTrue(bufferInspectionDue(True, 0, False, False, False))
		# A running task keeps a bounded fallback without scanning twice per second.
		self.assertFalse(bufferInspectionDue(False, 4.9, True, False, False))
		self.assertTrue(bufferInspectionDue(False, 5.0, True, False, False))
		# Prompt typing also suppresses fallback scans.
		self.assertFalse(bufferInspectionDue(False, 100, True, True, True))
		# Idle Claude is event-only whether focused or in the background.
		self.assertFalse(bufferInspectionDue(False, 1000, False, False, False))
		self.assertFalse(bufferInspectionDue(False, 1000, False, True, False))
		self.assertFalse(bufferInspectionDue(False, float("nan"), True, True, False))

	def test_closed_conversation_window_requires_a_confirmed_grace_period(self):
		self.assertFalse(conversationWindowShouldDetach(False, False, False, 10, 2))
		self.assertFalse(conversationWindowShouldDetach(True, None, None, 10, 2))
		self.assertFalse(conversationWindowShouldDetach(True, True, True, 10, 2))
		self.assertFalse(conversationWindowShouldDetach(True, False, False, 1.99, 2))
		self.assertTrue(conversationWindowShouldDetach(True, False, False, 2, 2))
		self.assertTrue(conversationWindowShouldDetach(True, True, False, 2, 2))
		self.assertFalse(conversationWindowShouldDetach(True, False, False, float("nan"), 2))



	def test_braille_display_chords_activate_typing_protection(self):
		self.assertTrue(isBrailleTypingGestureIdentifier("br(hims.BrailleSense):dot4+dot2"))
		self.assertTrue(isBrailleTypingGestureIdentifier("br(hims.BrailleSense):space"))
		self.assertTrue(isBrailleTypingGestureIdentifier("br(hims.BrailleSense):dot7"))
		self.assertFalse(isBrailleTypingGestureIdentifier("br(hims.BrailleSense):rightSideScrollDown"))
		self.assertFalse(isBrailleTypingGestureIdentifier("kb(laptop):a"))
		self.assertFalse(brailleTypingGestureCommitsText("br(hims.BrailleSense):dot4+dot2"))
		self.assertTrue(brailleTypingGestureCommitsText("br(hims.BrailleSense):space"))
		self.assertTrue(brailleTypingGestureCommitsText("br(hims.BrailleSense):dot8+dot3+space"))

	def test_delayed_caret_event_preserves_only_an_active_braille_composition(self):
		self.assertTrue(shouldPreserveBrailleComposition(True, True, True, 0.6))
		self.assertTrue(shouldPreserveBrailleComposition(True, True, True, 1.0))
		self.assertFalse(shouldPreserveBrailleComposition(True, True, True, 1.01))
		self.assertFalse(shouldPreserveBrailleComposition(False, True, True, 0.1))
		self.assertFalse(shouldPreserveBrailleComposition(True, False, True, 0.1))
		self.assertFalse(shouldPreserveBrailleComposition(True, True, False, 0.1))
		self.assertFalse(shouldPreserveBrailleComposition(True, True, True, float("nan")))


	def test_event_triggered_scans_are_coalesced_away_from_the_last_poll(self):
		self.assertEqual(150, coalescedPollDelay(10, 0.0))
		self.assertEqual(100, coalescedPollDelay(10, 0.05))
		self.assertEqual(10, coalescedPollDelay(10, 0.20))
		self.assertEqual(250, coalescedPollDelay(250, 0.0))
		self.assertEqual(10, coalescedPollDelay(10, float("inf")))
		self.assertEqual(150, coalescedPollDelay(10, float("-inf")))
		self.assertEqual(150, coalescedPollDelay(10, float("nan")))
		self.assertEqual(150, coalescedPollDelay(10, -1.0))
		self.assertEqual(150, coalescedPollDelay("bad", None))
		self.assertEqual(10, coalescedPollDelay(10, 0.20, float("inf")))
		self.assertFalse(shouldReplaceScheduledPoll(10.1, 10.2))
		self.assertTrue(shouldReplaceScheduledPoll(10.2, 10.1))
		self.assertTrue(shouldReplaceScheduledPoll(0.0, 10.1))



	def test_continuous_working_sound_uses_quiet_gaps_for_clicks_and_tones(self):
		self.assertTrue(shouldPlayContinuousWorkingClick(True, True, "clicks", True, 1.4, 1.4))
		self.assertTrue(shouldPlayContinuousWorkingClick(True, True, "tones", True, 1.4, 1.4))
		self.assertFalse(shouldPlayContinuousWorkingClick(False, True, "clicks", True, 10, 1.4))
		self.assertFalse(shouldPlayContinuousWorkingClick(True, False, "clicks", True, 10, 1.4))
		self.assertFalse(shouldPlayContinuousWorkingClick(True, True, "invalid", True, 10, 1.4))
		self.assertFalse(shouldPlayContinuousWorkingClick(True, True, "clicks", False, 10, 1.4))
		self.assertFalse(shouldPlayContinuousWorkingClick(True, True, "clicks", True, 1.39, 1.4))

	def test_focus_state_clicks_only_on_transitions(self):
		state, cue = focusStateTransition(None, False)
		self.assertEqual((False, ""), (state, cue))
		state, cue = focusStateTransition(state, True)
		self.assertEqual((True, "active"), (state, cue))
		state, cue = focusStateTransition(state, True)
		self.assertEqual((True, ""), (state, cue))
		state, cue = focusStateTransition(state, False)
		self.assertEqual((False, "inactive"), (state, cue))

	def test_prompt_submission_detects_populated_to_empty_transition(self):
		state, submitted = promptSubmissionTransition(None, False)
		self.assertEqual((False, False), (state, submitted))
		state, submitted = promptSubmissionTransition(state, True)
		self.assertEqual((True, False), (state, submitted))
		state, submitted = promptSubmissionTransition(state, True)
		self.assertEqual((True, False), (state, submitted))
		state, submitted = promptSubmissionTransition(state, False)
		self.assertEqual((False, True), (state, submitted))
		state, submitted = promptSubmissionTransition(state, False)
		self.assertEqual((False, False), (state, submitted))

	def test_prompt_submission_gesture_recognizes_only_unmodified_enter(self):
		for identifier in (
			"kb(laptop):enter", "kb(desktop):enter", "kb:enter",
			"kb(desktop):numpadEnter", "br(hims.BrailleSense):dot8",
		):
			self.assertTrue(isPromptSubmissionGestureIdentifier(identifier), identifier)
		for identifier in (
			"kb(laptop):shift+enter", "kb(laptop):control+enter",
			"br(hims.BrailleSense):dot7+dot8", "br(hims.BrailleSense):space",
			"kb(laptop):a", "enter", "",
		):
			self.assertFalse(isPromptSubmissionGestureIdentifier(identifier), identifier)

	def test_prompt_submission_gesture_requires_focus_mode_and_prompt_text_evidence(self):
		self.assertFalse(promptSubmissionGestureShouldStart(False, True, True))
		self.assertFalse(promptSubmissionGestureShouldStart(True, False, False))
		self.assertFalse(promptSubmissionGestureShouldStart(True, None, False))
		self.assertTrue(promptSubmissionGestureShouldStart(True, True, False))
		self.assertTrue(promptSubmissionGestureShouldStart(True, False, True))




	def test_prompt_labels_are_narrow_and_do_not_require_a_document_name(self):
		for label in ("Reply to Claude", "Ask Claude", "Message Claude", "Send a message", "Reply to Claude…"):
			self.assertTrue(isCodePromptLabel(label), label)
		for label in ("Search chats", "Announcement text", "Change permissions", ""):
			self.assertFalse(isCodePromptLabel(label), label)

	def test_user_message_number_and_submission_transition(self):
		self.assertEqual(80, userMessageNumber("Jump to user message 80"))
		self.assertIsNone(userMessageNumber("Jump to latest message"))
		state, submitted = userMessageSubmissionTransition(None, 79)
		self.assertEqual((79, False), (state, submitted))
		state, submitted = userMessageSubmissionTransition(state, 80)
		self.assertEqual((80, True), (state, submitted))
		state, submitted = userMessageSubmissionTransition(state, 80)
		self.assertEqual((80, False), (state, submitted))
		state, submitted = userMessageSubmissionTransition(state, None)
		self.assertEqual((80, False), (state, submitted))

	def test_user_message_increase_requires_active_stop_control(self):
		pending, confirmed = confirmedUserMessageSubmission(False, True, False)
		self.assertEqual((True, False), (pending, confirmed))
		pending, confirmed = confirmedUserMessageSubmission(pending, False, True)
		self.assertEqual((False, True), (pending, confirmed))
		self.assertEqual((False, False), confirmedUserMessageSubmission(False, False, True))

	def test_current_navigation_buttons_are_not_diagnostic_noise(self):
		for label in (
			"Review", "Review changed files", "Undo", "Open chat", "Edit message",
			"Worked for 2m 58s", "Worked for 27s",
			"Download Code Status Announcer 2026.2.1",
		):
			self.assertTrue(isKnownNonStatusButton(label), label)

	def test_stop_control_and_duplicate_event_safeguards(self):
		self.assertTrue(isStopControlLabel("Stop generating"))
		self.assertTrue(isStopControlLabel("Cancel task"))
		self.assertFalse(isStopControlLabel("Send message"))
		state, stopped = stopControlTransition(False, True)
		self.assertEqual((True, False), (state, stopped))
		state, stopped = stopControlTransition(state, False)
		self.assertEqual((False, True), (state, stopped))
		self.assertTrue(shouldSuppressDuplicate("Working", "Working", 1.49))
		self.assertFalse(shouldSuppressDuplicate("Working", "Working", 1.5))
		self.assertFalse(shouldSuppressDuplicate("Thinking", "Working", 0.1))
		self.assertTrue(shouldLogDiagnosticSnapshot(("Copy",), (), 0))
		self.assertTrue(shouldLogDiagnosticSnapshot(("Retry",), ("Copy",), 1))
		self.assertFalse(shouldLogDiagnosticSnapshot(("Copy",), ("Copy",), 29.9))
		self.assertTrue(shouldLogDiagnosticSnapshot(("Copy",), ("Copy",), 30))
		self.assertFalse(shouldLogDiagnosticSnapshot((), ("Copy",), 30))

	def test_response_completion_marker_requires_baseline_and_busy_state(self):
		marker, initialized, completed = responseCompletionTransition(None, False, 100, False)
		self.assertEqual((100, True, False), (marker, initialized, completed))
		marker, initialized, completed = responseCompletionTransition(marker, initialized, 100, True)
		self.assertEqual((100, True, False), (marker, initialized, completed))
		marker, initialized, completed = responseCompletionTransition(marker, initialized, 200, True)
		self.assertEqual((200, True, True), (marker, initialized, completed))
		marker, initialized, completed = responseCompletionTransition(marker, initialized, None, True)
		self.assertEqual((200, True, False), (marker, initialized, completed))
		marker, initialized, completed = responseCompletionTransition(marker, initialized, 300, False)
		self.assertEqual((300, True, False), (marker, initialized, completed))

	def test_plain_response_complete_marker_ends_a_busy_submission(self):
		self.assertTrue(isResponseCompletionMarkerText("Response complete"))
		self.assertTrue(isResponseCompletionMarkerText(" Response   complete: finished answer "))
		self.assertFalse(isResponseCompletionMarkerText("Response completing"))
		previous = responseCompletionScanMarker(12)
		current = responseCompletionScanMarker(13)
		marker, initialized, completed = responseCompletionTransition(previous, True, current, True)
		self.assertEqual((current, True, True), (marker, initialized, completed))
		self.assertIsNone(responseCompletionScanMarker(0))

	def test_tentative_response_completion_requires_a_quiet_idle_scan(self):
		self.assertTrue(shouldFinalizeResponseCompletion(True, 30, 30, True, False, ""))
		self.assertTrue(shouldFinalizeResponseCompletion(True, 5, 5, True, False, ""))
		self.assertFalse(shouldFinalizeResponseCompletion(True, 4.99, 5, True, False, ""))
		self.assertTrue(shouldFinalizeResponseCompletion(True, 30, 30, True, False, "Reading finished"))
		self.assertTrue(shouldFinalizeResponseCompletion(True, 30, 30, True, False, "Command finished"))
		self.assertFalse(shouldFinalizeResponseCompletion(True, 30, 30, True, True, ""))
		self.assertFalse(shouldFinalizeResponseCompletion(True, 30, 30, True, False, "Running command"))
		self.assertFalse(shouldFinalizeResponseCompletion(True, 30, 30, False, False, ""))
		self.assertFalse(shouldFinalizeResponseCompletion(True, 29.9, 30, True, False, ""))

	def test_trailing_intermediate_completion_preserves_response_completion_candidate(self):
		self.assertEqual(("completion", "Reading finished"), statusDetails("Reading finished"))
		for label in ("Reading finished", "Command finished", "File edit complete"):
			self.assertFalse(supersedesResponseCompletionCandidate(label), label)
		for label in ("Reading", "Working", "Thinking", "Running command"):
			self.assertTrue(supersedesResponseCompletionCandidate(label), label)

	def test_only_whole_task_labels_end_continuous_activity(self):
		for label in ("Response complete", "Finished", "Completed task", "Cancelled"):
			self.assertTrue(isTaskCompletionLabel(label), label)
		for label in ("Ran command", "File edit complete", "Compiled project", "Search finished"):
			self.assertFalse(isTaskCompletionLabel(label), label)
		self.assertEqual("command", intermediateCompletionCategory("Ran rg --files"))
		self.assertEqual("file", intermediateCompletionCategory("File edit complete"))
		self.assertEqual("build", intermediateCompletionCategory("Compiled project"))
		self.assertEqual("search", intermediateCompletionCategory("Searched the web"))


	def test_activity_messages(self):
		cases = {
			"Planning next step": "Thinking",
			"Thinking": "Thinking",
			"Working": "Working",
			"Analyzing files": "Analyzing",
			"Reading package metadata": "Checking files",
			"Writing tests": "Editing code",
			"Editing source": "Editing code",
			"Applying patch": "Applying changes",
			"Generating output": "Generating",
			"Waiting for process": "Waiting for command",
			"Using tool": "Using tool",
			"Searching the web": "Searching the web",
			"Running command Get-ChildItem": "Running command",
			"Running web search": "Searching the web",
			"Searched the web": "Web search finished",
			"Ran command": "Command finished",
			"Ran command and web search": "Command and web search finished",
			"Completed task": "Task finished",
			"Response complete: final answer": "Task finished",
			"Reviewed files": "Reading finished",
			"Updated source": "File updated",
		}
		for label, expected in cases.items():
			with self.subTest(label=label):
				self.assertEqual(expected, statusMessage(label))
		self.assertEqual(("build", "Running tests"), statusDetails("Running tests: 53 tests"))
		self.assertEqual(("build", "Generating"), statusDetails("Running build"))
		self.assertEqual(("tool", "Using tool"), statusDetails("Running tool: apply_patch"))

	def test_attention_messages(self):
		self.assertEqual(("attention", "Permission required"), statusDetails("Permission required to continue"))
		self.assertEqual(("attention", "User input required"), statusDetails("Waiting for your input"))
		self.assertFalse(nextBusyState(True, "attention"))
		self.assertEqual("urgent", announcementPriority("attention", "Permission required"))

	def test_first_status_label_falls_back_to_accessible_name(self):
		self.assertEqual("Planning", firstStatusLabel("", " Planning  "))

	def test_first_status_label_rejects_ordinary_button(self):
		self.assertEqual("", firstStatusLabel("Copy", "Retry"))

	def test_compilation_and_file_edit_messages(self):
		self.assertEqual("Compiling", statusMessage("Compiling project"))
		self.assertEqual("Compilation finished", statusMessage("Compiled project"))
		self.assertEqual("Editing code", statusMessage("File edit source.py"))
		self.assertEqual("File updated", statusMessage("File edit complete source.py"))

	def test_full_mode_returns_complete_normalized_label(self):
		self.assertEqual(
			"Running shell command: python -m unittest",
			statusMessage("  Running   shell command: python -m unittest  ", verbosity="full"),
		)

	def test_full_speech_profiles_offer_standard_developer_and_raw_detail(self):
		label = "  Running   shell command: python -m unittest discover -s tests  "
		self.assertEqual("Running command: python", statusMessage(label, verbosity="full", fullProfile="standard"))
		self.assertEqual(
			"Running shell command: python -m unittest discover -s tests",
			statusMessage(label, verbosity="full", fullProfile="developer"),
		)
		self.assertEqual(
			"Running   shell command: python -m unittest discover -s tests",
			statusMessage(label, verbosity="full", fullProfile="raw"),
		)
		self.assertEqual(
			"Command finished: rg",
			statusMessage("Ran rg -n pattern source", verbosity="full", fullProfile="standard"),
		)

	def test_standard_full_profile_keeps_file_counts_and_useful_timing(self):
		self.assertEqual(
			"Running tests: 43 tests, 12 seconds",
			statusMessage("Testing project: 43 tests for 12 seconds", verbosity="full", fullProfile="standard"),
		)

	def test_minimal_speech_profiles_are_essential_balanced_and_informative(self):
		self.assertEqual("", statusMessage("Editing C:\\project\\core.py", minimalProfile="essential"))
		self.assertEqual("Thinking", statusMessage("Thinking", minimalProfile="essential"))
		self.assertEqual("Task finished", statusMessage("Response complete", minimalProfile="essential"))
		self.assertEqual("Checking files", statusMessage("Inspecting source", minimalProfile="balanced"))
		self.assertEqual("Editing code", statusMessage("Editing C:\\project\\core.py", minimalProfile="balanced"))
		self.assertEqual(
			"Editing code: core.py",
			statusMessage("Editing C:\\project\\core.py", minimalProfile="informative"),
		)
		self.assertEqual(
			"Running tests: 43 tests, 12 seconds",
			statusMessage("Testing project: 43 tests for 12 seconds", minimalProfile="informative"),
		)

	def test_minimal_results_distinguish_success_failure_and_file_updates(self):
		self.assertEqual("Tests passed", statusMessage("Tests passed: 43 tests", minimalProfile="balanced"))
		self.assertEqual("Tests failed", statusMessage("Tests failed: 1 failure", minimalProfile="balanced"))
		self.assertEqual("File updated", statusMessage("Updated core.py", minimalProfile="balanced"))
		self.assertEqual("Waiting for command", statusMessage("Waiting for command", minimalProfile="balanced"))
		self.assertEqual(
			"Editing: core.py",
			statusMessage("Editing C:\\project\\core.py", verbosity="full", fullProfile="standard"),
		)

	def test_categories(self):
		self.assertEqual(("command", "Running command"), statusDetails("Executing shell command: dir"))
		self.assertEqual(("build", "Running tests"), statusDetails("Testing project"))
		self.assertEqual(("completion", "Command failed"), statusDetails("Command failed with exit code 1"))
		self.assertEqual(("completion", "Command finished"), statusDetails("Ran rg -n pattern source"))

	def test_full_mode_speaks_complete_ran_label(self):
		label = "Ran rg -n pattern source -g '*.py'"
		self.assertEqual(label, statusMessage(label, verbosity="full"))
		self.assertEqual("Command finished", statusMessage(label))

	def test_sensitive_redaction(self):
		text = redactSensitive("Running token=abc123 remote key=mySecret C:\\Users\\alice\\project https://example.com/?key=value")
		self.assertNotIn("abc123", text)
		self.assertNotIn("alice", text)
		self.assertNotIn("key=value", text)
		self.assertNotIn("mySecret", text)
		quoted = redactSensitive('password="two word secret" C:\\Users\\Jane Doe\\project')
		self.assertNotIn("two word secret", quoted)
		self.assertNotIn("Jane Doe", quoted)
		commandLine = redactSensitive("Running command: tool --token abc123 --password 'two words'")
		self.assertNotIn("abc123", commandLine)
		self.assertNotIn("two words", commandLine)

	def test_category_output_routing_respects_master_switches(self):
		self.assertEqual(
			{"speech": True, "braille": True, "sound": True},
			categoryOutputActions("all", True, True, True),
		)
		self.assertEqual(
			{"speech": False, "braille": False, "sound": True},
			categoryOutputActions("sound", True, True, True),
		)
		self.assertEqual(
			{"speech": False, "braille": False, "sound": False},
			categoryOutputActions("speech", False, True, True),
		)

	def test_braille_reading_protection_only_suppresses_focused_routine_progress(self):
		for category in (
			"thinking", "working", "command", "search", "file", "build", "tool", "commentary",
			"backgroundPulse1", "backgroundPulse2",
		):
			self.assertTrue(shouldSuppressRoutineBraille(True, True, category, "normal"), category)
		self.assertFalse(shouldSuppressRoutineBraille(True, False, "command", "normal"))
		self.assertFalse(shouldSuppressRoutineBraille(False, True, "command", "normal"))
		self.assertFalse(shouldSuppressRoutineBraille(True, True, "command", "high"))
		self.assertFalse(shouldSuppressRoutineBraille(True, True, "completion", "high"))
		self.assertTrue(shouldSuppressRoutineBraille(True, True, "completion", "high", True))
		self.assertFalse(shouldSuppressRoutineBraille(True, True, "completion", "urgent", True))
		self.assertFalse(shouldSuppressRoutineBraille(True, True, "attention", "urgent"))
		self.assertFalse(shouldSuppressRoutineBraille(True, True, "other", "normal"))
		self.assertEqual(
			{"speech": False, "braille": False, "sound": False},
			categoryOutputActions("off", True, True, True),
		)

	def test_conversation_reading_protection_suppresses_only_browse_mode_response_updates(self):
		self.assertTrue(shouldSuppressNativeConversationUpdate(
			True, True, True, True, False, "Response: streamed assistant text",
		))
		self.assertTrue(shouldSuppressNativeConversationUpdate(
			True, True, True, True, False, "Response complete: finished text",
		))
		self.assertTrue(shouldSuppressNativeConversationUpdate(
			True, True, True, True, False, "Response complete",
		))
		self.assertTrue(shouldSuppressNativeConversationUpdate(
			True, True, True, True, False, "Claude said: streamed assistant text",
		))
		for arguments in (
			(False, True, True, True, False, "Response: text"),
			(True, False, True, True, False, "Response: text"),
			(True, True, False, True, False, "Response: text"),
			(True, True, True, False, False, "Response: text"),
			(True, True, True, True, True, "Response: text"),
			(True, True, True, True, False, "Permission required: Allow or deny"),
			(True, True, True, True, False, "Running command"),
			(True, True, True, True, False, ""),
		):
			self.assertFalse(shouldSuppressNativeConversationUpdate(*arguments), arguments)


	def test_announcement_priorities(self):
		self.assertEqual("urgent", announcementPriority("completion", "Command failed"))
		self.assertEqual("high", announcementPriority("completion", "Command finished"))
		self.assertEqual("low", announcementPriority("commentary", "Inspecting files"))
		self.assertEqual("normal", announcementPriority("command", "Running command"))

	def test_elapsed_seconds(self):
		self.assertEqual(25, elapsedSeconds("Working for 25s"))
		self.assertIsNone(elapsedSeconds("Working"))

	def test_streamed_commentary_waits_for_complete_sentences(self):
		message, offset = completedTextDelta("I am inspecting the source")
		self.assertEqual("", message)
		message, offset = completedTextDelta("I am inspecting the source. Next step", offset)
		self.assertEqual("I am inspecting the source.", message)
		message, offset = completedTextDelta("I am inspecting the source. Next step is testing.", offset)
		self.assertEqual("Next step is testing.", message)


if __name__ == "__main__":
	unittest.main()
