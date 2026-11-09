"""Audit the Claude beta without claiming live NVDA verification."""
import argparse
import ast
from collections import Counter
import gettext
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
from string import Formatter
import tempfile
import wave
import zipfile

from build_addon import buildPackage, packageData, packageFiles
from extract_messages import messages


def manifestVersionMatches(manifest, version):
	return bool(re.search(rf"(?m)^version = {re.escape(version)}$", manifest))


def formatFields(message):
	return Counter(
		(field, spec, conversion)
		for _, field, spec, conversion in Formatter().parse(message)
		if field is not None
	)


def auditFrenchCatalog(projectRoot, archive):
	catalogPath = "locale/fr/LC_MESSAGES/nvda.mo"
	assert catalogPath in archive.namelist(), "Missing compiled French catalog"
	assert "locale/fr/manifest.ini" in archive.namelist(), "Missing French manifest"
	translation = gettext.GNUTranslations(io.BytesIO(archive.read(catalogPath)))
	assert translation.info().get("language") == "fr"
	assert (projectRoot / "locale/fr/LC_MESSAGES/nvda.po").is_file(), "Missing French translation source"
	sourceMessages = messages(projectRoot)
	catalogMessages = set(translation._catalog) - {""}
	assert catalogMessages == sourceMessages.keys(), "French catalog and source messages differ"
	for message in sourceMessages:
		localized = translation.gettext(message)
		assert localized, f"Empty French translation: {message!r}"
		assert formatFields(localized) == formatFields(message), f"Invalid French format fields: {message!r}"


def audit(projectRoot, packagePath, version):
	projectRoot = Path(projectRoot)
	manifest = (projectRoot / "manifest.ini").read_text(encoding="utf-8")
	for field in ("name = claudeDesktopAccess", f"version = {version}", "minimumNVDAVersion = 2026.2.0", "lastTestedNVDAVersion = 2026.2.0", "url = https://github.com/jcoffin1/claude-desktop-access", "docFileName = readme.md"):
		assert field in manifest.splitlines(), f"Incorrect manifest field: {field}"
	assert "(Beta)" in manifest, "Beta label missing"
	plugin = (projectRoot / "globalPlugins/claudeDesktopAccess/__init__.py").read_text(encoding="utf-8")
	assert f'ADDON_VERSION = "{version}"' in plugin
	assert 'CONFIG_SECTION = "claudeDesktopAccess"' in plugin
	assert 'DEFAULT_SUPPORTED_APP_NAMES = "claude"' in plugin
	assert f'[string]$Version = "{version}"' in (projectRoot / "build.ps1").read_text(encoding="utf-8")
	assert f"## {version}" in (projectRoot / "changelog.md").read_text(encoding="utf-8")
	app = (projectRoot / "appModules/claude.py").read_text(encoding="utf-8")
	assert 'class AppModule(appModuleHandler.AppModule)' in app
	assert len(re.findall(r'"kb:control\+[0-9]":', app)) == 10
	assert '"kb:NVDA+`": "toggleConversationMode"' in app
	assert "__gestures" not in plugin, "Unexpected global default bindings"
	paths = tuple(packageFiles(projectRoot))
	expected = tuple(path.relative_to(projectRoot).as_posix() for path in paths)
	assert [name for name in expected if name.startswith("appModules/")] == ["appModules/claude.py"]
	pythonCount = 0
	for path in paths:
		if path.suffix != ".py":
			continue
		pythonCount += 1
		source = path.read_text(encoding="utf-8")
		compile(source, str(path), "exec")
		for forbidden in ("CODEX_HOME", "CODE_HOME", "codex://", "code://", "session_index.jsonl", "chatgpt.com", "globalPlugins.codexStatusAnnouncer"):
			assert forbidden not in source, f"Upstream product dependency: {path.name}: {forbidden}"
	with zipfile.ZipFile(packagePath) as archive:
		names = tuple(archive.namelist())
		assert names == expected, "Unexpected archive contents or ordering"
		assert len(names) == len(set(names)), "Duplicate archive member"
		assert archive.testzip() is None, "Corrupt archive"
		assert sum(name.endswith(".wav") for name in names) == 51
		auditFrenchCatalog(projectRoot, archive)
		for path, name in zip(paths, names):
			assert not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
			assert "__pycache__" not in name and not name.endswith((".pyc", ".pyo"))
			data = archive.read(name)
			assert data == packageData(path), f"Source/package mismatch: {name}"
			if name.endswith(".wav"):
				with wave.open(io.BytesIO(data)) as sound:
					assert sound.getnframes() > 0 and sound.getnchannels() in (1, 2)
	with tempfile.TemporaryDirectory() as directory:
		copy = Path(directory) / "reproduction.nvda-addon"
		buildPackage(projectRoot, copy)
		assert hashlib.sha256(copy.read_bytes()).digest() == hashlib.sha256(Path(packagePath).read_bytes()).digest(), "Build is not reproducible"
	return pythonCount, len(expected)


if __name__ == "__main__":
	parser = argparse.ArgumentParser()
	parser.add_argument("package")
	parser.add_argument("version")
	args = parser.parse_args()
	count, entries = audit(Path(__file__).resolve().parents[1], args.package, args.version)
	print(f"Claude beta audit passed: {count} Python files, {entries} archive entries; reproducible package. Live testing outstanding.")
