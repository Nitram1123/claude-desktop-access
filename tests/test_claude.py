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
		self.assertTrue(adapter.isCodeDocument(node("document", "", value="", IAccessibleObject=SimpleNamespace(
			accValue=lambda child: "https://claude.ai/epitaxy/session",
		))))

	def test_prompt_editor_requires_native_composer_ancestry(self):
		for editor in (
			node("editabletext", "", classes="ProseMirror"),
			node("editabletext", "", IA2Attributes={"class": "ProseMirror"}),
		):
			self.assertFalse(adapter.isNativeComposer(editor))
			node("section", "", editor, classes="rounded-composer")
			self.assertTrue(adapter.isNativeComposer(editor))
			# A nested artifact document must not inherit the outer editor's context.
			node("section", "", node("document", "", editor), classes="rounded-composer")
			self.assertFalse(adapter.isNativeComposer(editor))

	def test_code_composer_announces_recalled_text_and_preserves_plain_caret_movement(self):
		tree = ast.parse((ROOT / "appModules/claude.py").read_text(encoding="utf-8"))
		mixin = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "ClaudeComposer")
		calls = []
		state = SimpleNamespace(focus=None, waiting=False, sayAll=False)
		env = {
			"api": SimpleNamespace(getFocusObject=lambda: state.focus),
			"ui": SimpleNamespace(message=lambda text: calls.append(("say", text))),
			"textInfos": SimpleNamespace(POSITION_ALL="all", UNIT_LINE="line"),
			"isScriptWaiting": lambda: state.waiting,
			"willSayAllResume": lambda gesture: state.sayAll,
		}
		import builtins
		realImport = builtins.__import__
		def importAdapter(name, *args):
			return adapter if name == "globalPlugins.claudeDesktopAccess.claudeAdapter" else realImport(name, *args)
		env["__builtins__"] = dict(vars(builtins), __import__=importAdapter)
		exec(compile(ast.Module(body=[mixin], type_ignores=[]), "composer", "exec"), env)

		class Editable:
			text = ""
			treeInterceptor = SimpleNamespace(rootNVDAObject=node(
				"document", "Claude Code", value="https://claude.ai/epitaxy/local_test",
			))

			def makeTextInfo(self, position):
				return SimpleNamespace(text=self.text)

			def _caretMovementScriptHelper(self, gesture, unit):
				calls.append(("send", gesture.identifiers[0]))
				self.text = gesture.replacement
				self._caretScriptPostMovedHelper(unit, gesture)

			def _caretScriptPostMovedHelper(self, unit, gesture, info):
				calls.append(("caret", unit))

		class Composer(env["ClaudeComposer"], Editable):
			pass

		composer = state.focus = Composer()
		for gesture, replacement, expected, guard in (
			("kb:upArrow", "Texte rappelé\nDeuxième ligne", [("caret", None), ("say", "Texte rappelé\nDeuxième ligne")], ""),
			("kb:upArrow", "Texte rappelé\nDeuxième ligne", [("caret", "line")], ""),
			("kb:downArrow", "Message plus récent", [("caret", None), ("say", "Message plus récent")], ""),
			("kb:shift+downArrow", "Brouillon", [("caret", "line")], ""),
			("kb:upArrow", "En attente", [("caret", "line")], "waiting"),
			("kb:upArrow", "Dire tout", [("caret", "line")], "sayAll"),
			("kb:upArrow", "Autre champ", [("caret", "line")], "focus"),
			("kb:upArrow", "Autre vue", [("caret", "line")], "document"),
			("kb:downArrow", "", [("caret", "line")], ""),
			("kb:upArrow", "", [("caret", "line")], ""),
		):
			with self.subTest(gesture=gesture, replacement=replacement):
				calls.clear()
				state.waiting, state.sayAll = guard == "waiting", guard == "sayAll"
				state.focus = None if guard == "focus" else composer
				composer.treeInterceptor.rootNVDAObject.value = (
					"https://claude.ai/chat/local_test" if guard == "document" else "https://claude.ai/epitaxy/local_test"
				)
				composer._caretMovementScriptHelper(SimpleNamespace(identifiers=[gesture], replacement=replacement), "line")
				self.assertEqual([("send", gesture), *expected], calls)
				self.assertIsNone(getattr(composer, "_claudeTextBeforeArrow", None))

	def scanClass(self):
		tree = ast.parse((PLUGIN / "claudeNavigator.py").read_text(encoding="utf-8"))
		node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "NavigationScan")
		queue = []
		def later(delay, callback):
			queue.append(callback)
			return SimpleNamespace(Stop=lambda: queue.clear())
		env = {"wx": SimpleNamespace(CallLater=later), "time": time, "navigationKind": adapter.navigationKind, "nativeNavigationKind": adapter.nativeNavigationKind, "isCodeDocument": adapter.isCodeDocument, "roleName": adapter.roleName}
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

	def test_compact_mode_uses_selection_and_structure(self):
		home = node("radiobutton", "Code", states={"CHECKED"})
		code = node("radiobutton", "", states={"FOCUSABLE"})
		group = node("grouping", "Mode", home, code, aria="radiogroup",
			classes="bg-[var(--cds-segmented-control-track)]")
		node("grouping", "", group, classes="dframe-chrome-bar")
		self.assertEqual("Mode", adapter.nativeNavigationKind(home))
		self.assertEqual("Mode", adapter.nativeNavigationKind(code))
		self.assertFalse(adapter.nativeMode(home))
		self.assertFalse(adapter.nativeMode(code))
		code.states = {"CHECKED"}
		self.assertEqual("code", adapter.nativeMode(code))
		code.next = node("radiobutton", "Cowork")
		self.assertFalse(adapter.nativeMode(code))

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

	def test_native_code_articles_ignore_names_and_preserve_repeated_content(self):
		def article(position, wrapper, *children):
			return node("article", "Ignorierter Titel", wrapper, *children,
				aria="article", props=f"posinset={position};setsize=3")
		user = article(1, node("grouping", "", node("statictext", "Copier"), classes="group/bubble"),
			node("heading", "Claude a répondu", classes="sr-only"))
		assistant = article(2, node("grouping", "",
			node("heading", "ユーザー", classes="sr-only"),
			node("heading", "Copier"), node("toolbar", "", node("statictext", "Ignore")),
			node("document", "", node("statictext", "Ignore")),
			classes="group/message-row select-text print:block"))
		another = article(3, node("grouping", "", node("statictext", "Copier"),
			classes="group/message-row select-text print:block"))
		unrelated = article(4, node("grouping", "", node("statictext", "Ignore"), classes="group/bubble"))
		root = node("document", "", node("grouping", "", user, assistant, another, aria="feed"), unrelated)
		self.assertEqual((("user", "Copier"), ("assistant", "Copier"), ("assistant", "Copier")),
			adapter.nativeArticleMessages(root))
		self.assertEqual((("assistant", "Copier"),), adapter.nativeArticleMessages(root, limit=1))
		user.firstChild.UIAElement.currentClassName = ""
		self.assertEqual((("assistant", "Copier"), ("assistant", "Copier")), adapter.nativeArticleMessages(root))

	def test_native_transcript_rejects_an_old_viewport_and_ambiguous_panels(self):
		message = node("article", "", node("grouping", "", node("statictext", "First"), classes="group/bubble"),
			props="posinset=1;setsize=2")
		first = node("grouping", "", message, aria="feed")
		root = node("document", "", first)
		self.assertEqual((), adapter.nativeArticleMessages(root))
		message.UIAElement.currentAriaProperties = "posinset=1;setsize=1"
		self.assertEqual((("user", "First"),), adapter.nativeArticleMessages(root))
		prompt = node("editabletext", "", classes="ProseMirror")
		left = node("grouping", "", first, prompt, classes="epitaxy-chat-panel")
		right = node("grouping", "", node("grouping", "", aria="feed"), classes="epitaxy-chat-panel")
		root = node("document", "", left, right)
		self.assertEqual((), adapter.nativeArticleMessages(root))
		self.assertEqual((("user", "First"),), adapter.nativeArticleMessages(root, focus=prompt))

	def test_ia2_uses_document_url_and_structural_message_fields(self):
		doc = node("document", "", IAccessibleObject=SimpleNamespace(accValue=lambda child: "https://claude.ai/epitaxy/session"))
		self.assertTrue(adapter.isCodeDocument(doc))
		def ia2(role, **attrs):
			return field(role, "任意", **{"IAccessible2::attribute_" + key.replace("_", "-"): val for key, val in attrs.items()})
		fields = [
			ia2("document"), ia2("section", xml_roles="feed"), ia2("article", posinset=1, setsize=2),
			ia2("heading", **{"class": "sr-only"}), "Invisible heading", END,
			ia2("section", **{"class": "group/bubble"}), "Copier", END, END,
			ia2("article", posinset=2, setsize=2),
			ia2("section", **{"class": "group/message-row select-text print:block"}),
			ia2("heading", **{"class": "sr-only"}), "Other invisible heading", END,
			ia2("toolbar"), "Ignore", END, END, END,
			ia2("section", **{"class": "group/message-row select-text print:block"}),
			ia2("paragraph"), "L", "ooks ", "good.", END, END, END, END,
		]
		self.assertEqual((("user", "Copier"), ("assistant", "Looks good.")), adapter.codeBufferMessages(fields, 10))
		self.assertEqual((("assistant", "Looks good."),), adapter.codeBufferMessages(fields, 1))

	def test_native_search_and_attachments_require_semantic_context(self):
		search = node("button", "任意", classes="hit-row", accelerator="Control+Shift+k")
		fake = node("button", "Rechercher", classes="hit-row")
		node("grouping", "", search, fake, classes="dframe-sidebar")
		self.assertEqual("Navigation", adapter.nativeNavigationKind(search))
		self.assertFalse(adapter.nativeNavigationKind(fake))
		add = node("button", "", props="haspopup=menu")
		ordinary = node("button", "Ajouter")
		slot = node("grouping", "", add, ordinary, classes="absolute bottom-0 start-0 pe-[var(--cds-gap-xs)]")
		node("grouping", "", slot, classes="rounded-composer")
		self.assertEqual("Attachment", adapter.nativeNavigationKind(add))
		self.assertFalse(adapter.nativeNavigationKind(ordinary))
		slot.parent = None
		self.assertFalse(adapter.nativeNavigationKind(add))

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
		names = {"_isClaudeObject", "_isCodePromptObject", "_roleName"}
		nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name in names]
		env = {"_settings": lambda: {"supportedAppNames": "claude"}, "Role": SimpleNamespace(EDITABLETEXT="edit"), "promptLabel": adapter.promptLabel, "nativeNavigationKind": adapter.nativeNavigationKind, "isCodeDocument": adapter.isCodeDocument, "_conversationModeForObject": lambda obj: getattr(obj, "mode", ""), "isNativeComposer": adapter.isNativeComposer}
		exec(compile(ast.Module(body=nodes, type_ignores=[]), "guards", "exec"), env)
		for app, role, label, expected in (("claude", "edit", "Reply to Claude", True), ("chatgpt", "edit", "Reply to Claude", False), ("code", "edit", "Reply to Claude", False), ("claude", "edit", "Search chats", False), ("claude", "button", "Reply to Claude", False)):
			obj = SimpleNamespace(appModule=SimpleNamespace(appName=app), role=role, name=label)
			self.assertEqual(expected, env["_isCodePromptObject"](obj))
		prompt = node("edit", "Reply to Claude", mode="code", appModule=SimpleNamespace(appName="claude"),
			classes="ProseMirror")
		self.assertFalse(env["_isCodePromptObject"](prompt))
		node("section", "", prompt, classes="rounded-composer")
		for label in ("", "Eingabe", "入力"):
			prompt.name = label
			self.assertTrue(env["_isCodePromptObject"](prompt))

	def test_current_messages_runs_adapter_through_plugin(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_currentChatMessages")
		fields = [field("GROUPING", "Claude response"), "Test answer", END]
		env = {"api": SimpleNamespace(getFocusObject=lambda: "claude"), "_isClaudeObject": lambda obj: obj == "claude", "textInfos": SimpleNamespace(POSITION_ALL="all"), "chatMessagesFromTokens": core.chatMessagesFromTokens, "messageTokens": adapter.messageTokens, "isCodeDocument": adapter.isCodeDocument, "nativeArticleMessages": adapter.nativeArticleMessages, "codeBufferMessages": adapter.codeBufferMessages}
		exec(compile(ast.Module(body=[method], type_ignores=[]), "messages", "exec"), env)
		buffer = SimpleNamespace(makeTextInfo=lambda pos: SimpleNamespace(getTextWithFields=lambda: fields))
		instance = SimpleNamespace(_rememberBuffer=lambda obj: buffer, _buffer=buffer)
		self.assertEqual((("assistant", "Test answer"),), env["_currentChatMessages"](instance))
		buffer.rootNVDAObject = node("document", "任意", value="https://claude.ai/epitaxy/session")
		# In Code, a label-shaped virtual-buffer string cannot become a message.
		self.assertEqual((), env["_currentChatMessages"](instance))
		instance._rememberBuffer = lambda obj: None
		self.assertEqual((), env["_currentChatMessages"](instance))

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
