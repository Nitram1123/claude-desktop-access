"""Create a deterministic gettext template from the add-on's Python sources."""

import argparse
import ast
import json
from pathlib import Path


HEADER = '''msgid ""
msgstr ""
"Project-Id-Version: Claude Desktop Access {version}\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Content-Transfer-Encoding: 8bit\\n"
"MIME-Version: 1.0\\n"
"Generated-By: tools/extract_messages.py\\n"

'''


def _version(projectRoot):
	manifest = (projectRoot / "manifest.ini").read_text(encoding="utf-8")
	for line in manifest.splitlines():
		if line.startswith("version = "):
			return line.split("=", 1)[1].strip()
	raise ValueError("manifest version is missing")


def messages(projectRoot):
	sourceRoot = projectRoot / "globalPlugins" / "claudeDesktopAccess"
	strings = sourceRoot / "strings.py"
	tree = ast.parse(strings.read_text(encoding="utf-8"), filename=str(strings))
	found = {}
	for node in tree.body:
		if not isinstance(node, ast.Assign):
			continue
		if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str) or not node.value.value:
			raise ValueError(f"{strings.name}:{node.lineno}: expected a nonempty message literal")
		message = node.value.value
		if message in found:
			raise ValueError(f"{strings.name}:{node.lineno}: duplicate message ID {message!r}")
		found[message] = [f"{strings.relative_to(projectRoot).as_posix()}:{node.lineno}"]

	for path in sorted([*sourceRoot.glob("*.py"), *(projectRoot / "appModules").glob("*.py")], key=lambda item: item.as_posix().casefold()):
		tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call) or not node.args:
				continue
			if not isinstance(node.func, ast.Name) or node.func.id not in ("_", "translate"):
				continue
			branches = [node.args[0]]
			while branches:
				value = branches.pop()
				if isinstance(value, ast.IfExp):
					branches.extend((value.body, value.orelse))
				elif isinstance(value, (ast.Constant, ast.JoinedStr)):
					raise ValueError(f"{path.name}:{value.lineno}: put the message in strings.py")
	return found


def render(projectRoot):
	parts = [HEADER.format(version=_version(projectRoot))]
	for message, references in sorted(messages(projectRoot).items(), key=lambda item: item[0].casefold()):
		parts.append("#: {references}\nmsgid {message}\nmsgstr \"\"\n\n".format(
			references=" ".join(sorted(references)),
			message=json.dumps(message, ensure_ascii=False),
		))
	return "".join(parts).rstrip() + "\n"


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("--check", action="store_true")
	args = parser.parse_args()
	root = Path(__file__).resolve().parents[1]
	output = root / "locale" / "claudeDesktopAccess.pot"
	expected = render(root)
	if args.check:
		if not output.is_file() or output.read_text(encoding="utf-8") != expected:
			raise SystemExit("Translation template is out of date; run tools/extract_messages.py")
		print("Translation template is current")
	else:
		output.parent.mkdir(parents=True, exist_ok=True)
		output.write_text(expected, encoding="utf-8", newline="\n")
		print(f"Wrote {output}")
