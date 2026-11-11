# Claude Desktop Access for NVDA

**Version 2026.2.2 — experimental beta for stable NVDA 2026.2 on Windows.**

This is a separate GPL-licensed adaptation of [ChatGPT Desktop Access](https://github.com/jcoffin1/chatgpt-desktop-access), with independent settings and an app module scoped to Claude Desktop. Both add-ons can remain installed.

The first beta has now been used with Claude and stable NVDA 2026.2. Version 2026.2.2 addresses activity and history bugs found in that NVDA log, with automated regression tests. Live post-update verification and broader feature testing remain ongoing. Claude-specific detection still relies on English accessibility labels; some versions may expose different labels or unusable message boundaries. This release does not claim verified feature parity.

## Install and start

1. Use the stable NVDA 2026.2 release and install the official Claude Desktop Windows app.
2. Download `claudeDesktopAccess-2026.2.2.nvda-addon` from this repository's Releases page. Open it, accept NVDA's installation dialog, and restart NVDA when prompted.
3. Open NVDA Settings, then **Claude Desktop Access**. Test the selected speech, Braille and sound outputs.
4. Open Claude and a disposable test conversation. Test in both focus mode and browse mode.

The add-on does not require an API key or a paid subscription. Test whichever Claude features your account exposes. It does not unlock paid features. No purchase, message submission, or permission approval is performed automatically.

## Default shortcuts in Claude

| Shortcut | Action |
| --- | --- |
| Control+1 through Control+9 | Read the first through ninth most recent exposed message |
| Control+0 | Read the tenth most recent exposed message |
| NVDA+Alt+V | Try the exposed start/end voice control |
| NVDA+Alt+M | Try the exposed microphone mute/unmute control |
| NVDA+grave accent (backtick) | Open Claude navigation for modes, artifacts and attachments |

Each default is separately assignable under NVDA Preferences > Input Gestures > Claude Desktop Access. Control+number replaces any native Claude action on those keys; remove or reassign the add-on gestures if you prefer Claude's shortcuts. Default gestures apply only while the `claude` application has focus. Terminal-based Claude Code and browser tabs are outside this beta's scope.

Additional unassigned actions include returning to the prompt, searchable chat history, current activity, announcement history, pause/resume, verbosity, privacy redaction, support reports, and the inherited embedded-browser tools. Assign shortcuts only to the actions you want. General plug-in actions are unassigned by default; manually binding one may make that action available globally.

## Features and beta status

All rows require live tester verification; automated checks cover shared logic and synthetic Claude scenarios.

| Feature | Implementation in this beta |
| --- | --- |
| Speech and Braille | Independent output, verbosity profiles, Braille detail, urgent alerts, custom wording and category routing |
| Sounds | 17 sound signatures at Soft, Normal and Loud levels; clicks or tones; submission, working, background, completion and focus cues |
| Activity | Candidate thinking/tool/search/file/build labels, busy-control observation, delayed completion and duplicate suppression |
| Reading and typing | Inherited reading protection, typing debounce, Braille composition protection and bounded polling |
| Message review | Explicit named user/assistant regions or speaker markers; drafts and nested documents excluded; no guessed speaker alternation |
| Prompt recall | Read the text recalled by Up/Down in the native Claude Code editor, including multiline prompts |
| Conversation history | Search exposed recent buttons/links; native Show more where available; exposed archive controls only |
| Mode navigation | Selected Chat, Cowork and Code tabs refine monitoring; the navigation dialog finds recognized exposed controls |
| Artifacts and attachments | Search recognized controls, move focus, or explicitly activate; never automatically publish artifacts or upload files |
| Dialogs and permissions | Inherited focus handling and permission/input announcements; approvals stay with the user |
| Voice | Experimental native-control actions; a missing-control message is expected where voice is not exposed |
| Embedded browser | Inherited navigator, page summary, snapshot, native focus and loading support; detection remains unverified in Claude |
| Support | Configuration repair, compatibility self-test, sanitized diagnostics, import/export and release notes |

**Known limits:** Some Claude message containers may be unlabeled, causing recent-message review to report no messages. History is limited to what the app exposes; it does not retrieve hidden account history, read private databases, or assume Codex storage formats. Archive/pin actions are experimental and only work when matching native controls exist. Account-wide quotas, model identity, and complete artifact contents are not independently queried. English recognition patterns need tester samples before translation to other interface languages. Claude may change its interface without notice.

In the navigation dialog, type to filter, Tab to the list, and use the Arrow keys. Enter or **Move to item** focuses the selected control. **Activate item** performs its native action. Escape closes. Scans happen only on request, stop at a bounded limit, and yield between slices. Native accessibility calls can still be slow on some machines; report delays.

In the Claude Code editor, use Up/Down in focus mode to recall prompts through Claude's own input history. When Claude replaces the editor text, the add-on reads the recalled prompt, including multiple lines. It uses the accessible editor contents without matching the translated history announcement or keeping a separate prompt history. Ordinary line movement and selection retain NVDA's standard behavior.

The recalled prompt is editable immediately. Use Left/Right, Control+Left/Right and Home/End to position the caret, then type your changes. In a single-line prompt, Up/Down can continue recalling history because Claude handles those keys at the first or last visual line. If the keys read the page instead of moving the editing caret, return to the editor and use NVDA+Space to enable focus mode. Prompt recall and editing were tested with the French Claude interface and NVDA; multiline recall still needs live verification.

For Control+1 through Control+0 in long Claude Code conversations, the add-on uses Claude's native accessibility paging buttons to load missing recent messages on demand. It preserves their actual positions rather than skipping unloaded gaps. Loading is limited to five seconds and stops when you press another key, leave Claude or change sessions. The transcript may scroll as Claude loads a page; focus returns to the prompt when the request started there. Controls are identified by their native structure and surrounding message positions, without matching translated button names.

Recent-message shortcuts announce the speaker and message text directly, without repeating the message number.

Completion is inferred from exposed activity and the disappearance of a Stop control after a settling delay. It means generation appears to have ended, not that Claude's work succeeded. Cancel/error scenarios are particularly important beta tests.

## Settings

The keyboard-accessible pages are General, Speech and Braille, Sounds, Activity Output, Wording and Preview, Browser Access, Advanced, and Support. Use Control+Tab or Shift+Control+Tab to switch pages. Output settings, working intervals, sound levels, announcement wording, privacy redaction and per-category routing carry over from the original add-on.

Use **Test current announcement outputs** before testing activity detection. Preview one sound or speech sample at a time. Custom announcement placeholders include `{message}`, `{activity}`, `{seconds}`, and `{duration}`. Import/export uses a file you choose and this add-on's own settings namespace; it does not automatically import or change ChatGPT settings.

## Beta testing and feedback

Start with a disposable chat containing no private information:

1. Send a short request; verify submission and working feedback, then a single completion announcement.
2. Send a longer request and cancel it. Check that the working cue stops and no success claim is made.
3. Read messages using Control+1 through Control+0. Confirm speaker and order, and that an unsent draft is never read as a message.
4. Type with a keyboard and, if available, Braille. Read older text during generation and check for interruptions or lost reading position.
5. Open navigation, search, move to a control, and separately test explicit activation. Check artifacts, attachments and modes available to your account.
6. Test recent history, dialogs, voice and embedded pages where available. Mark unavailable features as **not available**, rather than passed.
7. Switch conversations and apps, close/reopen Claude, and confirm no stale announcements or changes to ChatGPT or other apps.
8. With a paid account, optionally test Cowork and Code progress and permission requests. Do not grant a permission merely to test the add-on.

Report add-on version, NVDA version, Windows version, Claude app version, interface language, account tier (no account identifiers), feature, steps, expected result, actual speech/Braille behavior, and whether it reproduces with this add-on disabled. A second clean reproduction is especially useful.

Use the Support page or an assigned **Save a sanitized Claude Desktop Access support report** gesture. Reports are saved only to a user-chosen file and are not uploaded. Review them before sharing. Sanitized diagnostics omit conversation bodies, while normal NVDA debug logs can contain speech and private data. Do not attach a raw log without reviewing it. Recognition failures may require a manually reviewed, minimal accessible label sample from a harmless test chat.

File reports at [GitHub Issues](https://github.com/jcoffin1/claude-desktop-access/issues). Disable or remove the add-on using NVDA's add-on manager if it interferes with normal use, then restart NVDA.

## Development

Run `./build.ps1 -PythonPath python`. This runs automated tests, validates Python and the translation template, builds a deterministic archive, and audits its contents and compatibility metadata. Tests include inherited output/state logic and synthetic Claude controls; they do not replace manual NVDA testing. GitHub Actions runs the same checks. Versions follow stable NVDA: 2026.2.1 is the first release in the 2026.2 line. Beta status is expressed in release metadata and documentation without changing the requested version number.

The project is not currently submitted to the NVDA Add-on Store. GitHub releases remain marked prerelease while live beta validation is outstanding.

## Credits and license

Based on ChatGPT Desktop Access 2026.2.6. Original copyright and GPL v2-or-later terms are retained in LICENSE.txt. Claude Desktop Access is an independent community add-on, not an Anthropic or NV Access product.
