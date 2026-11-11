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


def taskTimerSeconds(value):
	"""Parse the value of a verified elapsed-time control."""
	value = str(value or "").strip()
	if re.fullmatch(r"\d{1,4}(?::[0-5]\d){1,2}", value):
		seconds = 0
		for part in value.split(":"):
			seconds = 60 * seconds + int(part)
		return seconds
	units = re.fullmatch(
		r"(?:(\d{1,4})\s*h\s*)?(?:(\d{1,2})\s*(?:min|m)\s*)?(?:(\d{1,2})\s*s)?",
		value, re.IGNORECASE,
	)
	if units and any(units.groups()):
		hours, minutes, seconds = (int(part or 0) for part in units.groups())
		if minutes < 60 and seconds < 60:
			return hours * 3600 + minutes * 60 + seconds
	return None


def codeFeedTaskProgress(fields):
	"""Return the feed's native busy state and its uniquely identified timer value."""
	stack = []
	blockedDepth = feedDepth = timerDepth = 0
	busy = None
	timers = []
	parts = []
	timerName = ""
	for item in fields:
		if isinstance(item, str):
			if timerDepth and not blockedDepth:
				parts.append(item)
			continue
		command = getattr(item, "command", "")
		if command == "controlStart":
			field = item.field or {}
			role = roleName(field.get("role"))
			ariaRole = field.get("IAccessible2::attribute_xml-roles")
			blocked = role == "document" and bool(stack) or role == "article" or ariaRole == "article"
			stack.append(role)
			depth = len(stack)
			if blockedDepth:
				continue
			if blocked:
				blockedDepth = depth
			elif ariaRole == "feed":
				if busy is not None:
					return None, None
				busy = field.get("IAccessible2::attribute_busy") == "true"
				feedDepth = depth
			elif feedDepth and ariaRole == "timer":
				if timerDepth:
					return busy, None
				timerDepth = depth
				timerName = field.get("name", "")
				parts = []
		elif command == "controlEnd" and stack:
			depth = len(stack)
			if depth == blockedDepth:
				blockedDepth = 0
			elif depth == timerDepth:
				seconds = taskTimerSeconds("".join(parts))
				timers.append(taskTimerSeconds(timerName) if seconds is None else seconds)
				timerDepth = 0
			elif depth == feedDepth:
				feedDepth = 0
			stack.pop()
	return busy, timers[0] if len(timers) == 1 else None


def isCodeTaskFeed(obj):
	return _ariaRole(obj) == "feed"


def isTaskTimerObject(obj):
	return any(_ariaRole(item) == "timer" for item in (obj, *_ancestors(obj, 3)))


def nativeCodeFeedTaskProgress(root, focus=None):
	deadline = time.monotonic() + 1.0
	feed = _codeFeed(root, focus, deadline)
	if feed is None:
		return None, None
	busy = _ariaProperty(feed, "busy") == "true"
	timers = []
	for obj, role, _ in _taskFeedObjects(feed, deadline):
		if role in ("grouping", "section", "textframe", "timer") and _ariaRole(obj) == "timer":
			seconds = taskTimerSeconds(getattr(obj, "name", ""))
			if seconds is None:
				seconds = taskTimerSeconds(getattr(obj, "value", ""))
			if seconds is None:
				text = "".join(str(getattr(child, "name", "") or "") for child, role, leaf in _taskFeedObjects(obj, deadline) if leaf and role == "statictext")
				seconds = taskTimerSeconds(text)
			timers.append(seconds)
	return busy, timers[0] if len(timers) == 1 and time.monotonic() < deadline else None


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


_MESSAGE_CONTROL_ROLES = {
	"alert", "button", "checkbox", "combobox", "editabletext", "menu", "menubutton",
	"radiobutton", "statusbar", "togglebutton", "toolbar",
}



def _taskFeedObjects(root, deadline):
	childAttr, siblingAttr = "firstChild", "next"
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
		child = None if role in ("heading", "statictext") else getattr(obj, childAttr, None)
		yield obj, role, child is None
		if child is not None:
			pending.append(child)


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
