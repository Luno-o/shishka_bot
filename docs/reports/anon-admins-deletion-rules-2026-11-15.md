# Feature: anon-admins-deletion-rules — 2026-11-15
Status: Done
Branch: feat/anon-admins-deletion-rules (from feature/backup-telegram-antiraid-warn-catfriends)

## Request
- Admins who post as the group or channel (anonymous admin, "send as channel") are not recognized as admins; admin functions do not work for them. Make them work.
- When a message is deleted for block or spam, send the logs/report group a message naming the rule that triggered the block.
- User decisions:
  - A "send as channel" sender counts as admin only if `sender_chat` is the chat itself (anonymous group admin) or a channel listed in `config.groups.linked_channels`. Any other channel is not admin.
  - Deletion reports go to the existing logs chat (`config.groups.logs` / env `GROUPS_LOGS`). Existing logs are kept, a "Правило: ..." line is added, and logs are added where deletions were silent.

## Research summary
- `filters/is_admin.py` special-cases GroupAnonymousBot (1087968824) only. "Send as channel" comes from Channel_Bot (136817688) with `sender_chat` set, which falls through to `get_chat_member(136817688)` and is not admin.
- `handlers/cat_commands.py` had its own copy of the admin check (`is_chat_admin`).
- Moderation handlers in `handlers/group_events.py` check `retrieve_tgmember(from_user.id)`, so anonymous-admin and linked-channel posts were moderated like a 0-reputation user.
- Silent deletions: ML-spam, non-text media in `on_user_message`, `on_user_media`, `on_user_contact`. Location, forward and external-reply handlers logged but did not record deletion.
- NSFW used `_report_nsfw` (send_message with keyboard).
- User text went into HTML logs unescaped; a `<` broke parse_mode HTML and the log failed.
- `write_log` exceptions propagated, so a misconfigured logs chat aborted the handler after delete.
- Baseline: `.venv/Scripts/python -m pytest -q` → 86 passed.

## Plan
- Work units recorded in state:
  - U1: admin sender recognition.
  - U2: deletion rule in logs.
- Detailed plan document: Not recorded.

## Implemented
- Files:
  - `services/admin_identity.py` (new): `sender_chat_admin_verdict`, `is_admin_sender`, `actor_id`.
  - `services/moderation_log.py` (new): `RULES`, `describe_rule`, `log_auto_action`, `log_auto_event`. Never raises, escapes HTML, logs a warning when logs chat count is 0.
  - `filters/is_admin.py`: `IsAdminFilter` delegates to `admin_identity`.
  - `handlers/cat_commands.py`: `is_chat_admin` delegates to `admin_identity`; `added_by` uses `actor_id`.
  - `admin_actions` module (warn, linkallow): uses `actor_id`. Exact path: Not recorded.
  - `handlers/group_events.py`: auto-moderation handlers (voice, contact, location, external reply, forward, media, message) return early on a True `sender_chat_admin_verdict`; record deletion via `moderation_log`; `_report_nsfw` deletes before logging and tolerates delete failure; `user_mention()` escapes full_name.
  - Rules/sites covered by the logs: cn_spam, invisible_spacing, single_emoji, link, ml_spam, media (on_user_message + on_user_media), contact, location, external_reply, forward, first_comment, nsfw_photo, nsfw_profile, autoban (deleted=False), unwanted_bot (join), raid alert, newcomer_timeout (newcomer_guard).
- Endpoints: Not recorded.
- Migrations: Not recorded.
- Commits: `1bddfec` (test, U2), `c35f429` (feat, U2), `f7cc54b` (review fix), `9d91d51` and `9630892` (nit fixes). U1 commit hashes: Not recorded.

## Tests
- Full suite: 172 passed (after review round 1).
- Baseline: 86 passed.
- New test files:
  - `tests/test_admin_identity.py`: 30 tests (U1).
  - `tests/test_moderation_log.py`: 37 tests (U2).
  - `tests/test_moderation_early_returns.py`: 16 tests (review fix; handler-level early returns: anonymous admin and linked channel are not moderated, foreign channel still is).
- Count by layer: Not recorded.
- Stage totals recorded in state: 116 after U1 (86 + 30), 152 after U2. Note: 116 + 37 = 153, not 152. Reason: Not recorded.
- Edit `1bddfec` → `c35f429` in tests: judged legitimate by review (pins config value, does not weaken the test).

## Review
- Round 1 verdict: CHANGES REQUIRED.
- Blocking (resolved in `f7cc54b`):
  - No handler-level tests for the early returns on `sender_chat_admin_verdict` in group_events. Added `tests/test_moderation_early_returns.py` (16 tests).
- Nits (resolved in `9d91d51`, `9630892`):
  - `user_mention()` did not escape full_name, so the log was dropped for names containing `<`. Now escaped.
  - `_report_nsfw` deleted before logging; a delete failure lost the keyboard report. Now tolerates delete failure.
  - Location / invisible_spacing rule key `links_rep_threshold` matches code: no change needed.
- Round 2 verdict: Not recorded.
- Disputes: none recorded.
- `consilium-security`: not recorded as run.

## Validation
| Check | Result |
|---|---|
| Full test suite (`.venv/Scripts/python -m pytest -q`) | 172 passed |
| ruff | Clean on new files. Pre-existing findings in `group_events.py`, `helpers.py` and services left unchanged. |
| mypy | Not run |
| Live Telegram scenario | Not checked (needs the user's bot in a real group) |
| `scenario.md` steps passed/total | Not recorded (file does not exist) |

## Problems and rollbacks
- `_report_nsfw` delete-before-log ordering lost the keyboard report on delete failure. Fixed in review round 1.
- User text in HTML logs broke parse_mode on a `<` and dropped the log. Fixed in U2 (HTML escaping) and in `user_mention()` (review nit).
- Rollbacks: none recorded.

## Decisions and accepted risks
- Sender admin rule (user decision): `sender_chat` admin only when it is the chat itself or in `config.groups.linked_channels`. Any other channel is not admin.
- Deletion reports to the existing logs chat (user decision).
- `DECISIONS.md` entries: Not recorded.
- Accepted risk: members who post as their own (foreign) channel all share Channel_Bot's `from_user` id 136817688, so reputation and violations are shared between them. Pre-existing, out of scope.

## WHY-UNKNOWN items
- Stage total mismatch: 116 + 37 ≠ 152 (see Tests). Reason: Not recorded.
- Round 2 review verdict: Not recorded.
- Scenario step counts: Not recorded.

## Follow-ups
- `tests/test_newcomer_guard.py::test_inactive_newcomer_is_removed` is timing-flaky (0.05s sleep). Pre-existing; also fails on baseline sometimes.
- Foreign-channel posters share reputation and violations via id 136817688. Pre-existing, out of scope; needs a separate decision.
- Run mypy (not run in this task).
- Run the live Telegram scenario in a real group.
- Pre-existing ruff findings in `group_events.py`, `helpers.py` and services left as-is.
- Optional/FYI review items: Not recorded.

## PR description (draft)
Treat "send as channel" admins as admins and log the rule behind auto-deletions

What changed:
- Messages sent as the chat itself (anonymous group admin) or as a channel listed in `config.groups.linked_channels` are recognized as admin. Any other channel is not.
- Admin checks in `IsAdminFilter`, `is_chat_admin` and admin actions now share `services/admin_identity.py`.
- Auto-moderation handlers skip messages from recognized admins.
- New `services/moderation_log.py` adds a "Правило: ..." line to the logs chat for each auto-deletion and logs deletions that were silent before. Logging never raises and escapes user text for HTML.

Why:
- Anonymous admins were moderated like 0-reputation users and could not use admin commands.
- Moderators needed to see which rule caused each deletion.

Trade-offs:
- Admin status for "send as channel" depends on a config list of linked channels. Unlisted channels are not admins by design.
- Deletion now happens before the NSFW report is sent, so a delete failure is logged instead of losing the report.

Known shortcomings:
- Members posting as their own channel share one `from_user` id (136817688), so their reputation and violations are shared. Out of scope.
- Live Telegram scenario not run. mypy not run.
- `tests/test_newcomer_guard.py` has a pre-existing timing flake.
