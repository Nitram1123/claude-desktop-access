# Release history

## 2026.2.2

Bug fixes based on the 2026.2.1 NVDA log and synthetic reproductions. Compatibility remains stable NVDA 2026.2.

- Excludes Read aloud controls, ordinary links and sidebar titles from activity detection.
- Starts the completion settling timer when Stop disappears even if a completed tool label remains visible, preventing a stuck working state.
- Resets pending completion when generation resumes, so it cannot finish using an earlier quiet interval.
- Reuses confirmed, unchanged recent history without scheduling another confirmation scan. Changed or invalidated history still requires confirmation.
- Recognizes the main landmark on a generic section when leaving the sidebar history region.

119 automated tests pass, including regressions reproduced before applying the fixes. No unrelated NVDA add-on is changed. Live post-update verification remains pending.

## 2026.2.1

First Claude Desktop Access beta, targeting stable NVDA 2026.2.

- Separate Claude application module and configuration namespace, alongside ChatGPT Desktop Access.
- Ported speech, Braille, sounds, wording, routing, reading/typing protection and support tools.
- Experimental Claude message parsing, prompt recognition, Chat/Cowork/Code detection and exposed history navigation.
- Added a bounded, searchable navigator for mode, artifact and attachment controls.
- Removed Codex local-index dependencies and product-specific purchase/deep-link actions.
- Added synthetic Claude tests, package auditing and a tester checklist.

Live Claude/NVDA validation is outstanding. Voice, artifacts, archives, paid features and embedded pages depend on exposed controls. This is a prerelease, not a verified feature-parity claim.
