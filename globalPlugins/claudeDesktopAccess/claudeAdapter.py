"""Conservative Claude accessibility classifiers, independent of NVDA.

Labels are candidate English patterns for beta testing, not captured live fixtures.
No conversation text is sent to a service or written to disk by this module.
"""

from collections import deque
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


def _ariaProperty(obj, name):
	attrs = getattr(obj, "IA2Attributes", None) or {}
	if name in attrs:
		return str(attrs[name])
	for pair in (_uiaProperty(obj, "currentAriaProperties") or "").split(";"):
		key, _, value = pair.partition("=")
		if key == name:
			return value
	return ""


def isCodeDocument(obj):
	if roleName(getattr(obj, "role", None)) != "document":
		return False
	value = getattr(obj, "value", "")
	if not value:
		try:
			# Chromium IA2 exposes the document URL through MSAA, even when NVDA's value is empty.
			value = obj.IAccessibleObject.accValue(0)
		except Exception:
			return False
	try:
		url = urlsplit(value or "")
		return url.scheme == "https" and url.hostname == "claude.ai" and (
			url.path == "/epitaxy" or url.path.startswith("/epitaxy/")
		)
	except ValueError:
		return False


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


def _compactModeChoice(obj):
	if roleName(getattr(obj, "role", None)) != "radiobutton":
		return ""
	group = getattr(obj, "parent", None)
	if _ariaRole(group) != "radiogroup" or not (
		"bg-[var(--cds-segmented-control-track)]" in nativeClasses(group)
		and _inside(group, "dframe-chrome-bar")
	):
		return ""
	first = getattr(group, "firstChild", None)
	second = getattr(first, "next", None)
	if (
		roleName(getattr(first, "role", None)) != "radiobutton"
		or roleName(getattr(second, "role", None)) != "radiobutton"
		or getattr(second, "next", None) is not None
	):
		return ""
	# The compact switcher presents the shared Chat/Cowork option before Code.
	return "home" if obj == first else "code" if obj == second else ""


def nativeMode(obj):
	if roleName(getattr(obj, "role", None)) != "radiobutton":
		return ""
	states = {roleName(state) for state in getattr(obj, "states", ())}
	if states.intersection(("checked", "selected")) and _compactModeChoice(obj) == "code":
		return "code"
	return ""


def nativeNavigationKind(obj):
	role = roleName(getattr(obj, "role", None))
	if role == "radiobutton" and _compactModeChoice(obj):
		return "Mode"
	if role not in ("button", "menubutton"):
		return ""
	if (
		{"absolute", "bottom-0", "start-0", "pe-[var(--cds-gap-xs)]"} <= nativeClasses(getattr(obj, "parent", None))
		and _inside(obj, "rounded-composer")
		and (role == "menubutton" or _ariaProperty(obj, "haspopup") == "menu")
	):
		return "Attachment"
	if "hit-row" in nativeClasses(obj) and _inside(obj, "dframe-sidebar"):
		shortcut = _ariaProperty(obj, "keyshortcuts") or _uiaProperty(obj, "currentAcceleratorKey") or getattr(obj, "keyboardShortcut", "")
		if str(shortcut).casefold() in ("ctrl+shift+k", "control+shift+k"):
			return "Navigation"
	return ""


_MESSAGE_CONTROL_ROLES = {
	"alert", "button", "checkbox", "combobox", "editabletext", "menu", "menubutton",
	"radiobutton", "statusbar", "togglebutton", "toolbar",
}


def _codeFeed(root, focus, deadline):
	panel = next((obj for obj in _ancestors(focus) if "epitaxy-chat-panel" in nativeClasses(obj)), None)
	pending = deque([(getattr(panel or root, "firstChild", None), 0)])
	feed = None
	seen = {}
	while pending and len(seen) < 300 and time.monotonic() < deadline:
		obj, depth = pending.popleft()
		if obj is None or id(obj) in seen:
			continue
		seen[id(obj)] = obj
		pending.appendleft((getattr(obj, "next", None), depth))
		role = roleName(getattr(obj, "role", None))
		if role not in ("grouping", "section", "region", "landmark", "unknown", "pane", "complementary", "application", "feed"):
			continue
		if _ariaRole(obj) == "feed":
			if feed is not None:
				return None
			feed = obj
		elif depth < 16:
			pending.append((getattr(obj, "firstChild", None), depth + 1))
	return feed if not pending else None


def _transcriptObjects(root, deadline, reverse=False, continuations=False):
	childAttr, siblingAttr = ("lastChild", "previous") if reverse else ("firstChild", "next")
	pending = [getattr(root, childAttr, None)]
	seen = {}
	while pending and len(seen) < 600 and time.monotonic() < deadline:
		obj = pending.pop()
		if obj is None or id(obj) in seen:
			continue
		seen[id(obj)] = obj
		pending.append(getattr(obj, siblingAttr, None))
		role = roleName(getattr(obj, "role", None))
		if role == "document" or role in _MESSAGE_CONTROL_ROLES:
			continue
		if role == "article" or (role in ("grouping", "section") and _ariaRole(obj) == "article"):
			yield obj, "article", True
			continue
		classes = nativeClasses(obj) if role != "statictext" else set()
		if "sr-only" in classes:
			continue
		if continuations and _messageAuthor(classes) == "assistant":
			yield obj, "continuation", True
			continue
		child = None if role in ("heading", "statictext") else getattr(obj, childAttr, None)
		yield obj, role, child is None
		if child is not None:
			pending.append(child)


def _messageAuthor(classes):
	if "group/bubble" in classes:
		return "user"
	if {"group/message-row", "select-text", "print:block"} <= classes:
		return "assistant"
	return ""


def _messageRecord(position, size, author, parts):
	body = " ".join("".join(parts).split())
	return (position, size, (author, body) if author and body else None)


def _latestMessages(records, limit, busy):
	messages = []
	expected = lastPosition = None
	for position, size, message in records:
		if not position.isdecimal():
			continue
		position = int(position)
		if expected is None:
			expected = lastPosition = int(size) if size.isdecimal() else position
		if position != expected:
			break
		if message is None:
			# A pending response can have an article before there is any readable body.
			if position != lastPosition or not busy:
				break
		else:
			messages.append(message)
			if len(messages) >= limit:
				break
		expected -= 1
	return tuple(reversed(messages))


def codeBufferMessages(fields, limit):
	"""Read positioned articles in the IA2 virtual buffer when it contains the Code feed."""
	stack = []
	records = []
	feedDepth = articleDepth = continuationDepth = blockedDepth = 0
	feeds = 0
	author, parts = "", []
	position = size = ""
	busy = False
	for item in fields:
		if isinstance(item, str):
			if (articleDepth or continuationDepth) and not blockedDepth:
				parts.append(item)
			continue
		command = getattr(item, "command", "")
		if command == "controlStart":
			field = item.field or {}
			role = roleName(field.get("role"))
			ariaRole = field.get("IAccessible2::attribute_xml-roles")
			classes = set(str(field.get("IAccessible2::attribute_class") or "").split())
			nested = role == "document" and ("document" in stack or feedDepth)
			stack.append(role)
			depth = len(stack)
			if blockedDepth:
				continue
			if nested or "sr-only" in classes or role in _MESSAGE_CONTROL_ROLES:
				blockedDepth = depth
			elif ariaRole == "feed":
				feeds += 1
				feedDepth = depth
				busy = str(field.get("IAccessible2::attribute_busy")).casefold() == "true"
			elif feedDepth and (role == "article" or ariaRole == "article"):
				if articleDepth:
					blockedDepth = depth
				else:
					if position:
						records.append(_messageRecord(position, size, author if author != "ambiguous" else "", parts))
					articleDepth = depth
					position = str(field.get("IAccessible2::attribute_posinset", ""))
					size = str(field.get("IAccessible2::attribute_setsize", ""))
					author, parts = "", []
			elif articleDepth and depth == articleDepth + 1:
				candidate = _messageAuthor(classes)
				if candidate and author and candidate != author:
					author = "ambiguous"
				elif candidate:
					author = candidate
			elif feedDepth and not (articleDepth or continuationDepth) and author == "assistant" and _messageAuthor(classes) == "assistant":
				# Large answers have continuation rows without their own article or position.
				continuationDepth = depth
				parts.append(" ")
		elif command == "controlEnd" and stack:
			depth = len(stack)
			role = stack.pop()
			if blockedDepth:
				if depth == blockedDepth:
					blockedDepth = 0
			elif depth == articleDepth:
				articleDepth = 0
			elif depth == continuationDepth:
				continuationDepth = 0
			elif depth == feedDepth:
				if position:
					records.append(_messageRecord(position, size, author if author != "ambiguous" else "", parts))
				position = ""
				feedDepth = 0
			elif (articleDepth or continuationDepth) and role in ("paragraph", "heading", "listitem"):
				parts.append(" ")
	return _latestMessages(reversed(records), limit, busy) if feeds == 1 else ()


def _readArticle(article, deadline):
	author, parts = "", []
	for obj, role, leaf in _transcriptObjects(article, deadline):
		if role == "article":
			continue
		if role in ("grouping", "section") and getattr(obj, "parent", None) == article:
			candidate = _messageAuthor(nativeClasses(obj))
			if candidate:
				if author and author != candidate:
					return "", ""
				author = candidate
		if leaf and role in ("statictext", "heading", "link", "paragraph"):
			body = " ".join(str(getattr(obj, "name", "") or "").split())
			if body:
				parts.append(body)
	return (author, " ".join(parts)) if time.monotonic() < deadline else ("", "")


def nativeArticleMessages(root, limit=10, focus=None):
	"""Read the contiguous end of Claude Code's native, possibly virtualized feed."""
	if limit < 1:
		return ()
	deadline = time.monotonic() + 1.0
	feed = _codeFeed(root, focus, deadline)
	if feed is None:
		return ()
	def records():
		fragments = []
		for obj, role, _leaf in _transcriptObjects(feed, deadline, reverse=True, continuations=True):
			if role == "continuation":
				_, text = _readArticle(obj, deadline)
				if text:
					fragments.append(text)
			elif role == "article":
				author, text = _readArticle(obj, deadline)
				if author == "assistant" and fragments:
					text = " ".join(part for part in (text, *reversed(fragments)) if part)
				yield (
					_ariaProperty(obj, "posinset"), _ariaProperty(obj, "setsize"),
					(author, text) if author and text else None,
				)
				fragments.clear()

	return _latestMessages(records(), limit, _ariaProperty(feed, "busy") == "true")


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
