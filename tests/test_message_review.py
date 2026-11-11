"""Regression tests for missing messages in Claude's virtualized transcript."""

import ast
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

PLUGIN = Path(__file__).resolve().parents[1] / "globalPlugins/claudeDesktopAccess"


def load(name):
	spec = importlib.util.spec_from_file_location(name, PLUGIN / (name + ".py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


adapter = load("claudeAdapter")
MessageReview = load("messageReview").MessageReview
END = SimpleNamespace(command="controlEnd", field={})


def start(role, **attrs):
	return SimpleNamespace(command="controlStart", field={"role": role, **{
		"IAccessible2::attribute_" + key.replace("_", "-"): value for key, value in attrs.items()
	}})


def article(position, total=21, author="user", text="message"):
	classes = "group/bubble" if author == "user" else "group/message-row select-text print:block"
	return [start("section"), start("article", posinset=str(position), setsize=str(total)),
		start("section", **{"class": classes}), text, END, END, END]


def button(identifier=100, classes="sr-only select-none", **attrs):
	f = start("button", **{"class": classes})
	f.field.update({"controlIdentifier_docHandle": "7", "controlIdentifier_ID": str(identifier), **attrs})
	return [f, "Any translated label", END]


def page(*rows):
	return [start("document"), start("grouping", xml_roles="feed"), start("section"),
		*(f for row in rows for f in row), END, END, END]


class NativePagingTests(unittest.TestCase):
	def test_observed_middle_viewport_keeps_tail_and_loads_the_intervening_gap(self):
		fields = page(button(1), *(article(n) for n in range(5, 12)), button(2), article(20), article(21))
		for limit in range(1, 11):
			with self.subTest(shortcut=limit):
				self.assertEqual(2 if limit >= 2 else 1, len(adapter.codeBufferMessages(fields, limit)))
				self.assertEqual((7, 2, 11, 20, 21) if limit >= 3 else None, adapter.codeMessageLoadTarget(fields, limit))

	def test_loader_before_the_first_visible_article_fills_the_recent_gap(self):
		fields = page(button(5), *(article(n, 100) for n in range(95, 101)))
		self.assertEqual((7, 5, 0, 95, 100), adapter.codeMessageLoadTarget(fields, 10))
		self.assertIsNone(adapter.codeMessageLoadTarget(fields, 6))

	def test_highest_gap_is_loaded_before_older_gaps(self):
		fields = page(button(1), article(12), button(2), article(17), button(3), article(20), article(21))
		self.assertEqual((7, 3, 17, 20, 21), adapter.codeMessageLoadTarget(fields, 10))
		fields = page(button(1), article(12), button(2), *(article(n) for n in range(17, 22)))
		self.assertEqual((7, 2, 12, 17, 21), adapter.codeMessageLoadTarget(fields, 10))

	def test_available_tail_does_not_load_old_history(self):
		for total in (1, 2, 10, 1000):
			first = max(1, total - 9)
			fields = page(button(1), *(article(n, total) for n in range(first, total + 1)))
			self.assertIsNone(adapter.codeMessageLoadTarget(fields, 10))
			self.assertEqual(min(10, total), len(adapter.codeBufferMessages(fields, 10)))

	def test_buttons_in_answers_artifacts_or_unrelated_controls_are_never_activated(self):
		cases = [
			button(8, classes="sr-only"), button(8, classes="sr-only select-none extra"),
			[start("section"), *button(8), END],
			[start("document"), *button(8), END],
			[start("section", **{"class": "group/message-row select-text print:block"}), *button(8), END],
			[start("article", posinset="10", setsize="21"), *button(8), END],
		]
		for control in cases:
			with self.subTest(control=control[0].field):
				self.assertIsNone(adapter.codeMessageLoadTarget(page(control, article(20), article(21)), 10))

	def test_invalid_hidden_disabled_or_ambiguous_loaders_are_rejected(self):
		for attrs in ({"controlIdentifier_ID": "bad"}, {"states": {"UNAVAILABLE"}},
			{"states": {"INVISIBLE"}}, {"isHidden": True}):
			self.assertIsNone(adapter.codeMessageLoadTarget(page(button(1, **attrs), article(20), article(21)), 10))
		self.assertIsNone(adapter.codeMessageLoadTarget(page(button(1), button(2), article(20), article(21)), 10))
		self.assertIsNone(adapter.codeMessageLoadTarget(page(button(1), article(20), article(21)) * 2, 10))

	def test_inconsistent_positions_cannot_authorize_loading(self):
		for rows in ((article(20), article(19)), (article(20), article(20)),
			(article(20), article(21, 22)), (article(22),), (article("bad"),), (article(0),)):
			with self.subTest(rows=rows):
				self.assertIsNone(adapter.codeMessageLoadTarget(page(button(1), *rows), 10))

	def test_labels_and_message_contents_do_not_authorize_a_loader(self):
		fields = page(button(2), article(20, text="Charger les messages suivants"), article(21, text="Load later messages"))
		for f in fields:
			if not isinstance(f, str) and f.command == "controlStart":
				f.field["name"] = "任意のラベル"
		self.assertEqual((7, 2, 0, 20, 21), adapter.codeMessageLoadTarget(fields, 10))
		self.assertEqual(2, len(adapter.codeBufferMessages(fields, 10)))

	def test_pending_response_does_not_hide_the_tenth_readable_message(self):
		fields = page(button(5), *(article(n) for n in range(12, 21)), article(21, author="assistant", text=""))
		fields[1].field["IAccessible2::attribute_busy"] = "true"
		self.assertEqual(9, len(adapter.codeBufferMessages(fields, 10)))
		self.assertEqual((7, 5, 0, 12, 21), adapter.codeMessageLoadTarget(fields, 10))
		fields[1].field["IAccessible2::attribute_busy"] = "false"
		self.assertIsNone(adapter.codeMessageLoadTarget(fields, 10))


class RetrievalTests(unittest.TestCase):
	def harness(self, position=10):
		state = SimpleNamespace(now=0.0, valid=True, messages=("tail",), loader=(7, 1), reads=0)
		queue, activated, reported, errors = [], [], [], []
		def schedule(delay, callback):
			item = (state.now + delay / 1000, callback)
			queue.append(item)
			return SimpleNamespace(Stop=lambda: queue.remove(item) if item in queue else None)
		def read(limit):
			state.reads += 1
			return state.messages, state.loader
		request = MessageReview(position, read, activated.append, lambda: state.valid, reported.append,
			lambda: errors.append(True), schedule, lambda: state.now)
		def tick():
			time, callback = queue.pop(0)
			state.now = time
			callback()
		return state, request, queue, activated, reported, errors, tick

	def test_all_ten_shortcuts_retrieve_the_requested_message_after_loading(self):
		for position in range(1, 11):
			with self.subTest(shortcut=position):
				state, req, queue, activated, reported, errors, tick = self.harness(position)
				state.messages = ()
				req.step()
				self.assertEqual([(7, 1)], activated)
				tick()  # Still waiting on the same native control; do not click twice.
				state.messages = tuple(range(position))
				state.loader = None
				tick()
				self.assertEqual([tuple(range(position))], reported)
				self.assertEqual([(7, 1)], activated)
				self.assertFalse(queue or errors)

	def test_multiple_pages_and_temporary_missing_buffer_are_supported(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		req.step()
		state.loader = None
		tick()
		self.assertFalse(reported or errors)
		state.loader = (7, 2)
		tick()
		state.messages = tuple(range(10))
		tick()
		self.assertEqual([(7, 1), (7, 2)], activated)
		self.assertEqual([tuple(range(10))], reported)

	def test_reused_native_button_can_load_again_when_its_gap_changes(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		state.loader = (7, 1, 0, 16, 17)
		req.step()
		state.messages = tuple(range(7))
		state.loader = (7, 1, 0, 11, 17)
		tick()
		state.messages = tuple(range(10))
		tick()
		self.assertEqual([(7, 1, 0, 16, 17), (7, 1, 0, 11, 17)], activated)
		self.assertEqual([tuple(range(10))], reported)
		self.assertFalse(errors)

	def test_session_or_application_switch_cancels_without_speaking(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		req.step()
		state.valid = False
		state.messages = tuple(range(10))
		tick()
		self.assertTrue(req.cancelled)
		self.assertFalse(reported or errors or queue)

	def test_context_change_during_read_never_activates_a_control(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		def read(limit):
			state.valid = False
			return (), (7, 1)
		req.read = read
		req.step()
		self.assertFalse(activated or reported or errors or queue)

	def test_user_input_cancellation_stops_pending_work(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		req.step()
		req.cancel()
		self.assertFalse(queue)
		req.step()
		self.assertEqual(1, state.reads)
		self.assertFalse(reported or errors)

	def test_failed_loading_has_a_time_limit_and_does_not_repeat_activation(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		req.step()
		while queue:
			tick()
		self.assertEqual([(7, 1)], activated)
		self.assertEqual([True], errors)
		self.assertFalse(reported)
		self.assertLess(state.now, 5.2)

	def test_short_conversations_and_already_available_messages_need_no_actions(self):
		for position, messages in ((1, ("tail",)), (10, ()), (10, (1, 2))):
			state, req, queue, activated, reported, errors, tick = self.harness(position)
			state.messages, state.loader = messages, None
			req.step()
			self.assertEqual([messages], reported)
			self.assertFalse(activated or errors or queue)

	def test_inaccessible_action_fails_without_retrying(self):
		state, req, queue, activated, reported, errors, tick = self.harness()
		def broken(loader):
			raise RuntimeError("provider disappeared")
		req.activate = broken
		req.step()
		self.assertEqual([True], errors)
		self.assertFalse(reported or queue)

	def test_plugin_loads_the_native_gap_restores_focus_and_announces_the_requested_position(self):
		tree = ast.parse((PLUGIN / "__init__.py").read_text(encoding="utf-8"))
		methods = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in (
			"_cancelMessageReview", "_readRecentChatMessage", "_reportRecentChatMessage",
		)]
		for correctControl in (True, False):
			with self.subTest(correctControl=correctControl):
				spoken, actions, queue = [], [], []
				state = SimpleNamespace(fields=page(button(5), article(20), article(21)), focus=None)
				root = SimpleNamespace(role="document", value="https://claude.ai/epitaxy/local_test")
				def node(role, classes, parent=None):
					return SimpleNamespace(role=role, IA2Attributes={"class": classes}, parent=parent)
				prompt = node("editabletext", "ProseMirror", node("section", "rounded-composer", root))
				state.focus = prompt
				prompt.setFocus = lambda: setattr(state, "focus", prompt)
				def activate():
					actions.append(True)
					state.fields = page(button(5), *(article(n, text=f"prompt {n}") for n in range(12, 22)))
					state.focus = root
				control = node("button", "sr-only select-none" if correctControl else "unrelated")
				control.doAction = activate
				def resolve(handle, identifier):
					self.assertEqual((7, 5), (handle, identifier))
					return control
				buffer = SimpleNamespace(rootNVDAObject=root, getNVDAObjectFromIdentifier=resolve,
					makeTextInfo=lambda position: SimpleNamespace(getTextWithFields=lambda: state.fields))
				def schedule(delay, callback):
					queue.append(callback)
					return SimpleNamespace(Stop=lambda: queue.remove(callback) if callback in queue else None)
				env = dict(api=SimpleNamespace(getFocusObject=lambda: state.focus), _isClaudeObject=lambda obj: True,
					codeDocumentUrl=adapter.codeDocumentUrl, isNativeComposer=adapter.isNativeComposer,
					codeMessageLoadTarget=adapter.codeMessageLoadTarget, nativeClasses=adapter.nativeClasses,
					_roleName=lambda obj: adapter.roleName(obj.role), MessageReview=MessageReview,
					textInfos=SimpleNamespace(POSITION_ALL="all"), wx=SimpleNamespace(CallLater=schedule),
					ui=SimpleNamespace(message=spoken.append), _=lambda s: s)
				exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name="Plugin", bases=[], keywords=[], body=methods, decorator_list=[])],
					type_ignores=[])), "messageReviewPlugin", "exec"), env)
				plugin = env["Plugin"]()
				plugin._rememberBuffer = lambda obj: buffer
				plugin._currentChatMessages = lambda limit: adapter.codeBufferMessages(state.fields, limit)
				plugin._readRecentChatMessage(10)
				for _ in range(5):
					if not queue:
						break
					queue.pop(0)()
				if correctControl:
					self.assertEqual([True], actions)
					self.assertIs(prompt, state.focus)
					self.assertEqual(["You: prompt 12"], spoken)
				else:
					self.assertFalse(actions)
					self.assertEqual(["Recent chat messages could not be read"], spoken)
				self.assertIsNone(plugin._messageReview)


if __name__ == "__main__":
	unittest.main()
