"""Conservative Claude accessibility classifiers, independent of NVDA.

Labels are candidate English patterns for beta testing, not captured live fixtures.
No conversation text is sent to a service or written to disk by this module.
"""

import re

from . import strings


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
		return strings.MODE
	if label in ("artifacts", "artifact", "open artifact", "show artifact", "view artifact") or label.startswith(("open artifact:", "view artifact:")):
		return strings.ARTIFACT
	if label in ("attach files", "add files", "add files or photos", "attachments", "upload file", "upload files") or label.startswith(("attachment:", "download file:")):
		return strings.ATTACHMENT
	if label in ("chats", "search chats", "search", "new chat", "projects", "recents", "recent chats"):
		return strings.NAVIGATION
	return ""
