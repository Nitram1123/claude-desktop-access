"""Synthetic Claude contracts and executable integration tests (not live UI tests)."""
import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
import time

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "globalPlugins/claudeDesktopAccess"


def load(name):
	spec = importlib.util.spec_from_file_location(name, PLUGIN / (name + ".py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


adapter, core = load("claudeAdapter"), load("core")


def field(role, name="", **attrs):
	return SimpleNamespace(command="controlStart", field={"role": role, "name": name, **attrs})


END = SimpleNamespace(command="controlEnd", field={})


def node(role, name, *children, classes="", aria="", props="", accelerator="", **attrs):
	obj = SimpleNamespace(role=role, name=name, firstChild=children[0] if children else None,
		lastChild=children[-1] if children else None,
		UIAElement=SimpleNamespace(currentClassName=classes, currentAriaRole=aria,
			currentAriaProperties=props, currentAcceleratorKey=accelerator), **attrs)
	for child in children:
		child.parent = obj
	for previous, following in zip(children, children[1:]):
		previous.next, following.previous = following, previous
	return obj


class ClaudeContracts(unittest.TestCase):
	def test_code_document_uses_native_url_without_its_title(self):
		for name in ("", "Beliebiger Titel", "セッション"):
			self.assertTrue(adapter.isCodeDocument(node("document", name, value="https://claude.ai/epitaxy/session")))
		for value in ("https://other.test/epitaxy/", "https://claude.ai/epitaxy-other", "https://claude.ai/settings"):
			self.assertFalse(adapter.isCodeDocument(node("document", "Claude Code", value=value)))


	def test_native_task_progress_requires_a_unique_timer_inside_the_feed(self):
		def feed(busy=None):
			attributes = {"IAccessible2::attribute_xml-roles": "feed"}
			if busy is not None:
				attributes["IAccessible2::attribute_busy"] = busy
			return field("SECTION", "任意", **attributes)
		timer = field("GROUPING", "任意", **{"IAccessible2::attribute_xml-roles": "timer"})
		self.assertEqual((None, None), adapter.codeFeedTaskProgress([timer, "00:09", END]))
		self.assertEqual((True, None), adapter.codeFeedTaskProgress([feed("true"), "00:09", END]))
		self.assertEqual((True, 62), adapter.codeFeedTaskProgress([feed("true"), timer, "1 min", " 02 s", END, END]))
		self.assertEqual((False, 75), adapter.codeFeedTaskProgress([feed(), timer, "01:15", END, END]))
		self.assertEqual((False, None), adapter.codeFeedTaskProgress([
			field("DOCUMENT"), feed(), field("ARTICLE"), timer, "00:09", END, END,
			field("DOCUMENT"), feed("true"), timer, "00:12", END, END, END, END, END,
		]))
		self.assertEqual((True, None), adapter.codeFeedTaskProgress([feed("true"), timer, "00:09", END, timer, "00:12", END, END]))
		self.assertEqual((None, None), adapter.codeFeedTaskProgress([feed("true"), END, feed(), END]))

	def test_native_task_progress_reads_the_feed_state_without_translated_labels(self):
		timer = node("grouping", "01:04", aria="timer")
		nested = node("document", "", node("section", "09:00", aria="timer"))
		feed = node("section", "任意", timer, nested, aria="feed", props="busy=true")
		root = node("document", "", node("grouping", "", feed, classes="epitaxy-chat-panel"))
		self.assertEqual((True, 64), adapter.nativeCodeFeedTaskProgress(root))
		feed.UIAElement.currentAriaProperties = "busy=false"
		self.assertEqual((False, 64), adapter.nativeCodeFeedTaskProgress(root))
		feed.firstChild = node("statictext", "1 min 04 s")
		self.assertEqual((False, None), adapter.nativeCodeFeedTaskProgress(root))


	def test_native_timer_sounds_only_follow_advancing_values(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		names = {"_updateNativeTaskTimer", "_emitNativeProgressPulse"}
		methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
		sounds = []
		configuration = {
			"announceWorking": True, "maximumBusyMinutes": 60, "workingIntervalSeconds": 5,
			"announceHeartbeat": True, "continuousWorkingClicks": True, "workingClickStartDelayMs": 750,
			"workingClickIntervalMs": 1400, "outputWorking": "all", "speech": True, "braille": True,
			"soundWhenSpeechUnavailable": True, "progressSoundStyle": "clicks", "clickVolume": "normal",
			"protectBrailleReading": False, "verbosity": "full",
		}
		env = {
			"_settings": lambda: configuration, "_": lambda label: label,
			"CATEGORY_OUTPUT_CONFIG": {"working": "outputWorking"},
			"categoryOutputActions": core.categoryOutputActions, "formatElapsedDuration": core.formatElapsedDuration,
			"shouldSuppressRoutineBraille": core.shouldSuppressRoutineBraille,
			"backgroundActivityName": core.backgroundActivityName, "_customizeAnnouncement": lambda message, *args: message,
			"_playProgressSound": lambda category, *args: sounds.append(category),
			"_send": lambda message, speech, braille, category, sound, **kwargs: sounds.append((category, message)) or True,
		}
		exec(compile(ast.Module(body=methods, type_ignores=[]), "nativeTimer", "exec"), env)
		state = SimpleNamespace(_nativeTaskSeconds=None, _paused=False, _appFocusState=True,
			_activeCategory="working", _latestFullMessage="", _conversationBrowseModeActive=lambda: False)
		state._emitNativeProgressPulse = lambda *args: env["_emitNativeProgressPulse"](state, *args)
		for seconds in (None, 0, 0, 1, 2, 2, 4, 5, 5, None, None, 0, 2, 1, 1):
			env["_updateNativeTaskTimer"](state, seconds)
		self.assertEqual(["working", "working", ("backgroundPulse1", "Processing still running, 5 seconds"), "working"], sounds)


	def test_fallback_sounds_follow_busy_state_and_current_conversation(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_announceNativeFallbackProgress")
		sounds, requests = [], []
		conf = {
			"announceWorking": True, "maximumBusyMinutes": 60, "announceHeartbeat": True, "workingIntervalSeconds": 5,
			"continuousWorkingClicks": True, "workingClickStartDelayMs": 750, "workingClickIntervalMs": 1400,
			"outputWorking": "all", "speech": True, "braille": True, "soundWhenSpeechUnavailable": True,
			"progressSoundStyle": "clicks", "clickVolume": "normal",
		}
		env = {
			"api": SimpleNamespace(getForegroundObject=lambda: 7), "codeDocumentUrl": lambda root: root.url,
			"_settings": lambda: conf, "_": lambda value: value, "CATEGORY_OUTPUT_CONFIG": {"working": "outputWorking"},
			"categoryOutputActions": core.categoryOutputActions, "_playProgressSound": lambda category, *args: sounds.append(category),
		}
		exec(compile(ast.Module(body=[method], type_ignores=[]), "fallbackProgress", "exec"), env)
		root = SimpleNamespace(url="current")
		state = SimpleNamespace(
			_nativeTaskState=None, _nativeTaskSeconds=None, _nativeFallbackClock=None, _paused=False, _appFocusState=True,
			_conversationWindowHandle=7, _conversationWindowHandleFrom=lambda obj, buffer: obj,
			_conversationWindowIsAvailable=lambda handle: True, _buffer=SimpleNamespace(rootNVDAObject=root),
			_nativeTaskDocument="current", _nativeTaskObserver=SimpleNamespace(request=lambda: requests.append(True)),
			_estimatedNativeTaskSeconds=lambda now: int(now - 10),
			_emitNativeProgressPulse=lambda seconds, *args, estimated: sounds.append(("pulse", seconds, estimated)) or True,
		)
		state._recordNativeTaskState = lambda busy, now: setattr(state, "_nativeTaskState", busy)
		update = lambda now: env["_announceNativeFallbackProgress"](state, now)
		update(9)
		self.assertFalse(sounds)
		state._nativeTaskState = True
		update(10)
		update(10.7)
		update(11)
		update(12)
		update(12.5)
		update(15)
		self.assertEqual(["working", "working", ("pulse", 5, True)], sounds)
		state._nativeTaskState = False
		update(16)
		self.assertIsNone(state._nativeFallbackClock)
		state._nativeTaskState = True
		state._nativeTaskSeconds = 0
		update(17)
		state._nativeTaskSeconds = None
		root.url = "another"
		update(18)
		self.assertEqual([True], requests)
		self.assertIsNone(state._nativeTaskState)
		self.assertEqual(3, len(sounds))


	def test_task_timer_reports_an_estimate_only_when_the_native_value_is_missing(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		names = {"_recordNativeTaskState", "_estimatedNativeTaskSeconds", "_reportNativeTaskStatus"}
		methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
		messages = []
		clock = SimpleNamespace(now=10.0)
		env = {
			"api": SimpleNamespace(getFocusObject=lambda: object()),
			"time": SimpleNamespace(monotonic=lambda: clock.now),
			"ui": SimpleNamespace(message=messages.append),
			"formatElapsedDuration": core.formatElapsedDuration, "_": lambda value: value,
		}
		exec(compile(ast.Module(body=methods, type_ignores=[]), "taskTimerReport", "exec"), env)
		state = SimpleNamespace(_nativeTaskState=None, _nativeTaskStartedAt=None, _sample=(True, None),
			_rememberBuffer=lambda focus: object())
		state._recordNativeTaskState = lambda *args: env["_recordNativeTaskState"](state, *args)
		state._estimatedNativeTaskSeconds = lambda now: env["_estimatedNativeTaskSeconds"](state, now)
		state._readNativeTaskProgress = lambda buffer, focus: state._sample
		report = lambda: env["_reportNativeTaskStatus"](state)
		state._recordNativeTaskState(True, 10)
		state._recordNativeTaskState(True, 12)
		clock.now = 14.8
		report()
		state._sample = (True, 7)
		report()
		state._sample = (False, None)
		report()
		state._sample = (True, None)
		clock.now = 22.0
		report()
		state._sample = (None, None)
		report()
		self.assertIsNone(state._nativeTaskStartedAt)
		self.assertEqual([
			"Estimated elapsed time is 4 seconds", "7 seconds", "No active Claude task",
			"Estimated elapsed time is 0 seconds", "Claude's native task status is unavailable",
		], messages)


	def test_switching_between_busy_sessions_restarts_the_selected_timer(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		names = {"_recordNativeTaskState", "_estimatedNativeTaskSeconds", "_observeNativeTaskState"}
		methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
		clock = SimpleNamespace(now=10)
		env = {
			"api": SimpleNamespace(getFocusObject=lambda: None), "_isClaudeObject": lambda obj: False,
			"time": SimpleNamespace(monotonic=lambda: clock.now), "codeDocumentUrl": lambda root: root.url,
		}
		exec(compile(ast.Module(body=methods, type_ignores=[]), "switchTaskSession", "exec"), env)
		root = SimpleNamespace(url="alpha")
		buffer = SimpleNamespace(rootNVDAObject=root)
		state = SimpleNamespace(
			_buffer=buffer, _conversationWindowHandle=1, _nativeTaskDocument="",
			_nativeTaskState=None, _nativeTaskStartedAt=None, _nativeFallbackClock=None, _appFocusState=True,
			_conversationWindowIsAvailable=lambda handle: True,
			_readNativeTaskProgress=lambda current, focus: (True, None),
			_updateNativeTaskTimer=lambda seconds: None,
		)
		state._recordNativeTaskState = lambda *args: env["_recordNativeTaskState"](state, *args)
		observe = lambda current: env["_observeNativeTaskState"](state, current)
		elapsed = lambda: env["_estimatedNativeTaskSeconds"](state, clock.now)
		observe(buffer)
		clock.now = 23
		self.assertEqual(13, elapsed())
		root.url = "bravo"
		observe(buffer)
		self.assertEqual("bravo", state._nativeTaskDocument)
		self.assertEqual(0, elapsed())
		self.assertEqual((23, None, 23), state._nativeFallbackClock)
		clock.now = 25
		observe(SimpleNamespace(rootNVDAObject=SimpleNamespace(url="alpha")))
		self.assertEqual("bravo", state._nativeTaskDocument)
		self.assertEqual(2, elapsed())


	def test_native_task_observer_waits_for_events_and_detaches(self):
		tree = ast.parse((PLUGIN / "bufferUpdates.py").read_text(encoding="utf-8"))
		observerClass = next(n for n in tree.body if isinstance(n, ast.ClassDef))
		callbacks, samples, handled = [], [], []
		def later(delay, callback):
			callbacks.append(callback)
			return SimpleNamespace(Stop=lambda: callbacks.remove(callback))
		env = {"wx": SimpleNamespace(CallLater=later), "time": SimpleNamespace(monotonic=lambda: 10)}
		exec(compile(ast.Module(body=[observerClass], type_ignores=[]), "observer", "exec"), env)
		observer = env["BufferUpdateObserver"](samples.append)
		original = handled.append
		buffer = SimpleNamespace(_handleUpdate=original)
		observer.attach(buffer)
		callbacks.pop(0)()
		self.assertEqual([buffer], samples)
		self.assertFalse(callbacks)
		buffer._handleUpdate("first")
		buffer._handleUpdate("second")
		self.assertEqual(["first", "second"], handled)
		self.assertEqual(1, len(callbacks))
		callbacks.pop(0)()
		self.assertEqual([buffer, buffer], samples)
		self.assertFalse(callbacks)
		buffer._handleUpdate("pending")
		observer.detach()
		self.assertIs(buffer._handleUpdate, original)
		self.assertFalse(callbacks)
		observer.attach(SimpleNamespace())
		self.assertEqual(1, len(callbacks))
		observer.detach()
		self.assertFalse(callbacks)

	def scanClass(self):
		tree = ast.parse((PLUGIN / "claudeNavigator.py").read_text(encoding="utf-8"))
		node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NavigationScan")
		queue = []
		def later(delay, callback):
			queue.append(callback)
			return SimpleNamespace(Stop=lambda: queue.clear())
		env = {"wx": SimpleNamespace(CallLater=later), "time": time, "navigationKind": adapter.navigationKind, "roleName": adapter.roleName}
		exec(compile(ast.Module(body=[node], type_ignores=[]), "scan", "exec"), env)
		return env["NavigationScan"], queue

	def test_navigator_stays_in_root_and_skips_nested_documents(self):
		Scan, queue = self.scanClass()
		outside = SimpleNamespace(name="Upload file", role="BUTTON")
		nested = SimpleNamespace(name="Artifact", role="DOCUMENT", firstChild=outside)
		tab = SimpleNamespace(name="Cowork", role="TAB", next=nested)
		root = SimpleNamespace(name="Claude", role="DOCUMENT", firstChild=tab, next=outside)
		results = []
		scan = Scan(root, lambda: True, lambda items, truncated: results.append((items, truncated)))
		scan.step()
		while queue:
			queue.pop(0)()
		self.assertEqual(1, len(results))
		self.assertEqual(["Mode: Cowork"], [item[0] for item in results[0][0]])
		self.assertFalse(results[0][1])

	def test_navigator_cancels_if_user_leaves_claude(self):
		Scan, queue = self.scanClass()
		results = []
		scan = Scan(SimpleNamespace(name="Cowork", role="TAB"), lambda: False, lambda *args: results.append(args))
		scan.step()
		self.assertTrue(scan.cancelled)
		self.assertFalse(results)
		self.assertFalse(queue)

	def test_navigator_yields_and_caps_large_tree(self):
		Scan, queue = self.scanClass()
		child = None
		for i in range(720):
			child = SimpleNamespace(name="Cowork", role="TAB", next=child)
		results = []
		scan = Scan(SimpleNamespace(name="Claude", role="DOCUMENT", firstChild=child), lambda: True, lambda *args: results.append(args))
		scan.step()
		self.assertTrue(queue)
		self.assertFalse(results)
		while queue:
			queue.pop(0)()
		self.assertTrue(results[0][1])
		self.assertLessEqual(len(results[0][0]), 699)

	def test_branded_root_only(self):
		for name in ("Claude", "My project - Claude", "My project – Claude"):
			self.assertEqual("claude", adapter.conversationDocumentMode([name]))
		self.assertEqual("cowork", adapter.conversationDocumentMode(["Claude Cowork"]))
		self.assertEqual("code", adapter.conversationDocumentMode(["Claude Code"]))
		for names in (["ChatGPT"], ["Code"], ["Google Chrome"], ["Artifact", "Claude"], []):
			self.assertFalse(adapter.conversationDocumentMode(names))

	def test_only_selected_tabs_change_mode(self):
		for label, expected in (("Chat", "claude"), ("Cowork", "cowork"), ("Code", "code")):
			self.assertEqual(expected, adapter.modeFromTab(label, True, True))
			self.assertEqual("", adapter.modeFromTab(label, True, False))
			self.assertEqual("", adapter.modeFromTab(label, False, True))

	def test_prompt_rejects_other_editors(self):
		for label in ("Reply to Claude…", "Message Claude", "Ask Claude:"):
			self.assertTrue(adapter.promptLabel(label))
		for label in ("Search", "Search chats", "Artifact editor", "API key", "", "Message ChatGPT"):
			self.assertFalse(adapter.promptLabel(label))

	def test_speaker_content_is_not_guessed(self):
		self.assertEqual("", adapter.speakerFromLabel("Claude"))
		self.assertEqual("", adapter.speakerFromLabel("An assistant message about Claude" ,True))
		self.assertEqual("assistant", adapter.speakerFromLabel("Claude response 4", True))
		self.assertEqual("user", adapter.speakerFromLabel("User message 7", True))

	def test_reading_excludes_draft_and_controls_and_preserves_links(self):
		fields = [field("DOCUMENT", "Claude"), field("GROUPING", "User message 1"), "Hi", END,
			field("GROUPING", "Claude response 1"), "Hello ", field("LINK", "source"), "world", END,
			field("BUTTON", "Copy"), "Copy", END, END,
			field("EDITABLETEXT", "Reply to Claude"), "secret draft", END, END]
		self.assertEqual((("user", "Hi"), ("assistant", "Hello world")), core.chatMessagesFromTokens(adapter.messageTokens(fields)))

	def test_nested_artifact_text_is_excluded(self):
		fields = [field("DOCUMENT", "Claude"), field("GROUPING", "Claude response"), "Answer",
			field("DOCUMENT", "Artifact"), "Private embedded document", END, END, END]
		self.assertEqual((("assistant", "Answer"),), core.chatMessagesFromTokens(adapter.messageTokens(fields)))

	def test_unlabeled_content_does_not_become_message(self):
		self.assertEqual((), core.chatMessagesFromTokens(adapter.messageTokens(["settings", "a draft", field("BUTTON", "Claude"), END])))

	def test_heading_markers_and_message_limit(self):
		fields = []
		for i in range(14):
			fields += [field("HEADING", "Claude said:"), END, f"Answer {i} "]
		messages = core.chatMessagesFromTokens(adapter.messageTokens(fields), 10)
		self.assertEqual(10, len(messages))
		self.assertEqual(("assistant", "Answer 13"), messages[-1])

	def test_stop_does_not_confuse_dialog_cancel(self):
		for label in ("Stop response", "Stop generating", "Stop responding"):
			self.assertTrue(core.isStopControlLabel(label))
		self.assertFalse(core.isStopControlLabel("Cancel"))
		self.assertFalse(core.isStopControlLabel("Cancel subscription"))

	def test_navigator_never_matches_ordinary_response_text(self):
		self.assertEqual("Mode", adapter.navigationKind("Cowork", "TAB"))
		self.assertEqual("Artifact", adapter.navigationKind("Open artifact: report", "BUTTON"))
		self.assertEqual("Attachment", adapter.navigationKind("Upload file", "BUTTON"))
		self.assertFalse(adapter.navigationKind("Open artifact", "STATICTEXT"))
		self.assertFalse(adapter.navigationKind("Please open artifact now", "BUTTON"))

	def test_executable_prompt_guard_requires_claude_process(self):
		text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
		names = {"_isClaudeObject", "_isCodePromptObject"}
		nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name in names]
		env = {
			"_settings": lambda: {"supportedAppNames": "claude"},
			"Role": SimpleNamespace(EDITABLETEXT="edit"), "promptLabel": adapter.promptLabel,
			"isNativeComposer": adapter.isNativeComposer,
			"_conversationModeForObject": lambda obj: getattr(obj, "mode", ""),
		}
		exec(compile(ast.Module(body=nodes, type_ignores=[]), "guards", "exec"), env)
		for app, role, label, expected in (("claude", "edit", "Reply to Claude", True), ("chatgpt", "edit", "Reply to Claude", False), ("code", "edit", "Reply to Claude", False), ("claude", "edit", "Search chats", False), ("claude", "button", "Reply to Claude", False)):
			obj = SimpleNamespace(appModule=SimpleNamespace(appName=app), role=role, name=label)
			self.assertEqual(expected, env["_isCodePromptObject"](obj))

	def test_current_messages_runs_adapter_through_plugin(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_currentChatMessages")
		fields = [field("GROUPING", "Claude response"), "Test answer", END]
		env = {"api": SimpleNamespace(getFocusObject=lambda: "claude"), "_isClaudeObject": lambda obj: obj == "claude", "textInfos": SimpleNamespace(POSITION_ALL="all"), "chatMessagesFromTokens": core.chatMessagesFromTokens, "messageTokens": adapter.messageTokens}
		exec(compile(ast.Module(body=[node], type_ignores=[]), "messages", "exec"), env)
		instance = SimpleNamespace(_rememberBuffer=lambda obj: None, _buffer=SimpleNamespace(makeTextInfo=lambda pos: SimpleNamespace(getTextWithFields=lambda: fields)))
		self.assertEqual((("assistant", "Test answer"),), env["_currentChatMessages"](instance))

	def test_independent_identity_and_version(self):
		manifest = (ROOT / "manifest.ini").read_text(encoding="utf-8")
		for line in ("name = claudeDesktopAccess", "version = 2026.2.2", "minimumNVDAVersion = 2026.2.0", "lastTestedNVDAVersion = 2026.2.0"):
			self.assertIn(line, manifest.splitlines())
		self.assertEqual(["claude.py"], [p.name for p in (ROOT / "appModules").glob("*.py")])
		text = (PLUGIN / "__init__.py").read_text(encoding="utf-8")
		self.assertIn('CONFIG_SECTION = "claudeDesktopAccess"', text)
		for obsolete in ("CODEX_HOME", "CODE_HOME", "session_index.jsonl", "codex://", "code://"):
			self.assertNotIn(obsolete, text)

	def test_every_imported_local_helper_exists(self):
		for path in PLUGIN.glob("*.py"):
			for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
				if isinstance(node, ast.ImportFrom) and node.level == 1 and node.module in ("core", "claudeAdapter", "browserAccess"):
					module = load(node.module)
					for alias in node.names:
						self.assertTrue(hasattr(module, alias.name), f"{path.name}: {alias.name}")


if __name__ == "__main__":
	unittest.main()
