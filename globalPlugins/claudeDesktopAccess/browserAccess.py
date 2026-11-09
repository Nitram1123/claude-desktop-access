"""Pure classification and presentation helpers for Claude's embedded browser."""

import re
from collections import Counter
from urllib.parse import urlsplit

from . import strings


_CONTAINER_PATTERN = re.compile(
	r"\b(?:browser|web\s*view|webview|web preview|website preview)\b",
	re.IGNORECASE,
)
_GENERIC_TITLES = {
	"browser", "browser content", "browser page", "embedded browser", "web preview", "web view", "webview",
}
NAVIGATOR_CATEGORY_ORDER = (
	"controls", "headings", "landmarks", "links", "buttons", "formFields", "tables",
)
_LANDMARK_ROLES = {
	"banner", "complementary", "contentinfo", "form", "landmark", "main", "navigation", "region", "search",
}
_BUTTON_ROLES = {"button", "checkbutton", "menuitem", "togglebutton"}
_FORM_FIELD_ROLES = {
	"checkbox", "combobox", "edit", "editabletext", "listbox", "radiobutton", "slider", "spinbutton", "switch",
}
_TABLE_ROLES = {"grid", "table", "treegrid"}
_SNAPSHOT_TEXT_ROLES = {
	"blockquote", "caption", "cell", "document", "figure", "heading", "link", "list", "listitem", "paragraph",
	"section", "statictext", "textframe",
} | _BUTTON_ROLES | _FORM_FIELD_ROLES | _LANDMARK_ROLES | _TABLE_ROLES


def normalizedText(value):
	return " ".join(str(value or "").split())


def isEmbeddedBrowserContainerText(*values):
	"""Return whether accessible container text explicitly identifies a browser view."""
	text = " ".join(normalizedText(value) for value in values if normalizedText(value))
	return bool(_CONTAINER_PATTERN.search(text))


def isEmbeddedBrowserContainerRole(roleName):
	"""Exclude browser-launch controls while tolerating unknown Chromium container roles."""
	role = normalizedText(roleName).casefold()
	return role not in {
		"button", "checkbutton", "combobox", "edit", "editabletext", "link", "menu", "menuitem",
	}


def isEmbeddedBrowserDocumentStructure(*roleNames):
	"""Recognize a web document nested inside Claude's outer Chromium document."""
	roles = tuple(normalizedText(role).casefold() for role in roleNames)
	return sum(role == "document" for role in roles) >= 2


def embeddedBrowserControlKind(name, roleName=""):
	"""Classify conservatively named embedded-browser controls."""
	text = normalizedText(name).casefold()
	role = normalizedText(roleName).casefold()
	if text in ("back", "go back", "previous page"):
		return "back"
	if text in ("forward", "go forward", "next page"):
		return "forward"
	if text in ("reload", "reload page", "refresh", "refresh page"):
		return "reload"
	if text in ("stop loading", "stop page loading"):
		return "stop"
	if text in (
		"address", "address bar", "address and search bar", "search or enter address",
		"search or type url", "url",
	):
		return "address"
	if text in (
		"open externally", "open in browser", "open in default browser",
		"open in external browser", "open in system browser",
	):
		return "external"
	if text in ("close browser", "close browser view", "close preview", "close web view"):
		return "close"
	if role == "document":
		return "content"
	return ""


def embeddedBrowserTitle(name):
	"""Return a bounded useful page title, excluding generic browser container names."""
	title = normalizedText(name)
	if not title or title.casefold() in _GENERIC_TITLES:
		return ""
	return title[:200]


def embeddedBrowserProgress(*values):
	"""Return ``(identity, percent, bucket)`` for browser loading progress."""
	parts = tuple(normalizedText(value) for value in values if normalizedText(value))
	text = " ".join(parts)
	if not text:
		return None
	match = re.search(r"(?<!\d)(100|[0-9]{1,2})\s*(?:%|percent\b)", text, re.IGNORECASE)
	lower = text.casefold()
	hasLoadingState = re.search(r"\b(?:loading|opening page|navigating)\b", lower) is not None
	directPercent = next(
		(int(part) for part in parts if re.fullmatch(r"100|[0-9]{1,2}", part)),
		None,
	)
	if not match and directPercent is None and not hasLoadingState:
		return None
	percent = int(match.group(1)) if match else directPercent
	bucket = None if percent is None else (
		100 if percent >= 100 else (0 if percent == 0 else max(10, (percent // 10) * 10))
	)
	identity = re.sub(r"(?<!\d)(?:100|[0-9]{1,2})\s*(?:%|percent\b)", "", lower)
	if directPercent is not None:
		identity = " ".join(part for part in identity.split() if part != str(directPercent))
	identity = " ".join(identity.split()) or "embedded browser"
	return identity[:160], percent, bucket


def browserPageAddress(*values):
	"""Return the first safe HTTP(S) address exposed by the browser."""
	for value in values:
		text = normalizedText(value)
		for match in re.finditer(r"https?://[^\s<>\"']+", text, re.IGNORECASE):
			candidate = match.group(0).rstrip(".,);]}")
			try:
				parsed = urlsplit(candidate)
			except ValueError:
				continue
			if parsed.scheme.casefold() in ("http", "https") and parsed.hostname:
				return candidate[:2048]
	return ""


def browserAddressDomain(address):
	"""Return a non-sensitive host label suitable for page summaries."""
	try:
		return str(urlsplit(address).hostname or "")[:253]
	except ValueError:
		return ""


def browserNavigatorCategory(roleName, controlKind=""):
	"""Classify a page object into one navigator list category."""
	role = normalizedText(roleName).casefold()
	kind = normalizedText(controlKind).casefold()
	# "content" identifies the page document itself, not a browser chrome control.
	if kind and kind != "content":
		return "controls"
	if role == "heading":
		return "headings"
	if role in _LANDMARK_ROLES:
		return "landmarks"
	if role == "link":
		return "links"
	if role in _BUTTON_ROLES:
		return "buttons"
	if role in _FORM_FIELD_ROLES:
		return "formFields"
	if role in _TABLE_ROLES:
		return "tables"
	return ""


def browserNavigatorItemLabel(category, name, roleName="", value="", level=None, states=(), translate=lambda text: text):
	"""Return a concise, bounded label for one navigator result."""
	role = normalizedText(roleName).casefold()
	label = normalizedText(name)
	if not label:
		fallbacks = {
			"controls": translate(strings.UNNAMED_BROWSER_CONTROL),
			"headings": translate(strings.UNNAMED_HEADING),
			"landmarks": translate(strings.UNNAMED_LANDMARK),
			"links": translate(strings.UNNAMED_LINK),
			"buttons": translate(strings.UNNAMED_BUTTON),
			"formFields": translate(strings.UNNAMED_FORM_FIELD),
			"tables": translate(strings.UNNAMED_TABLE),
		}
		label = fallbacks.get(category, translate(strings.UNNAMED_ITEM))
	roleLabels = {
		"controls": translate(strings.BROWSER_CONTROL),
		"headings": translate(strings.HEADING),
		"landmarks": translate(strings.LANDMARK),
		"links": translate(strings.LINK),
		"buttons": translate(strings.BUTTON),
		"formFields": translate(strings.FORM_FIELD),
		"tables": translate(strings.TABLE),
	}
	roleLabel = roleLabels.get(category, normalizedText(role) or translate(strings.ITEM))
	if category == "headings" and level not in (None, ""):
		roleLabel = translate(strings.HEADING_LEVEL_LEVEL).format(level=level)
	stateLabels = {
		"checked": translate(strings.CHECKED), "collapsed": translate(strings.COLLAPSED),
		"expanded": translate(strings.EXPANDED), "pressed": translate(strings.PRESSED),
		"required": translate(strings.REQUIRED), "selected": translate(strings.SELECTED),
		"unavailable": translate(strings.UNAVAILABLE), "visited": translate(strings.VISITED),
	}
	stateText = [stateLabels[state] for state in sorted(set(states)) if state in stateLabels]
	parts = [label, roleLabel]
	cleanValue = normalizedText(value)
	if cleanValue and cleanValue.casefold() not in label.casefold() and role in ("progressbar",):
		parts.append(cleanValue[:100])
	parts.extend(stateText)
	return ", ".join(part for part in parts if part)[:320]


def browserNavigatorSignature(category, roleName, name, occurrence=1):
	"""Return a stable, text-only location key without retaining page content values."""
	signature = "|".join((
		normalizedText(category).casefold(), normalizedText(roleName).casefold(), normalizedText(name).casefold(),
	))
	try:
		occurrence = max(1, int(occurrence))
	except (TypeError, ValueError):
		occurrence = 1
	if occurrence > 1:
		suffix = f"|{occurrence}"
		return f"{signature[:600 - len(suffix)]}{suffix}"
	return signature[:600]


def browserNavigatorMatches(item, category="all", query=""):
	"""Return whether a navigator item matches the selected category and search text."""
	if category not in ("", "all") and item.get("category") != category:
		return False
	needle = normalizedText(query).casefold()
	return not needle or needle in normalizedText(item.get("label", "")).casefold()


def browserPageIdentity(title, address):
	"""Return a bounded page key without query strings, fragments, or credentials."""
	pageTitle = normalizedText(title).casefold()
	address = normalizedText(address)
	try:
		if address:
			parsed = urlsplit(address)
			host = parsed.hostname or ""
			port = parsed.port
			addressKey = f"{host}{f':{port}' if port is not None else ''}{parsed.path or '/'}".casefold()
		else:
			addressKey = ""
	except ValueError:
		addressKey = ""
	if not pageTitle and not addressKey:
		return ""
	return f"{pageTitle}|{addressKey}"[:700]


def browserPageSummary(title, address, items, loadingPercent=None, truncated=False, translate=lambda text: text):
	"""Summarize page structure without exposing a full address or page text."""
	counts = Counter(item.get("category", "") for item in items)
	pageTitle = normalizedText(title) or translate(strings.UNTITLED_PAGE)
	domain = browserAddressDomain(address) or translate(strings.ADDRESS_UNAVAILABLE)
	parts = [
		translate(strings.BROWSER_PAGE_TITLE).format(title=pageTitle),
		translate(strings.DOMAIN_NAME).format(domain=domain),
		translate(strings.COUNT_BROWSER_CONTROLS).format(count=counts["controls"]),
		translate(strings.COUNT_HEADINGS).format(count=counts["headings"]),
		translate(strings.COUNT_LANDMARKS).format(count=counts["landmarks"]),
		translate(strings.COUNT_LINKS).format(count=counts["links"]),
		translate(strings.COUNT_BUTTONS).format(count=counts["buttons"]),
		translate(strings.COUNT_FORM_FIELDS).format(count=counts["formFields"]),
		translate(strings.COUNT_TABLES).format(count=counts["tables"]),
	]
	if loadingPercent is not None:
		parts.append(
			translate(strings.LOADED) if loadingPercent >= 100
			else translate(strings.LOADING_PERCENT_PERCENT).format(percent=loadingPercent)
		)
	if truncated:
		parts.append(translate(strings.SCAN_LIMIT_REACHED))
	return ". ".join(parts) + "."


def browserSnapshotLine(roleName, name, value="", level=None, translate=lambda text: text):
	"""Return one useful accessible-text snapshot line, or an empty string."""
	role = normalizedText(roleName).casefold()
	name = normalizedText(name)
	if role not in _SNAPSHOT_TEXT_ROLES or not name or name.casefold() in _GENERIC_TITLES:
		return ""
	category = browserNavigatorCategory(role)
	if category:
		return browserNavigatorItemLabel(category, name, role, level=level, translate=translate)
	return name[:500]


def browserSnapshotText(title, address, lines, truncated=False, translate=lambda text: text):
	"""Build an in-memory readable snapshot from already exposed accessibility text."""
	pageTitle = normalizedText(title) or translate(strings.UNTITLED_PAGE)
	domain = browserAddressDomain(address) or translate(strings.ADDRESS_UNAVAILABLE)
	uniqueLines = []
	previous = ""
	for line in lines:
		line = normalizedText(line)
		if not line or line == previous:
			continue
		uniqueLines.append(line)
		previous = line
	parts = [
		translate(strings.PAGE_TITLE).format(title=pageTitle),
		translate(strings.DOMAIN_NAME).format(domain=domain),
		"",
	]
	parts.extend(uniqueLines or [translate(strings.NO_READABLE_PAGE_TEXT_WAS_EXPOSED_BY_CLAUDE)])
	if truncated:
		parts.extend(("", translate(strings.THE_SNAPSHOT_ENDED_AT_THE_SAFE_SCAN_LIMIT)))
	return "\n".join(parts)
