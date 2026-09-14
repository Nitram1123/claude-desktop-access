"""NVDA-independent parsing and privacy helpers for Code activity."""

import json
import math
import re
from collections import deque
from pathlib import Path


def mergeSupportedAppNames(value, requiredNames=("claude",)):
	result = []
	for raw in (*requiredNames, *str(value or "").split(",")):
		name = str(raw).strip().casefold()
		if name and name not in ("chatgpt", "codex", "code") and name not in result:
			result.append(name)
	return ",".join(result)


def conversationModeFromDocumentNames(documentNames):
	"""Identify one top-level Claude or Code conversation document.

	Nested web content contains two document ancestors and is deliberately rejected,
	so activity on an embedded browser page is not mistaken for conversation status.
	"""
	names = tuple(" ".join(str(name or "").casefold().split()) for name in documentNames)
	if len(names) != 1:
		return ""
	return names[0] if names[0] in ("claude", "code") else ""


def conversationModeFromSwitchLabel(label):
	"""Read the active product mode from Claude's authoritative switch control."""
	text = " ".join(str(label or "").casefold().split())
	match = re.fullmatch(r"switch mode,\s*current mode:\s*(claude|code)", text)
	return match.group(1) if match else ""


def chatHistorySnapshotDecision(
	modeAge, settleSeconds, titles, otherTitles, otherCurrent,
	pendingTitles, pendingAge, confirmSeconds,
):
	"""Decide when a mode-specific sidebar snapshot is safe to publish."""
	try:
		modeAge = float(modeAge)
	except (TypeError, ValueError, OverflowError):
		modeAge = 0.0
	try:
		pendingAge = float(pendingAge)
	except (TypeError, ValueError, OverflowError):
		pendingAge = 0.0
	if modeAge < max(0.0, float(settleSeconds)):
		return "settle"
	titles = tuple(titles)
	otherTitles = tuple(otherTitles)
	if titles and otherCurrent and titles == otherTitles:
		return "otherMode"
	if pendingTitles is None or tuple(pendingTitles) != titles:
		return "confirm"
	if pendingAge < max(0.0, float(confirmSeconds)):
		return "confirm"
	return "publish"






def modeSpecificRecentChatTitles(mode, unifiedTitles, activeCodeTitles):
	"""Partition Claude's unified Recents list into Claude chats or Code tasks."""
	mode = str(mode or "").casefold()
	if mode not in ("claude", "code"):
		return ()
	codeKeys = {
		" ".join(str(title or "").split()).casefold()
		for title in activeCodeTitles
		if str(title or "").strip()
	}
	result = []
	seen = set()
	for rawTitle in unifiedTitles:
		title = " ".join(str(rawTitle or "").split())
		key = title.casefold()
		if not title or key in seen:
			continue
		isCode = key in codeKeys
		if (mode == "code") == isCode:
			seen.add(key)
			result.append(title)
	return tuple(result)




def uniqueThreadLabels(entries):
	"""Give duplicate archived task titles distinct labels without losing their IDs."""
	result = []
	counts = {}
	used = set()
	for threadId, title in entries:
		base = " ".join(str(title or "").split()) or f"Archived task {threadId}"
		count = counts.get(base, 0) + 1
		label = base if count == 1 else f"{base} ({count})"
		while label in used:
			count += 1
			label = f"{base} ({count})"
		counts[base] = count
		used.add(label)
		result.append((threadId, label))
	return tuple(result)




def repairConfigurationValues(values, choiceDefaults, numericDefaults, booleanDefaults=(), stringDefaults=()):
	"""Repair imported or migrated configuration values in place."""
	repaired = []
	for key, (choices, default) in choiceDefaults.items():
		if values.get(key) not in choices:
			values[key] = default
			repaired.append(key)
	for key, (minimum, maximum, default) in numericDefaults.items():
		original = values.get(key, default)
		try:
			value = default if isinstance(original, bool) else int(original)
		except (TypeError, ValueError, OverflowError):
			value = default
		if value < minimum or value > maximum:
			value = default
		if original != value:
			repaired.append(key)
		values[key] = value
	for key, default in booleanDefaults:
		original = values.get(key, default)
		if isinstance(original, bool):
			value = original
		elif original in (0, 1):
			value = bool(original)
		elif isinstance(original, str) and original.strip().casefold() in ("true", "yes", "on", "1", "false", "no", "off", "0"):
			value = original.strip().casefold() in ("true", "yes", "on", "1")
		else:
			value = default
		if original != value:
			repaired.append(key)
		values[key] = value
	for key, default in stringDefaults:
		original = values.get(key, default)
		value = original.strip() if isinstance(original, str) else default
		if not value and default:
			value = default
		if original != value:
			repaired.append(key)
		values[key] = value
	return tuple(dict.fromkeys(repaired))


def chatTitleMatches(selectedTitle, buttonName, titleFoundInsideButton=False):
	"""Validate a sidebar title, including Chromium's unnamed-button structure."""
	selected = " ".join(str(selectedTitle or "").casefold().split())
	button = " ".join(str(buttonName or "").casefold().split())
	return bool(selected and (selected == button or (titleFoundInsideButton and not button)))


def isChatOptionsLabel(label):
	"""Recognize Chromium labels for a conversation's custom options button."""
	label = " ".join(str(label or "").casefold().split())
	return bool(
		label in ("more", "options", "chat options", "conversation options", "open conversation options")
		or label.endswith((" chat options", " conversation options"))
	)


def chatActionMatches(action, label):
	"""Match only the exposed action buttons for a focused sidebar chat."""
	action = str(action or "").strip().casefold()
	label = " ".join(str(label or "").casefold().split())
	if action == "pin":
		return label in ("pin chat", "unpin chat")
	if action == "archive":
		return label == "archive chat"
	return False


def voiceControlKind(label):
	"""Classify only native Claude voice and microphone control labels."""
	label = " ".join(str(label or "").casefold().split())
	if label in ("start voice chat", "start voice mode"):
		return "start"
	if label in ("stop voice chat", "end voice chat", "leave voice mode", "exit voice mode"):
		return "stop"
	if label in ("mute microphone", "mute mic"):
		return "mute"
	if label in ("unmute microphone", "unmute mic"):
		return "unmute"
	return ""


def isPermissionPromptText(text):
	"""Identify permission/approval dialog wording without matching ordinary settings."""
	text = " ".join(str(text or "").casefold().split())
	return bool(
		any(phrase in text for phrase in (
			"permission required", "approval required", "requires your approval",
			"needs your approval", "allow this command", "allow code", "approve this",
		))
		or ("permission" in text and any(word in text for word in ("allow", "deny", "approve", "reject")))
	)


def isPermissionDecisionLabel(label):
	"""Recognize a permission dialog decision control; focus only, never activate it."""
	label = " ".join(str(label or "").casefold().split())
	return bool(label and any(word in label for word in ("allow", "approve", "deny", "reject")))


def usageLimitNotice(text, translate=lambda text: text):
	"""Return a concise actionable notice for an exhausted Claude usage allowance.

	The match deliberately requires exhaustion wording as well as ``usage limit``
	or ``credits``. This keeps help text and the normal usage-settings page from
	being mistaken for a terminal task error.
	"""
	text = re.sub(
		r"(?<=[a-z0-9%])(?=[A-Z])", " ",
		str(text or "").replace("\u2019", "'"),
	)
	text = " ".join(text.split())
	lower = text.casefold()
	remaining = re.search(r"\b(?P<percent>\d{1,3}(?:\.\d+)?)\s*%\s*usage\s+remaining", lower)
	consumed = re.search(r"\b(?P<percent>\d{1,3}(?:\.\d+)?)\s*%\s*usage\s+consumed", lower)
	percentageExhausted = bool(
		(remaining and float(remaining.group("percent")) <= 0)
		or (consumed and float(consumed.group("percent")) >= 100)
		or "no usage remaining" in lower
	)
	usageLimitReached = bool(
		percentageExhausted
		or "usage limit exceeded" in lower
		or re.search(r"\byou(?:'ve| have)\s+(?:hit|reached)\s+(?:your|the)\s+(?:\w+\s+){0,3}usage limit\b", lower)
		or re.search(r"\b(?:you are|you're)\s+out of\s+(?:claude |code )?usage\b", lower)
	)
	creditsExhausted = bool(
		("credit" in lower and re.search(
			r"\b(?:out of|not enough|insufficient|no)\s+(?:usage )?credits?\b", lower,
		))
		or re.search(r"\b0(?:\.0+)?\s+credits?\s+remaining\b", lower)
	)
	if not (usageLimitReached or creditsExhausted):
		return ""

	options = []
	if re.search(r"\bupgrade\s+(?:your\s+plan\s+)?to\s+pro\b", lower):
		options.append(translate("upgrade to Pro"))
	elif re.search(r"\bupgrade(?:\s+(?:your\s+)?plan)?\b", lower):
		options.append(translate("upgrade your plan"))
	if re.search(r"\b(?:add|buy|purchase)(?:\s+some)?(?:\s+more)?\s+credits?\b", lower):
		options.append(translate("purchase more credits in Claude usage settings"))
	retry = re.search(
		r"\btry again\s+(?P<when>(?:at|in|after)\s+[^.!?]+)",
		text,
		flags=re.IGNORECASE,
	)
	if retry:
		options.append(translate("try again {when}").format(when=retry.group("when").strip()))
	else:
		reset = re.search(
			r"\b(?:usage|limit)\s+resets?\s+(?P<when>(?:at|in|after)\s+[^.!?]+)",
			text,
			flags=re.IGNORECASE,
		)
		if not reset:
			reset = re.search(
				r"\bnext reset\s+(?:is\s+)?(?P<when>(?:on|at|in|after)\s+.*?)"
				r"(?=\s+(?:usage consumed|add credits|buy credits|purchase credits|upgrade)\b|[.!?\u00b7]|$)",
				text,
				flags=re.IGNORECASE,
			)
		if reset:
			options.append(translate("try again {when}").format(when=reset.group("when").strip()))

	message = translate("Usage limit reached")
	if options:
		if len(options) == 1:
			actionText = options[0]
		elif len(options) == 2:
			actionText = translate("{first} or {last}").format(first=options[0], last=options[1])
		else:
			actionText = translate("{first}, {middle}, or {last}").format(
				first=options[0], middle=", ".join(options[1:-1]), last=options[-1],
			)
		return translate("{message}. You can {actions}.").format(message=message, actions=actionText)
	return translate("{message}. Check Claude usage settings for reset details.").format(message=message)


def pluginInstallProgress(text, step=10):
	"""Parse and bucket a Claude plug-in installation progress description."""
	text = " ".join(str(text or "").split())
	lower = text.casefold()
	if "install" not in lower or not any(word in lower for word in ("plugin", "plug-in", "connector", "extension")):
		return None
	match = re.search(r"(?<!\d)(100|[1-9]?\d)\s*%", lower)
	if not match:
		match = re.search(r"(?<!\d)(100|[1-9]?\d)\s+percent\b", lower)
	percent = int(match.group(1)) if match else None
	if percent is None and re.search(r"\b(?:complete|completed|finished|installed|succeeded)\b", lower):
		percent = 100
	step = max(1, min(100, int(step)))
	bucket = None if percent is None else (100 if percent == 100 else (percent // step) * step)
	identity = re.sub(r"(?<!\d)(100|[1-9]?\d)\s*(?:%|percent\b)", "", lower)
	identity = re.sub(r"\bin\s+progress\b", "", identity)
	identity = re.sub(
		r"\b(?:install|installing|installation|installed|progress|complete|completed|finished|succeeded)\b",
		"", identity,
	)
	identity = " ".join(identity.split()) or "plugin installation"
	return identity, percent, bucket


def pluginProgressBusyTransition(currentBusy, ownsBusyState, complete):
	"""Keep installation completion from clearing an unrelated active Code task."""
	currentBusy = bool(currentBusy)
	ownsBusyState = bool(ownsBusyState)
	if complete:
		return (False, False) if ownsBusyState else (currentBusy, False)
	return True, bool(ownsBusyState or not currentBusy)


def pendingChatTitle(title, elapsed, timeout=10.0):
	"""Discard a stale history selection before a later unrelated document switch."""
	title = " ".join(str(title or "").split())
	return title if title and 0 <= float(elapsed) <= float(timeout) else ""


def formatElapsedDuration(totalSeconds, translate=lambda text: text):
	"""Format elapsed seconds as compact, speech-friendly hours, minutes, and seconds."""
	totalSeconds = max(0, int(round(float(totalSeconds or 0))))
	hours, remainder = divmod(totalSeconds, 3600)
	minutes, seconds = divmod(remainder, 60)
	parts = []
	if hours:
		parts.append(translate("{count} hour" if hours == 1 else "{count} hours").format(count=hours))
	if minutes:
		parts.append(translate("{count} minute" if minutes == 1 else "{count} minutes").format(count=minutes))
	if seconds or not parts:
		parts.append(translate("{count} second" if seconds == 1 else "{count} seconds").format(count=seconds))
	return " ".join(parts)


def currentActivitySummary(
	busy, category, latestMessage, elapsed=0, translate=lambda text: text, agentName="Code",
):
	"""Return useful current activity even during a gap in exposed commentary."""
	agentName = " ".join(str(agentName or "Code").split()) or "Code"
	latestMessage = " ".join(str(latestMessage or "").split())
	if latestMessage:
		return latestMessage
	if not busy:
		return f"{agentName} is idle"
	names = {
		"command": "running commands", "build": "running tests", "tool": "using tools",
		"search": "searching", "file": "working with files", "thinking": "thinking",
		"working": "working", "commentary": "working",
	}
	activity = names.get(str(category or "").casefold(), "working")
	elapsed = max(0, int(elapsed or 0))
	return f"{agentName} is still {activity}" + (f", {formatElapsedDuration(elapsed, translate)}" if elapsed else "")


def backgroundActivityName(category, latestMessage=""):
	"""Return an accurate activity name for recurring background announcements."""
	category = str(category or "").casefold()
	text = " ".join(str(latestMessage or "").casefold().split())
	if any(word in text for word in ("finished", "complete", "updated", "done")):
		return "Processing"
	detectedCategory = statusDetails(latestMessage)[0]
	if detectedCategory and detectedCategory != "completion":
		category = detectedCategory
	if category == "file":
		if any(word in text for word in ("editing", "writing", "creating", "updating", "modifying", "patching")):
			return "Editing code"
		if any(word in text for word in ("checking", "reading", "inspecting", "reviewing")):
			return "Checking files"
		return "File operations"
	return {
		"command": "Command", "build": "Tests", "tool": "Tool operation",
		"search": "Web search", "thinking": "Thinking", "working": "Processing",
	}.get(category, "Work")


def looksLikeCodeConversation(text):
	"""Distinguish a conversation document from settings and transient viewers."""
	text = " ".join(str(text or "").casefold().split())
	return any(marker in text for marker in (
		"reply to claude", "ask claude", "message claude", "send a message",
	))


def looksLikeBlankCodeConversation(text):
	"""Recognize a new blank conversation without mistaking a buffer refresh for one."""
	text = " ".join(str(text or "").casefold().split())
	if not looksLikeCodeConversation(text):
		return False
	return not (
		re.search(r"\buser message\s+\d+\b", text)
		or "response complete:" in text
		or "claude said:" in text
		or "you said:" in text
	)


def chatMessageShortcutIndex(keyName):
	"""Map Control+1 through Control+0 to newest-first chat message positions 1 through 10."""
	keyName = str(keyName or "").strip()
	if keyName == "0":
		return 10
	if keyName in tuple(str(number) for number in range(1, 10)):
		return int(keyName)
	return None


def isChatMessageTrailingUiText(text):
	"""Identify Claude chrome that follows, but is not part of, a conversation turn."""
	text = " ".join(str(text or "").strip().casefold().split())
	if not text:
		return False
	if re.fullmatch(r"(?:(?:today|yesterday)\s+)?\d{1,2}:\d{2}(?:\s*[ap]m)?", text):
		return True
	if re.fullmatch(r"(?:working|worked|thinking)\s+for\s+\d+(?:\s*[hms]|\s*(?:hours?|minutes?|seconds?))(?:\s+\d+(?:\s*[hms]|\s*(?:hours?|minutes?|seconds?)))*", text):
		return True
	if re.fullmatch(r"edited\s+\d+\s+files?", text):
		return True
	if re.fullmatch(r"step\s+\d+\s*/\s*\d+", text):
		return True
	return text in {
		"good response", "bad response", "copy", "copy message", "retry", "edit message",
		"share", "more", "change permissions", "review", "review changed files", "undo",
		"open chat", "outputs", "sources", "view all", "thinking", "working",
		"running command", "reading finished", "command finished", "stop",
		"add files and more", "full access",
	}


def chatMessagesFromTokens(tokens, limit=10):
	"""Build bounded conversation turns from accessibility-order speaker and text tokens."""
	try:
		limit = max(1, int(limit))
	except (TypeError, ValueError, OverflowError):
		limit = 10
	messages = deque(maxlen=limit)
	currentSpeaker = ""
	parts = []

	def finish():
		nonlocal currentSpeaker, parts
		# Preserve whitespace supplied by the virtual buffer. Chromium can split a
		# single word across adjacent text nodes (for example, "L" and "ooks").
		text = " ".join("".join(parts).split())
		if currentSpeaker and text:
			item = (currentSpeaker, text)
			if not messages or messages[-1] != item:
				messages.append(item)
		parts = []

	for token in tokens or ():
		try:
			kind, value = token
		except (TypeError, ValueError):
			continue
		kind = str(kind or "").strip().casefold()
		rawValue = str(value or "")
		value = " ".join(rawValue.split())
		if kind == "speaker" and value in ("user", "assistant"):
			# Chromium may expose the same marker as both a field name and text.
			if value != currentSpeaker or parts:
				finish()
			currentSpeaker = value
		elif kind == "text" and currentSpeaker and value:
			if value.casefold().startswith("response complete:"):
				# Chromium also exposes a hidden flattened copy of the response; the
				# normal Claude text nodes immediately following it are authoritative.
				continue
			if isChatMessageTrailingUiText(value):
				finish()
				currentSpeaker = ""
			elif value.casefold() not in ("you said:", "claude said:", "response complete"):
				parts.append(rawValue)
		elif kind == "end":
			finish()
			currentSpeaker = ""
	finish()
	return tuple(messages)


class AnnouncementHistory:
	"""A bounded, in-memory announcement history with review navigation."""

	def __init__(self, limit=20):
		self._items = deque(maxlen=limit)
		self._index = -1

	def add(self, message):
		message = str(message or "").strip()
		if not message or (self._items and self._items[-1] == message):
			return False
		self._items.append(message)
		self._index = len(self._items) - 1
		return True

	def move(self, offset):
		if not self._items:
			return ""
		self._index = min(max(self._index + offset, 0), len(self._items) - 1)
		return self._items[self._index]

	def clear(self):
		self._items.clear()
		self._index = -1

	def items(self):
		return tuple(self._items)

	def __len__(self):
		return len(self._items)

CATEGORY_SETTING = {"thinking": "announceThinking", "working": "announceWorking", "command": "announceCommands", "search": "announceSearches", "file": "announceFiles", "build": "announceBuilds", "tool": "announceTools", "completion": "announceCompletions", "attention": "announceAttention", "other": "announceOther", "commentary": "announceCommentary"}

TONE_PATTERNS = {
	"thinking": ((392, 45), (440, 45)),
	"working": ((440, 45),),
	"command": ((523, 55), (659, 65)),
	"search": ((659, 50), (784, 60)),
	"file": ((494, 45), (587, 55)),
	"build": ((587, 55), (698, 70)),
	"tool": ((698, 55),),
	"completion": ((659, 55), (784, 55), (988, 85)),
	"failure": ((659, 65), (523, 65), (392, 100)),
	"other": ((392, 50),),
	"commentary": ((554, 45),),
	"attention": ((784, 70), (988, 100)),
	"backgroundPulse1": ((392, 35), (523, 55)),
	"backgroundPulse2": ((440, 35), (587, 55)),
	"monitoringActive": ((523, 45), (784, 65)),
	"monitoringInactive": ((587, 45), (392, 70)),
	"submission": ((523, 40), (659, 50), (784, 65)),
}


def tonePattern(category, message=""):
	"""Return a short earcon pattern for a progress category and message."""
	message = str(message or "").lower()
	if category == "completion" and any(word in message for word in ("fail", "error", "cancel")):
		return TONE_PATTERNS["failure"]
	return TONE_PATTERNS.get(category, TONE_PATTERNS["other"])


def soundKey(category, message=""):
	"""Return the bundled click-earcon name for a category and message."""
	message = str(message or "").lower()
	if category == "completion" and any(word in message for word in ("fail", "error", "cancel")):
		return "failure"
	return category if category in TONE_PATTERNS else "other"


def userMessageNumber(label):
	"""Return the number from a Code 'Jump to user message' control."""
	match = re.search(r"(?i)\bjump to user message\s+(\d+)\b", str(label or ""))
	return int(match.group(1)) if match else None


def userMessageSubmissionTransition(previousNumber, currentNumber):
	"""Detect a newly posted user message without firing on the initial baseline."""
	if currentNumber is None:
		return previousNumber, False
	return currentNumber, previousNumber is not None and currentNumber > previousNumber


def confirmedUserMessageSubmission(pendingIncrease, messageNumberIncreased, stopControlVisible):
	"""Retain and confirm a message-count increase once active work is visible.

	Loading a different Code task can expose a larger historical user-message
	count.  The active Stop/Cancel control distinguishes that navigation change
	from a request that Claude is currently processing. Retaining an increase
	also covers Chromium exposing the new message one scan before the Stop control.
	"""
	pending = bool(pendingIncrease or messageNumberIncreased)
	confirmed = bool(pending and stopControlVisible)
	return False if confirmed else pending, confirmed


def isStopControlLabel(label):
	return " ".join(str(label or "").casefold().split()) in (
		"stop", "stop generating", "stop response", "stop responding", "stop generation", "stop task", "cancel task", "cancel request",
	)


def stopControlTransition(previousVisible, currentVisible):
	"""Detect disappearance of a previously visible task stop control."""
	currentVisible = bool(currentVisible)
	return currentVisible, bool(previousVisible and not currentVisible)


def shouldSuppressDuplicate(message, previousMessage, elapsedSeconds, windowSeconds=1.5):
	"""Suppress rapid duplicate accessibility events without hiding later updates."""
	return bool(message == previousMessage and float(elapsedSeconds) < float(windowSeconds))


def semanticStatusKey(message):
	"""Collapse cosmetic wording differences into a stable activity key."""
	text = " ".join(str(message or "").casefold().split())
	replacements = (
		("editing file", "editing code"), ("editing source", "editing code"),
		("reading files", "checking files"), ("reading", "checking files"),
		("file edit finished", "file updated"), ("changes finished", "file updated"),
		("build or test still running", "tests still running"),
	)
	for old, new in replacements:
		if text.startswith(old):
			text = new + text[len(old):]
	return text


def shouldSuppressSemanticDuplicate(message, previousMessage, elapsedSeconds, windowSeconds=1.5):
	return bool(
		semanticStatusKey(message)
		and semanticStatusKey(message) == semanticStatusKey(previousMessage)
		and float(elapsedSeconds) < float(windowSeconds)
	)


def duplicateChannelActions(speechMessage, brailleMessage, previousSpeech, previousBraille, speechElapsed, brailleElapsed):
	"""Resolve duplicate suppression independently for speech and Braille."""
	return {
		"speech": bool(speechMessage) and shouldSuppressSemanticDuplicate(
			speechMessage, previousSpeech, speechElapsed,
		),
		"braille": bool(brailleMessage) and shouldSuppressSemanticDuplicate(
			brailleMessage, previousBraille, brailleElapsed,
		),
	}


def formatCommandSpeech(message, punctuation="normal", maximumCharacters=240):
	"""Prepare long command text for speech without changing stored or braille text."""
	text = str(message or "")
	if punctuation == "enhanced":
		text = text.replace("&&", " and then ").replace("||", " or else ").replace("|", " pipe ")
		text = text.replace(">>", " append to ").replace(">", " redirect to ")
	elif punctuation == "literal":
		for symbol, word in (("&&", " ampersand ampersand "), ("||", " pipe pipe "), ("|", " pipe "), (">", " greater than "), ("<", " less than ")):
			text = text.replace(symbol, word)
	text = " ".join(text.split())
	maximumCharacters = max(40, int(maximumCharacters or 240))
	if len(text) <= maximumCharacters:
		return text, False
	return text[:maximumCharacters].rstrip(" ,;:-") + "…", True


def shouldLogDiagnosticSnapshot(snapshot, previousSnapshot, elapsedSeconds, repeatSeconds=30.0):
	"""Log changed diagnostic data immediately and unchanged data only periodically."""
	snapshot = tuple(snapshot or ())
	return bool(snapshot and (snapshot != tuple(previousSnapshot or ()) or float(elapsedSeconds) >= float(repeatSeconds)))


def isResponseCompletionMarkerText(text):
	"""Return whether virtual-buffer text is Claude's completed-response marker."""
	normalized = " ".join(str(text or "").casefold().split())
	return normalized == "response complete" or normalized.startswith("response complete:")


def responseCompletionScanMarker(markerCount, latestDetailedFingerprint=None):
	"""Create privacy-safe scan state that changes when another response completes."""
	count = max(0, int(markerCount or 0))
	if not count:
		return None
	return count, latestDetailedFingerprint


def responseCompletionTransition(previousMarker, initialized, currentMarker, busy):
	"""Detect a new completed-response marker after establishing a buffer baseline."""
	if currentMarker is None:
		return previousMarker, True, False
	completed = bool(initialized and busy and currentMarker != previousMarker)
	return currentMarker, True, completed


def shouldFinalizeResponseCompletion(pending, elapsedSeconds, settleSeconds, busy, stopControlVisible, activityLabel):
	"""Finalize a tentative response only after a quiet, explicitly idle scan."""
	normalizedLabel = " ".join(str(activityLabel or "").lower().split())
	operationFinished = bool(
		intermediateCompletionCategory(activityLabel)
		and any(word in normalizedLabel for word in ("finished", "complete", "succeeded", "failed", "passed"))
	)
	labelIsQuiet = (
		not normalizedLabel
		or statusDetails(activityLabel)[0] == "completion"
		or operationFinished
	)
	return bool(
		pending
		and busy
		and not stopControlVisible
		and labelIsQuiet
		and float(elapsedSeconds) >= float(settleSeconds)
	)


def isTaskCompletionLabel(label):
	"""Distinguish whole-task completion from an intermediate operation finishing."""
	lower = " ".join(str(label or "").lower().split())
	return lower.startswith(("response complete", "finished", "completed", "done", "cancelled", "canceled"))


def supersedesResponseCompletionCandidate(label):
	"""Return whether a new activity label proves that a tentative response completion is stale."""
	category, _message = statusDetails(label)
	return bool(category and category != "completion")


def intermediateCompletionCategory(label):
	"""Map an operation completion back to the activity category it belongs to."""
	lower = " ".join(str(label or "").lower().split())
	if lower.startswith("ran") or "command" in lower or "process" in lower:
		return "command"
	if "search" in lower and ("web" in lower or "internet" in lower):
		return "search"
	if lower.startswith(("compiled", "transpiled", "generated", "built")):
		return "build"
	if lower.startswith(("file edit", "file editing", "file edited", "wrote", "created", "edited", "updated", "modified", "applied", "patched", "read", "inspected", "reviewed")):
		return "file"
	return ""


def isKnownNonStatusButton(label):
	"""Filter stable Code controls that are not progress statuses."""
	text = " ".join(str(label or "").lower().split())
	return bool(
		isCodePromptLabel(text)
		or userMessageNumber(text) is not None
		or promptControlKind(text)
		or voiceControlKind(text)
		or text in (
			"outputs", "sources", "view all", "copy", "copy message", "retry", "edit", "share", "more",
			"fork chat from here", "scroll to bottom", "add files and more", "dictate", "send",
			"review", "review changed files", "undo", "open chat", "edit message",
		)
		or re.fullmatch(r"worked for (?:\d+h )?(?:\d+m )?\d+s", text) is not None
		or text.startswith("download code status announcer ")
		or re.fullmatch(r"show \d+ more files?", text) is not None
		or re.search(r"\+\d+-\d+$", text) is not None
	)


def isChatHistoryInterfaceText(label):
	"""Identify non-history controls that must never become chat titles."""
	text = " ".join(str(label or "").casefold().split())
	if not text:
		return False
	return bool(
		isKnownNonStatusButton(text)
		or isChatMessageTrailingUiText(text)
		or re.fullmatch(r"(?:sources?|outputs?)(?:\s+\d+|\s*\(\d+\))?", text)
		or re.fullmatch(r"(?:copy|share) (?:response|message|link)", text)
		or re.fullmatch(r"\d{1,3}% usage remaining", text)
		or text.startswith(("resets every ", "next reset "))
		or text in (
			"read aloud", "stop reading", "regenerate", "regenerate response",
			"branch in new chat", "like", "dislike", "thumbs up", "thumbs down",
			"report", "copy code", "copy code to clipboard", "share chat",
			"more actions", "more options", "open message actions", "previous response", "next response",
			"show more", "show less", "loading", "loading…",
			"dismiss usage alert", "usage consumed", "view usage", "add credits", "buy credits",
			"purchase credits", "manage plan", "manage subscription", "my plan", "upgrade",
			"upgrade plan", "upgrade to pro", "update", "update now", "install update",
			"restart to update", "manage account", "settings", "help", "log out", "sign out",
		)
	)


def isChatHistoryConversationBoundary(label):
	"""Identify conversation or account content following the sidebar chat list."""
	text = " ".join(str(label or "").casefold().split())
	return bool(
		userMessageNumber(text) is not None
		or text in ("you said:", "claude said:", "dismiss usage alert", "usage consumed")
		or re.fullmatch(r"\d{1,3}% usage remaining", text)
		or text.startswith(("resets every ", "next reset "))
	)


def promptControlKind(name):
	"""Classify stable and dynamic prompt-toolbar control names."""
	text = " ".join(str(name or "").casefold().split())
	if text == "add files and more" or text.startswith(("add files", "attach files", "upload files")):
		return "files"
	if text == "change permissions" or ("permission" in text and text.startswith(("change", "select", "choose"))):
		return "permissions"
	if text in ("model", "select model", "choose model", "change model"):
		return "model"
	if re.search(r"\b(?:gpt[- ]?\d|o[1345](?:[- ]|$)|code model|reasoning model)\b", text):
		return "model"
	return ""


def categoryOutputActions(mode, speechEnabled=True, brailleEnabled=True, soundEnabled=True):
	"""Resolve a category output mode through the global master switches."""
	mode = mode if mode in ("all", "speech", "sound", "braille", "off") else "all"
	return {
		"speech": bool(speechEnabled and mode in ("all", "speech")),
		"braille": bool(brailleEnabled and mode in ("all", "braille")),
		"sound": bool(soundEnabled and mode in ("all", "sound")),
	}


def shouldSuppressRoutineBraille(
	protectReading, appFocused, category, priority="normal", browseMode=False,
):
	"""Keep routine background output from replacing a Braille line being read in Claude."""
	routineCategories = {
		"thinking", "working", "command", "search", "file", "build", "tool", "commentary",
		"backgroundPulse1", "backgroundPulse2",
	}
	if not (protectReading and appFocused):
		return False
	priority = str(priority or "normal")
	category = str(category or "")
	if priority == "urgent" or category == "attention":
		return False
	if browseMode and category == "completion":
		return True
	return category in routineCategories and priority != "high"


def shouldSuppressNativeConversationUpdate(
	protectReading, appFocused, browseMode, inConversation, inPopup, text,
):
	"""Keep ordinary streamed response updates from replacing active reading.

	Permission and approval text is never suppressed. The caller remains responsible
	for handling any state-only completion signal after suppressing native output.
	"""
	if not (protectReading and appFocused and browseMode and inConversation) or inPopup:
		return False
	text = " ".join(str(text or "").casefold().split())
	if not text or isPermissionPromptText(text) or statusDetails(text)[0] == "attention":
		return False
	return text == "response complete" or text.startswith((
		"response:", "response complete:", "claude said:",
	))


def announcementPriority(category, message=""):
	"""Return low, normal, high, or urgent output priority."""
	message = str(message or "").lower()
	if category == "attention" or any(word in message for word in ("permission", "input required", "needs your")):
		return "urgent"
	if category == "completion" and any(word in message for word in ("fail", "error", "cancel")):
		return "urgent"
	if category == "completion":
		return "high"
	if category in ("commentary", "backgroundPulse1", "backgroundPulse2"):
		return "low"
	return "normal"


def outputActions(speechEnabled, speechOff, brailleEnabled, progressSoundsEnabled, toneCategory):
	"""Return which output channels should be used for one announcement."""
	speechUnavailable = not speechEnabled or speechOff
	return {
		"speech": bool(speechEnabled and not speechUnavailable),
		"braille": bool(brailleEnabled),
		"tone": bool(progressSoundsEnabled and toneCategory),
	}


def nextBusyState(currentBusy, category="", commentary=False):
	"""Update task activity without allowing final commentary to restart it."""
	if commentary:
		return bool(currentBusy)
	if category:
		return category not in ("completion", "attention")
	return bool(currentBusy)


def pollDelay(active, idlePollMs, activePollMs=500):
	"""Return the lightweight housekeeping interval, not a full-buffer scan rate."""
	return int(activePollMs if active else max(1000, idlePollMs))


def bufferInspectionDue(
	dirty, elapsedSinceInspection, active, appFocused, promptTyping,
	activeFallbackSeconds=5.0, focusedIdleFallbackSeconds=15.0,
):
	"""Decide whether the comparatively expensive Claude buffer must be inspected.

	Relevant accessibility events mark the buffer dirty for the next safe moment.
	All whole-buffer inspection is deliberately suspended while the user is typing,
	and idle Claude is event-only whether focused or in the background. Direct event
	handlers still announce time-sensitive activity.
	"""
	if promptTyping:
		return False
	if dirty:
		return True
	try:
		elapsed = float(elapsedSinceInspection)
	except (TypeError, ValueError, OverflowError):
		elapsed = 0.0
	if math.isnan(elapsed) or elapsed < 0:
		elapsed = 0.0
	if active:
		try:
			fallback = max(0.0, float(activeFallbackSeconds))
		except (TypeError, ValueError, OverflowError):
			fallback = 5.0
		return elapsed >= fallback
	return False


def conversationWindowShouldDetach(
	windowKnown, windowExists, windowVisible, unavailableSeconds, graceSeconds=2.0,
):
	"""Confirm that the tracked Claude window is unavailable before discarding task state."""
	if not windowKnown or windowExists is None or windowVisible is None:
		return False
	if bool(windowExists) and bool(windowVisible):
		return False
	try:
		elapsed = float(unavailableSeconds)
		grace = max(0.0, float(graceSeconds))
	except (TypeError, ValueError, OverflowError):
		return False
	return bool(not math.isnan(elapsed) and elapsed >= grace)


def isBrailleTypingGestureIdentifier(identifier):
	"""Recognize a Braille display dot/space chord without claiming its command."""
	text = str(identifier or "").casefold().strip()
	if not text.startswith("br(") or ":" not in text:
		return False
	gesture = text.rsplit(":", 1)[-1]
	return any(re.fullmatch(r"dot[1-8]|space", token) for token in gesture.split("+"))


def brailleTypingGestureCommitsText(identifier):
	"""Return whether a recognized Braille typing gesture contains Space."""
	if not isBrailleTypingGestureIdentifier(identifier):
		return False
	gesture = str(identifier or "").casefold().rsplit(":", 1)[-1]
	return "space" in gesture.split("+")


def isPromptSubmissionGestureIdentifier(identifier):
	"""Recognize an unmodified keyboard Enter or a Braille display Enter chord.

	This classifies identifiers only. It neither claims nor sends a gesture, so the
	caller can observe submission without changing NVDA or display-driver behavior.
	"""
	text = str(identifier or "").casefold().strip()
	if ":" not in text:
		return False
	prefix, gesture = text.rsplit(":", 1)
	if prefix.startswith("kb"):
		return gesture in ("enter", "numpadenter")
	if prefix.startswith("br("):
		return gesture == "dot8"
	return False


def promptSubmissionGestureShouldStart(promptInFocusMode, promptHadText, promptTypingActive):
	"""Require evidence of an actual prompt before Enter starts task feedback.

	Braille dot-8 activates an edit field while NVDA is in browse mode, so the
	gesture alone is not proof that Claude received a prompt. Recent typing is
	accepted because Chromium can replace the editor before its final text event.
	"""
	return bool(promptInFocusMode and (promptHadText is True or promptTypingActive))


def shouldPreserveBrailleComposition(
	promptFocused, compositionActive, hasBufferedCells, elapsedSinceSend, graceSeconds=1.0,
):
	"""Ignore only the delayed caret event produced by our prior contracted-word send."""
	if not (promptFocused and compositionActive and hasBufferedCells):
		return False
	try:
		elapsed = float(elapsedSinceSend)
		grace = max(0.0, float(graceSeconds))
	except (TypeError, ValueError, OverflowError):
		return False
	return math.isfinite(elapsed) and 0.0 <= elapsed <= grace


def coalescedPollDelay(requestedDelayMs, elapsedSinceLastPoll, minimumIntervalMs=150):
	"""Prevent rapid accessibility events from flooding NVDA's main thread with scans."""
	try:
		requestedDelayMs = int(requestedDelayMs)
	except (TypeError, ValueError, OverflowError):
		requestedDelayMs = 0
	requestedDelayMs = max(0, requestedDelayMs)
	try:
		minimumIntervalMs = int(minimumIntervalMs)
	except (TypeError, ValueError, OverflowError):
		minimumIntervalMs = 150
	minimumIntervalMs = max(0, minimumIntervalMs)
	try:
		elapsedSeconds = float(elapsedSinceLastPoll)
	except (TypeError, ValueError, OverflowError):
		elapsedSeconds = 0.0
	# Positive infinity deliberately means there has never been a previous poll.
	# It therefore needs no minimum-interval throttle and must never be rounded.
	if math.isinf(elapsedSeconds) and elapsedSeconds > 0:
		return requestedDelayMs
	if not math.isfinite(elapsedSeconds):
		elapsedSeconds = 0.0
	elapsedMs = max(0.0, elapsedSeconds * 1000.0)
	remainingMs = max(0, round(minimumIntervalMs - elapsedMs))
	return max(requestedDelayMs, remainingMs)


def shouldReplaceScheduledPoll(existingDeadline, requestedDeadline):
	"""Keep an already scheduled earlier scan instead of postponing it during event storms."""
	existingDeadline = float(existingDeadline or 0.0)
	requestedDeadline = float(requestedDeadline or 0.0)
	return not existingDeadline or requestedDeadline < existingDeadline


def shouldPlayContinuousWorkingClick(busy, enabled, soundStyle, soundAllowed, elapsedSinceSound, intervalSeconds):
	"""Play a working earcon only in a quiet gap between other progress sounds.

	The legacy function name is retained for add-on configuration compatibility.
	"""
	return bool(
		busy
		and enabled
		and soundStyle in ("clicks", "tones")
		and soundAllowed
		and float(elapsedSinceSound) >= float(intervalSeconds)
	)


def focusStateTransition(previousState, isFocused):
	"""Return the new focus state and a cue only when the state changes."""
	isFocused = bool(isFocused)
	if previousState is None:
		return isFocused, "active" if isFocused else ""
	if bool(previousState) == isFocused:
		return isFocused, ""
	return isFocused, "active" if isFocused else "inactive"


def promptSubmissionTransition(previousHadText, currentHasText):
	"""Detect a prompt edit changing from populated to empty without storing text."""
	currentHasText = bool(currentHasText)
	return currentHasText, bool(previousHadText and not currentHasText)


def isCodePromptLabel(label):
	text = " ".join(str(label or "").casefold().split()).rstrip(".…:")
	return text in ("reply to claude", "message claude", "ask claude", "how can i help you today", "how can i help you", "what can i help you with", "send a message", "write a reply")


def statusDetails(label):
	"""Return ``(category, minimal message)`` for a recognized activity label."""
	text = " ".join(str(label or "").split())
	lower = text.lower()
	if not lower:
		return "", ""
	if lower.startswith(("permission required", "approval required", "waiting for approval", "needs your approval", "requires permission")):
		return "attention", "Permission required"
	if lower.startswith(("input required", "waiting for user input", "waiting for your input", "needs your input", "question for you")):
		return "attention", "User input required"
	if lower.startswith(("file edit complete", "file editing complete", "file edited")):
		return "completion", "File edit finished"
	if lower.startswith(("compiled", "transpiled")):
		return "completion", "Compilation finished"
	if lower.startswith(("searched the web", "search complete", "search finished")):
		return "completion", "Web search finished"
	if lower.startswith("ran"):
		hasSearch = "search" in lower and "web" in lower
		if hasSearch:
			return "completion", "Command and web search finished"
		# Code normally formats completed shell activity as "Ran <command>"
		# without including the literal word "command".
		return "completion", "Command finished"
	if lower.startswith(("command failed", "failed command", "process failed")):
		return "completion", "Command failed"
	if lower.startswith(("command succeeded", "process succeeded")):
		return "completion", "Command finished"
	if lower.startswith(("tests failed", "testing failed", "test failed")):
		return "completion", "Tests failed"
	if lower.startswith(("tests passed", "testing passed", "test passed")):
		return "completion", "Tests passed"
	if lower.startswith(("build failed", "compilation failed")):
		return "completion", "Build failed"
	if lower.startswith(("finished", "completed", "done", "cancelled", "canceled", "response complete")):
		return "completion", "Finished"
	if lower.startswith(("reading finished", "reading complete", "inspection finished", "review finished")):
		return "completion", "Reading finished"
	if lower == "read" or lower.startswith(("read ", "read:", "inspected", "reviewed")):
		return "completion", "Reading finished"
	if lower.startswith(("wrote", "created")):
		return "completion", "Writing finished"
	if lower.startswith(("edited", "updated", "modified", "applied", "patched")):
		return "completion", "Changes finished"
	if lower.startswith(("generated", "built")):
		return "completion", "Generation finished"
	if lower.startswith(("planning", "thinking")):
		return "thinking", "Thinking"
	if lower.startswith(("working", "processing")):
		return "working", "Working"
	if lower.startswith(("analyzing", "analysing")):
		return "working", "Analyzing"
	if lower.startswith(("running", "executing")):
		if "search" in lower and ("web" in lower or "internet" in lower):
			return "search", "Searching the web"
		if lower.startswith(("running tests", "running test", "executing tests", "executing test", "running build", "executing build")):
			return "build", "Running tests" if "test" in lower else "Generating"
		if lower.startswith(("running tool", "executing tool")):
			return "tool", "Using tool"
		return "command", "Running command"
	if lower.startswith("searching"):
		return "search", "Searching the web"
	if lower.startswith(("reading", "inspecting", "reviewing")):
		return "file", "Reading"
	if lower.startswith(("writing", "creating")):
		return "file", "Writing"
	if lower.startswith(("file edit", "editing", "updating", "modifying")):
		return "file", "Editing file" if lower.startswith("file edit") else "Editing"
	if lower.startswith(("applying", "patching")):
		return "file", "Applying changes"
	if lower.startswith(("compiling", "transpiling", "generating", "building", "testing")):
		if lower.startswith(("compiling", "transpiling")):
			return "build", "Compiling"
		if lower.startswith("testing"):
			return "build", "Running tests"
		return "build", "Generating"
	if lower.startswith(("using", "calling")):
		return "tool", "Using tool"
	if lower.startswith("waiting"):
		return "other", "Waiting"
	return "", ""


def redactSensitive(text):
	text = " ".join(str(text or "").split())
	text = re.sub(r"(?i)(https?://[^\s?]+)\?\S+", r"\1?[query redacted]", text)
	text = re.sub(r"(?i)\b[\w.-]+@[\w.-]+\.[a-z]{2,}\b", "[email redacted]", text)
	secretValue = r'''(?:"[^"]*"|'[^']*'|[^\s;]+)'''
	text = re.sub(r"(?i)\b(api[_-]?key|token|secret|password|passwd|pwd|authorization)\s*[:=]\s*" + secretValue, r"\1=[redacted]", text)
	text = re.sub(
		r"(?i)(--?(?:api[_-]?key|token|secret|password|passwd|pwd|authorization))\s+" + secretValue,
		r"\1 [redacted]", text,
	)
	text = re.sub(r"(?i)(C:\\Users\\)[^\\]+", r"\1[user]", text)
	text = re.sub(r"(?i)(/home/|/users/)[^/\s]+", r"\1[user]", text)
	text = re.sub(r"(?i)\b(remote\s+(?:key|password)|connection\s+key)\s*[:=]\s*" + secretValue, r"\1=[redacted]", text)
	text = re.sub(r"(?i)\b(bearer)\s+[a-z0-9._~+/-]+=*", r"\1 [redacted]", text)
	return text


def standardFullMessage(label, translate=lambda text: text):
	"""Return an action-first Full message with useful targets, counts, and timing."""
	text = " ".join(str(label or "").split())
	lower = text.casefold()
	category, minimal = statusDetails(text)
	if not category:
		return ""
	details = []
	if category == "command" or lower.startswith("ran "):
		command = re.sub(
			r"(?i)^(?:(?:running|executing)(?:\s+(?:shell|terminal))?\s+command|ran)\s*:?\s*",
			"", text,
		)
		if command and command != text:
			executable = command.split()[0].strip("'\"")
			executable = re.split(r"[\\/]", executable)[-1]
			if executable:
				details.append(executable)
	else:
		fileMatch = re.search(r"(?i)(?:^|\s)([^\s<>|*?\"]+\.[a-z0-9]{1,8})(?:\s|$)", text)
		if fileMatch:
			details.append(re.split(r"[\\/]", fileMatch.group(1))[-1])
	countMatch = re.search(r"(?i)\b\d+\s+(?:files?|tests?|warnings?|errors?|failures?|passed|failed)\b", text)
	if countMatch and countMatch.group(0).casefold() not in {item.casefold() for item in details}:
		details.append(countMatch.group(0))
	seconds = elapsedSeconds(text)
	if seconds is not None and seconds >= 5:
		details.append(f"{seconds} seconds")
	message = translate(minimal)
	return f"{message}: {', '.join(details)}" if details else message


def minimalProfileMessage(label, translate=lambda text: text, profile="balanced"):
	"""Return Essential, Balanced, or Informative Minimal speech."""
	text = " ".join(str(label or "").split())
	category, minimal = statusDetails(text)
	if not category:
		return ""
	lower = text.casefold()
	if profile == "essential":
		isFailure = any(word in lower for word in ("fail", "error", "cancel"))
		if category not in ("thinking", "attention") and not (
			category == "completion" and (isFailure or isTaskCompletionLabel(text))
		):
			return ""
	balanced = minimal
	if category == "file":
		if lower.startswith(("reading", "inspecting", "reviewing")):
			balanced = "Checking files"
		elif lower.startswith(("writing", "creating", "file edit", "editing", "updating", "modifying")):
			balanced = "Editing code"
	elif category == "completion":
		if isTaskCompletionLabel(text):
			balanced = "Task canceled" if lower.startswith(("cancelled", "canceled")) else "Task finished"
		elif lower.startswith(("file edit", "file edited", "edited", "updated", "modified", "applied", "patched")):
			balanced = "File updated"
	elif category == "other" and lower.startswith("waiting"):
		if "command" in lower or "process" in lower:
			balanced = "Waiting for command"
		elif "tool" in lower:
			balanced = "Waiting for tool"
	message = translate(balanced)
	if profile != "informative":
		return message
	details = []
	fileMatch = re.search(r"(?i)(?:^|\s)([^\s<>|*?\"]+\.[a-z0-9]{1,8})(?:\s|$)", text)
	if fileMatch:
		details.append(re.split(r"[\\/]", fileMatch.group(1))[-1])
	countMatch = re.search(r"(?i)\b\d+\s+(?:files?|tests?|warnings?|errors?|failures?|passed|failed)\b", text)
	if countMatch:
		details.append(countMatch.group(0))
	seconds = elapsedSeconds(text)
	if seconds is not None and seconds >= 10:
		details.append(f"{seconds} seconds")
	return f"{message}: {', '.join(details)}" if details else message


def statusMessage(label, translate=lambda text: text, verbosity="minimal", redact=False, fullProfile="developer", minimalProfile="balanced"):
	text = " ".join(str(label or "").split())
	category, minimal = statusDetails(text)
	if not category:
		return ""
	if verbosity == "full":
		if fullProfile == "standard":
			message = standardFullMessage(text, translate)
		elif fullProfile == "raw":
			message = str(label or "").strip()
		else:
			message = text
		return redactSensitive(message) if redact else message
	return minimalProfileMessage(text, translate, minimalProfile)


def brailleStatusMessage(label, translate=lambda text: text, detail="full", redact=False):
	"""Format status independently for a Braille display."""
	detail = detail if detail in ("concise", "informative", "full") else "full"
	if detail == "concise":
		return statusMessage(label, translate, "minimal", redact, "developer", "balanced")
	if detail == "informative":
		return statusMessage(label, translate, "minimal", redact, "developer", "informative")
	return statusMessage(label, translate, "full", redact, "developer", "balanced")


def firstStatusLabel(*labels):
	for label in labels:
		text = " ".join(str(label or "").split())
		if statusDetails(text)[0]:
			return text
	return ""


def elapsedSeconds(label):
	match = re.search(r"(?i)\b(?:for\s+)?(\d+)\s*s(?:ec(?:ond)?s?)?\b", str(label or ""))
	return int(match.group(1)) if match else None


def completedTextDelta(text, spokenOffset=0):
	"""Return newly completed streamed sentences and the updated offset."""
	text = " ".join(str(text or "").split())
	spokenOffset = min(max(int(spokenOffset or 0), 0), len(text))
	end = 0
	for match in re.finditer(r"[.!?](?:[\"'”’\)]*)($|\s)", text):
		end = match.end()
	if end <= spokenOffset:
		return "", spokenOffset
	return text[spokenOffset:end].strip(), end


def changelogForDisplay(markdownText):
	"""Convert the installed Markdown history into clean accessible text."""
	lines = []
	for rawLine in str(markdownText or "").splitlines():
		line = rawLine.strip()
		if line == "# Changelog":
			lines.append("Complete release history")
		elif line.startswith("## "):
			lines.extend(("", f"Version {line[3:].strip()}"))
		elif line.startswith("### "):
			lines.extend(("", line[4:].strip()))
		elif line.startswith("- "):
			lines.append(line[2:])
		else:
			lines.append(line)
	cleanLines = []
	for line in lines:
		if line or not cleanLines or cleanLines[-1]:
			cleanLines.append(line)
	return "\n".join(cleanLines).replace("**", "").replace("`", "").strip()


def viewerTitleMatches(expectedTitle, foregroundName):
	"""Return whether the intended browseable-message viewer is foreground."""
	expected = str(expectedTitle or "").strip().lower()
	foreground = str(foregroundName or "").strip().lower()
	return bool(expected and (foreground == expected or foreground.startswith(expected + " ")))


def previewSelection(items, selection):
	"""Return one preview item, falling back safely to the first item."""
	if not items:
		return None
	if not 0 <= selection < len(items):
		selection = 0
	return items[selection]


def formatCustomAnnouncement(template, message, activity="", seconds=0, duration=""):
	"""Format a user announcement without allowing unknown fields to break output."""
	template = str(template or "").strip()
	if not template:
		return str(message or "")
	duration = str(duration or formatElapsedDuration(seconds))
	try:
		return template.format(message=message, activity=activity, seconds=seconds, duration=duration)
	except (AttributeError, KeyError, IndexError, ValueError):
		return template
