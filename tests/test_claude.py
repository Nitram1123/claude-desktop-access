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

	def test_composer_suggestions_require_native_selection_in_a_listbox(self):
		ia2 = node("listitem", "über Datei", IA2Attributes={"xml-roles": "option"}, states={"SELECTED"})
		uia = node("listitem", "élément", aria="option", states={"FOCUSED"})
		box = node("list", "", node("grouping", "", ia2), uia, IA2Attributes={"xml-roles": "listbox"})
		self.assertIs(box, adapter.selectedComposerSuggestionList(ia2))
		self.assertIsNone(adapter.selectedComposerSuggestionList(uia))
		uia.states.add("SELECTED")
		self.assertIs(box, adapter.selectedComposerSuggestionList(uia))
		editor = node("editabletext", "", aria="textbox", classes="ProseMirror")
		node("section", "", editor, box, classes="rounded-composer")
		self.assertIsNone(adapter.selectedComposerMention(editor))
		ia2.states.clear()
		self.assertIs(uia, adapter.selectedComposerMention(editor))
		command = node("menuitem", "command", aria="menuitem", states={"FOCUSED"})
		node("popupmenu", "", command, aria="menu")
		self.assertIsNone(adapter.selectedComposerSuggestionList(command))
		for identifier in ("kb:upArrow", "kb(desktop):downArrow"):
			self.assertTrue(adapter.isComposerArrowGestureIdentifier(identifier))
		for identifier in ("kb:shift+upArrow", "kb:NVDA+downArrow", "br(display):upArrow"):
			self.assertFalse(adapter.isComposerArrowGestureIdentifier(identifier))

	def test_composer_selection_is_spoken_once_after_an_arrow(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		plugin = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "GlobalPlugin")
		method = next(item for item in plugin.body if getattr(item, "name", "") == "_announceComposerSuggestion")
		choice = node("listitem", "選択肢")
		focus = SimpleNamespace(makeTextInfo=lambda position: SimpleNamespace(text="@"), treeInterceptor=SimpleNamespace(rootNVDAObject=node(
			"document", "Code", value="https://claude.ai/epitaxy/local_test",
		)))
		current = SimpleNamespace(focus=focus)
		messages = []
		env = {
			"api": SimpleNamespace(getFocusObject=lambda: current.focus),
			"ui": SimpleNamespace(message=messages.append),
			"textInfos": SimpleNamespace(POSITION_ALL="all"),
			"selectedComposerMention": lambda obj: choice,
			"isNativeComposer": lambda obj: obj is focus,
			"isCodeDocument": adapter.isCodeDocument,
		}
		exec(compile(ast.Module(body=[method], type_ignores=[]), "composerSuggestion", "exec"), env)
		announce = env[method.name]
		addon = SimpleNamespace(
			_appFocusState=True, _composerCommandMenu=None, _lastComposerSuggestion=None,
		)
		announce(addon, focus)
		announce(addon, focus)
		self.assertEqual(["選択肢"], messages)
		current.focus = None
		choice.name = "Autre choix"
		announce(addon, focus)
		self.assertEqual(["選択肢"], messages)

	def test_slash_menu_uses_the_unique_visible_row_with_a_different_background(self):
		def background(color):
			return SimpleNamespace(attributes=lambda offset: (0, 1, f"background-color:{color};"))

		first = node("menuitem", "Uno", states=set(), IAccessibleTextObject=background("rgb(10,10,10)"))
		second = node("menuitem", "二", states=set(), IAccessibleTextObject=background("rgb(30,30,30)"))
		third = node("menuitem", "Trois", states={"OFFSCREEN"}, IAccessibleTextObject=background("rgb(40,40,40)"))
		menu = node("popupmenu", "", node("grouping", "", first, second, third),
			IAccessibleTextObject=background("rgb(10,10,10)"))
		self.assertIs(second, adapter.highlightedComposerCommand(menu)[0])
		third.states.clear()
		self.assertIsNone(adapter.highlightedComposerCommand(menu)[0])
		third.states.add("OFFSCREEN")
		first.next = third
		self.assertIsNone(adapter.highlightedComposerCommand(menu)[0])
		menu.firstChild = second
		self.assertIs(second, adapter.highlightedComposerCommand(menu)[0])

	def test_slash_menu_reuses_the_ordinary_color_when_the_filtered_range_is_mixed(self):
		first = node("menuitem", "Uno", states=set(), background=0)
		second = node("menuitem", "二", states=set(), background=5)
		third = node("menuitem", "Trois", states=set(), background=0)
		menu = node("popupmenu", "", first, second, third, background=None)
		backgroundFor = lambda obj: obj.background
		selection, background = adapter.highlightedComposerCommand(menu, backgroundFor)
		self.assertIs(second, selection)
		self.assertEqual(0, background)
		second.next = None
		self.assertIsNone(adapter.highlightedComposerCommand(menu, backgroundFor)[0])
		self.assertIs(second, adapter.highlightedComposerCommand(menu, backgroundFor, background)[0])

	def test_slash_menu_can_be_located_while_focus_remains_in_the_composer(self):
		nested = node("popupmenu", "", aria="menu", classes="bg-surface-3 max-h-96", states=set())
		hidden = node("popupmenu", "", aria="menu", classes="bg-surface-3 max-h-96", states={"INVISIBLE"})
		visible = node("popupmenu", "", aria="menu", classes="bg-surface-3 max-h-96", states=set())
		document = node("document", "", node("grouping", "",
			node("document", "", nested), node("section", "", visible), hidden,
		))
		self.assertIs(visible, adapter.composerCommandMenu(document))

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
		env = {"_settings": lambda: {"supportedAppNames": "claude"}, "Role": SimpleNamespace(EDITABLETEXT="edit"), "promptLabel": adapter.promptLabel}
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
