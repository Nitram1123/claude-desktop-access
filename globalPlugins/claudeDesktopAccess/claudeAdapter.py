"""Conservative Claude accessibility classifiers, independent of NVDA.

Labels are candidate English patterns for beta testing, not captured live fixtures.
No conversation text is sent to a service or written to disk by this module.
"""

from collections import Counter, deque
import re
import time
from urllib.parse import urlsplit


def normalized(value):
	return " ".join(str(value or "").casefold().split())


def modeDisplayName(mode):
	return {"claude": "Claude Chat", "code": "Claude Code", "cowork": "Claude Cowork"}.get(mode, "Claude")


def conversationDocumentMode(names):
	"""Require a single branded document; reject nested artifact/web documents."""
	names = tuple(normalized(name) for name in names)
	if len(names) != 1:
		return ""
	name = names[0]
	if name in ("claude code", "code – claude", "code - claude"):
		return "code"
	if name in ("claude cowork", "cowork – claude", "cowork - claude"):
		return "cowork"
	if name == "claude" or name.endswith((" - claude", " – claude", " | claude")):
		return "claude"
	return ""


def modeFromTab(label, isTab, selected):
	if not isTab or not selected:
		return ""
	return {"chat": "claude", "claude chat": "claude", "cowork": "cowork", "code": "code"}.get(normalized(label), "")


def promptLabel(value):
	return normalized(value).rstrip(".…:") in {
		"reply to claude", "message claude", "ask claude", "how can i help you today",
		"how can i help you", "what can i help you with", "send a message", "write a reply",
	}


def speakerFromLabel(label, structural=False):
	label = normalized(label)
	if label in ("you said:", "user said:") or (structural and re.fullmatch(r"(?:user|human) message(?: \d+)?", label)):
		return "user"
	if label in ("claude said:", "assistant said:") or (structural and re.fullmatch(r"(?:assistant|claude) (?:message|response)(?: \d+)?", label)):
		return "assistant"
	if structural:
		return {"you": "user", "human": "user", "user": "user", "claude": "assistant", "assistant": "assistant"}.get(label.rstrip(":"), "")
	return ""


def roleName(role):
	return str(getattr(role, "name", role) or "").casefold().replace(" ", "").replace("_", "")


def _uiaProperty(obj, name):
	try:
		return getattr(getattr(obj, "UIAElement", None), name, None)
	except Exception:
		# A UIA provider can disappear when Claude replaces a panel.
		return None


def nativeClasses(obj):
	attrs = getattr(obj, "IA2Attributes", None) or {}
	return set(str(attrs.get("class") or _uiaProperty(obj, "cachedClassName") or _uiaProperty(obj, "currentClassName") or "").split())


def _ariaRole(obj):
	attrs = getattr(obj, "IA2Attributes", None) or {}
	return attrs.get("xml-roles") or _uiaProperty(obj, "currentAriaRole") or roleName(getattr(obj, "role", None))


def nativeDocumentUrl(obj):
	if roleName(getattr(obj, "role", None)) != "document":
		return ""
	value = getattr(obj, "value", "")
	if not value:
		try:
			# Chromium IA2 exposes the document URL through MSAA.
			value = obj.IAccessibleObject.accValue(0)
		except Exception:
			return ""
	return value or ""


def codeDocumentUrl(obj):
	value = nativeDocumentUrl(obj)
	try:
		url = urlsplit(value)
	except ValueError:
		return ""
	if url.scheme == "https" and url.hostname == "claude.ai" and (
		url.path == "/epitaxy" or url.path.startswith("/epitaxy/")
	):
		return value
	return ""


def isCodeDocument(obj):
	return bool(codeDocumentUrl(obj))


def _ancestors(obj, limit=12):
	for _ in range(limit):
		obj = getattr(obj, "parent", None)
		if obj is None or roleName(getattr(obj, "role", None)) == "document":
			break
		yield obj


def _inside(obj, className):
	return any(className in nativeClasses(parent) for parent in _ancestors(obj))


def isNativeComposer(obj):
	return "ProseMirror" in nativeClasses(obj) and _inside(obj, "rounded-composer")


def isComposerArrowGestureIdentifier(identifier):
	source, _, key = str(identifier or "").casefold().rpartition(":")
	return source.startswith("kb") and key in ("uparrow", "downarrow")


def selectedComposerSuggestionList(obj):
	"""Return the native suggestion list for an option marked as selected."""
	if _ariaRole(obj) != "option" or "selected" not in {roleName(state) for state in getattr(obj, "states", ())}:
		return None
	return next((parent for parent in _ancestors(obj) if _ariaRole(parent) == "listbox"), None)


def selectedComposerMention(editor):
	"""Find the native selected option in the editor's own mention popup."""
	composer = next((obj for obj in _ancestors(editor) if "rounded-composer" in nativeClasses(obj)), None)
	if composer is None:
		return None
	pending = [(getattr(composer, "firstChild", None), 0)]
	deadline = time.monotonic() + 0.35
	selected = None
	for _ in range(140):
		if not pending:
			return selected
		if time.monotonic() >= deadline:
			return None
		obj, depth = pending.pop()
		if obj is None:
			continue
		pending.append((getattr(obj, "next", None), depth))
		role = _ariaRole(obj)
		if role == "option":
			if selectedComposerSuggestionList(obj) is not None:
				if selected is not None:
					return None
				selected = obj
		elif role not in ("document", "textbox") and depth < 10:
			pending.append((getattr(obj, "firstChild", None), depth + 1))
	return None


def nativeTextBackground(obj):
	try:
		_, _, attributes = obj.IAccessibleTextObject.attributes(0)
	except Exception:
		return None
	match = re.search(r"(?:^|;)background-color:([^;]+)", attributes or "")
	return match.group(1) if match else None


def isComposerCommandMenu(obj):
	return _ariaRole(obj) == "menu" and {"bg-surface-3", "max-h-96"}.issubset(nativeClasses(obj))


def composerCommandMenu(root):
	"""Find the popup that Claude appends near the end of the document."""
	pending = deque([(root, 0)])
	deadline = time.monotonic() + 0.35
	for _ in range(55):
		if not pending or time.monotonic() >= deadline:
			return None
		obj, depth = pending.popleft()
		if isComposerCommandMenu(obj):
			states = {roleName(state) for state in getattr(obj, "states", ())}
			if not states.intersection(("invisible", "offscreen")):
				return obj
		if depth >= 4 or (obj is not root and _ariaRole(obj) in ("document", "feed", "textbox")):
			continue
		child = getattr(obj, "lastChild", None)
		for _ in range(8):
			if child is None:
				break
			pending.append((child, depth + 1))
			child = getattr(child, "previous", None)
	return None


def highlightedComposerCommand(menu, backgroundFor=nativeTextBackground, previousBackground=None):
	"""Return the one highlighted row and the ordinary background of its menu."""
	background = backgroundFor(menu)
	pending = [(getattr(menu, "firstChild", None), 0)]
	deadline = time.monotonic() + 0.35
	rows = []
	colors = Counter()
	for _ in range(96):
		if not pending:
			break
		if time.monotonic() >= deadline:
			return None, previousBackground
		obj, depth = pending.pop()
		if obj is None:
			continue
		pending.append((getattr(obj, "next", None), depth))
		role = _ariaRole(obj)
		if role in ("menuitem", "menuitemcheckbox", "menuitemradio"):
			color = backgroundFor(obj)
			if color is None:
				continue
			colors[color] += 1
			states = {roleName(state) for state in getattr(obj, "states", ())}
			if not states.intersection(("invisible", "offscreen", "unavailable")):
				rows.append((obj, color))
		elif role != "menu" and depth < 4:
			pending.append((getattr(obj, "firstChild", None), depth + 1))
	else:
		return None, previousBackground
	if background is None:
		background = previousBackground
		if colors:
			common, count = colors.most_common(1)[0]
			if count > 1 and count * 2 > sum(colors.values()):
				background = common
	highlighted = [obj for obj, color in rows if background is not None and color != background]
	return (highlighted[0] if len(highlighted) == 1 else None), background


def messageTokens(fields):
	"""Read named message regions; ignore editors, toolbars and nested documents.

	Only explicit speaker markers establish authorship. Do not guess alternating
	speakers or parse the contents of the user's draft as a sent message.
	"""
	stack = []
	ignored = 0
	for item in fields:
		if isinstance(item, str):
			if not ignored:
				speaker = speakerFromLabel(item)
				yield ("speaker", speaker) if speaker else ("text", item)
			continue
		command = getattr(item, "command", "")
		field = getattr(item, "field", {}) or {}
		if command == "controlStart":
			role = roleName(field.get("role"))
			skip = bool(ignored or role in ("button", "editabletext", "combobox", "toolbar", "checkbox", "radiobutton") or (role == "document" and stack))
			structural = role in ("grouping", "section", "article", "heading", "listitem", "unknown")
			speaker = "" if skip else speakerFromLabel(field.get("name"), structural)
			# Some backends preserve explicit HTML author attributes in the field.
			if not skip and structural and not speaker:
				author = normalized(field.get("data-message-author-role"))
				speaker = author if author in ("user", "assistant") else ""
			stack.append((skip, bool(speaker and role != "heading")))
			if skip:
				ignored += 1
			elif speaker:
				yield "speaker", speaker
		elif command == "controlEnd" and stack:
			skip, boundary = stack.pop()
			if skip:
				ignored -= 1
			elif boundary:
				yield "end", ""
	yield "end", ""


def navigationKind(name, role):
	label, role = normalized(name), roleName(role)
	if role not in ("tab", "button", "link"):
		return ""
	if label in ("chat", "cowork", "code"):
		return "Mode"
	if label in ("artifacts", "artifact", "open artifact", "show artifact", "view artifact") or label.startswith(("open artifact:", "view artifact:")):
		return "Artifact"
	if label in ("attach files", "add files", "add files or photos", "attachments", "upload file", "upload files") or label.startswith(("attachment:", "download file:")):
		return "Attachment"
	if label in ("chats", "search chats", "search", "new chat", "projects", "recents", "recent chats"):
		return "Navigation"
	return ""
