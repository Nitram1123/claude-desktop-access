"""Regressions from 2026.2.1 log review; fixtures contain no conversation data.

Read aloud and the stuck-active/confirmation-loop symptoms came from the log.
The surrounding field trees are synthetic reproductions, not captured UI trees.
"""
import ast
import re
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_claude import core, adapter, field, END, PLUGIN


def scanner():
	clock = SimpleNamespace(value=100.0)
	roles = SimpleNamespace(**{name: name for name in ("BUTTON", "LINK", "LANDMARK", "HEADING", "TAB")})
	env = {name: value for name, value in vars(core).items() if not name.startswith("__")}
	env.update({
		"re": re, "Role": roles, "State": SimpleNamespace(SELECTED="selected"),
		"modeFromTab": adapter.modeFromTab, "time": SimpleNamespace(monotonic=lambda: clock.value),
		"_": lambda text: text, "_settings": lambda: {"diagnosticLogging": False},
		"log": SimpleNamespace(info=lambda *a, **k: None, debug=lambda *a, **k: None),
		"CHAT_HISTORY_MODE_SETTLE_SECONDS": .75,
		"CHAT_HISTORY_SNAPSHOT_CONFIRM_SECONDS": .25,
		"CHAT_HISTORY_RETRY_MILLISECONDS": 300,
	})
	tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
	names = {"_latestButtonStatus", "_cacheChatHistoryScan", "_modeSpecificRecentChatTitles", "_queueResponseCompletion"}
	nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
	exec(compile(ast.Module(body=nodes, type_ignores=[]), "plugin scanner", "exec"), env)
	Harness = type("Harness", (), {name: env[name] for name in names})
	h = Harness()
	h._conversationMode = "claude"
	h._conversationModeChangedAt = 1.0
	h._busy = False
	h._stopControlVisible = False
	h._pendingResponseCompletionAt = 0.0
	h._promptHadText = False
	h._latestUserMessageNumber = None
	h._pendingUserMessageIncrease = False
	h._latestResponseMarker = None
	h._responseMarkerInitialized = False
	h._lastDeferredHistoryLog = ()
	h._lastDeferredHistoryLogAt = 0.0
	h._recentClassificationSummaries = {}
	for name, value in (("_chatHistoryMoreAvailable", False), ("_recentHistoryShowMoreOrdinals", 0), ("_unifiedRecentCounts", 0), ("_chatHistoryScanGenerations", 0), ("_chatHistoryCaches", ()), ("_chatHistoryCacheCurrent", False), ("_pendingChatHistorySnapshots", None), ("_pendingChatHistorySnapshotAt", 0.0), ("_archivedChatHistoryCaches", ()), ("_archivedChatHistoryLoaded", False)):
		setattr(h, name, dict.fromkeys(("claude", "code", "cowork"), value))
	h.scheduled = []
	h._schedulePoll = lambda **kwargs: h.scheduled.append(kwargs)
	def begin(reason):
		h._busy = True
	h._beginPromptSubmission = begin
	h._setConversationMode = lambda *args, **kwargs: None
	h.scan = lambda fields: h._latestButtonStatus(SimpleNamespace(getTextWithFields=lambda: fields))
	return h, clock


class LogRegressions(unittest.TestCase):
	def test_read_aloud_is_not_a_completed_read_operation(self):
		self.assertEqual(("", ""), core.statusDetails("Read aloud"))
		self.assertEqual("", core.firstStatusLabel("Read aloud"))
		h, _ = scanner()
		self.assertEqual("", h.scan([field("BUTTON", "Read aloud"), END]))

	def test_real_completed_read_operation_remains_recognized(self):
		self.assertEqual(("completion", "Reading finished"), core.statusDetails("Read report.txt"))
		self.assertEqual(("completion", "Reading finished"), core.statusDetails("Reading finished"))

	def test_link_titles_do_not_become_activity_or_stop_signals(self):
		h, _ = scanner()
		self.assertEqual("", h.scan([field("LINK", "Reading notes"), END, field("LINK", "Stop"), END]))
		self.assertFalse(h._busy)

	def test_sidebar_button_title_does_not_become_activity(self):
		h, _ = scanner()
		self.assertEqual("", h.scan(["Recents", field("BUTTON", "Running a marathon"), END]))

	def test_main_landmark_ends_history_even_on_a_generic_section_role(self):
		h, _ = scanner()
		fields = ["Recents", field("BUTTON", "Example chat"), END,
			field("SECTION", "", landmark="main"), field("BUTTON", "Running tests"), END, END]
		self.assertEqual("Running tests", h.scan(fields))
		self.assertEqual(("Example chat",), h._pendingChatHistorySnapshots["claude"])

	def test_stop_disappearance_with_completed_tool_queues_completion(self):
		h, clock = scanner()
		h.scan([field("BUTTON", "Stop response"), END])
		self.assertTrue(h._busy)
		label = h.scan([field("BUTTON", "Reading finished"), END])
		self.assertGreater(h._pendingResponseCompletionAt, 0.0)
		self.assertTrue(core.shouldFinalizeResponseCompletion(h._pendingResponseCompletionAt, 5.1, 5, h._busy, h._stopControlVisible, label))

	def test_resumed_generation_restarts_the_settling_delay(self):
		h, clock = scanner()
		h.scan([field("BUTTON", "Stop response"), END])
		h.scan([])
		first = h._pendingResponseCompletionAt
		self.assertGreater(first, 0)
		clock.value += 4
		h.scan([field("BUTTON", "Stop response"), END])
		self.assertEqual(0.0, h._pendingResponseCompletionAt)
		clock.value += 2
		h.scan([])
		self.assertGreater(h._pendingResponseCompletionAt, first)

	def test_active_tool_after_stop_disappears_blocks_finalization(self):
		h, _ = scanner()
		h.scan([field("BUTTON", "Stop response"), END])
		label = h.scan([field("BUTTON", "Running tests"), END])
		self.assertFalse(core.shouldFinalizeResponseCompletion(h._pendingResponseCompletionAt, 9, 5, h._busy, h._stopControlVisible, label))

	def test_unchanged_history_does_not_keep_scheduling_confirmation(self):
		h, clock = scanner()
		fields = ["Recents", field("LINK", "Example chat"), END]
		h.scan(fields)
		self.assertEqual(1, len(h.scheduled))
		clock.value += .4
		h.scan(fields)
		self.assertEqual(("Example chat",), h._chatHistoryCaches["claude"])
		h.scheduled.clear()
		for i in range(5):
			clock.value += 5
			h.scan(fields)
		self.assertEqual([], h.scheduled)
		self.assertIsNone(h._pendingChatHistorySnapshots["claude"])

	def test_changed_history_still_requires_confirmation(self):
		h, clock = scanner()
		old = ["Recents", field("LINK", "First chat"), END]
		new = ["Recents", field("LINK", "Second chat"), END]
		h.scan(old)
		clock.value += .4
		h.scan(old)
		h.scan(new)
		self.assertEqual(("First chat",), h._chatHistoryCaches["claude"])
		clock.value += .4
		h.scan(new)
		self.assertEqual(("Second chat",), h._chatHistoryCaches["claude"])
