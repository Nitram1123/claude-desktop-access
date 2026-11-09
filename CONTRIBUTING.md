# Contributing

Start with the beta checklist in readme.md. Use small, anonymized accessibility examples from disposable chats. Identify synthetic test fixtures explicitly. Do not include conversation exports, account identifiers, credentials or raw logs in issues or commits.

Run build.ps1 before proposing a change. Preserve independent app scoping, settings, native roles/actions and GPL attribution. Never treat a test with stubs as proof of live compatibility.

Keep user-facing Python messages in `globalPlugins/claudeDesktopAccess/strings.py` and translate them at their point of use. Regenerate the template with `python tools/extract_messages.py`. Update `locale/fr/LC_MESSAGES/nvda.po` and rebuild the compiled catalog with GNU gettext:

```powershell
msgfmt --check -o locale/fr/LC_MESSAGES/nvda.mo locale/fr/LC_MESSAGES/nvda.po
```

Commit both the source and compiled catalog so the development junction and the packaged add-on use the same translations.
