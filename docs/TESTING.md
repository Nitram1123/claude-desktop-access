# Beta validation

See the installation steps, feature-status table and complete beta checklist in [readme.md](../readme.md).

Record each scenario as Pass, Fail, Not available, or Not tested. Version 2026.2.1 has been used with Claude and NVDA 2026.2. A reviewed log showed false Read aloud activity, stuck busy state and repeated history confirmation. Version 2026.2.2 adds regression coverage and fixes; live post-update verification is pending.

Automated scope: inherited output/state/parsing/privacy behavior; synthetic Claude message fields and selected tabs; process isolation; prompt guards; archive integrity and reproducibility. Synthetic fields are deliberately labeled as synthetic, not captured from Claude.

Release acceptance after beta feedback: verify free-account chat on stable NVDA 2026.2, typing and Braille protection, no cross-application interception, canceled/failed requests, app restart, and reported supported paid workflows. Keep unsupported features clearly identified.

## 2026.2.2 retest

- Finish a chat response with Read aloud visible: no false Reading finished announcement.
- Finish a response after a tool reports completion: working feedback stops after a quiet interval.
- Allow generation to pause and resume: no premature completion using the old quiet interval.
- Leave recent history unchanged: no repeated confirmation loop. Add or rename a chat and verify the changed list refreshes after confirmation.
- A sidebar title or ordinary link beginning with Reading or Running must not produce activity feedback.
