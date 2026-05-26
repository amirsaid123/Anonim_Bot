# CLAUDE.md

Auto-loaded by Claude every session. Keep this current. **If you change a load-bearing pattern, update this file in the same commit.**

---

## What this bot is

**Anonim_Bot** — a Telegram anonymous-message bot.

- Each user owns a personal `https://t.me/<bot>?start=<token>` link.
- Anyone who opens that link can send the receiver an anonymous message.
- Receivers reply by swiping right (Telegram's reply-to feature). Their reply goes back anonymously.
- Admins (super-admins + DB admins) see the sender's real identity for moderation; regular receivers only see an anonymous nickname.
- Multi-lingual (EN / RU / UZ) via Babel.

---

## Tech stack

- **Python 3.12** in a venv at `.venv/`. Always use `.venv/bin/python`, never the system `python3` (which is 3.14 and lacks the project deps).
- **aiogram 3.22** — async Telegram framework.
- **SQLAlchemy 2** with **asyncpg** driver — async ORM on PostgreSQL.
- **Babel 2.17** — `.po` / `.mo` translation pipeline.
- **python-dotenv** — secrets loaded from `.env` (copy from `env_copy` template if missing).

---

## Run / dev workflow

```bash
# from /home/amirsaid123/PycharmProjects/Anonim_Bot

.venv/bin/python main.py              # start the bot (polling)

# Translation pipeline after editing any _() or __() string:
.venv/bin/pybabel extract --input-dirs=. -o locales/messages.pot
.venv/bin/pybabel update -d locales -D messages -i locales/messages.pot
# ...edit locales/{en,ru,uz}/LC_MESSAGES/messages.po to fill new msgstr entries...
.venv/bin/pybabel compile -d locales -D messages

# Static check after any code change:
.venv/bin/python -m py_compile <changed files>

# Import smoke test (catches import-time errors before booting):
TOKEN=dummy1234567890:AAGfake_for_import_check DB_USER=x DB_PASSWORD=x \
DB_NAME=x DB_HOST=localhost DB_PORT=5432 \
.venv/bin/python -c "from bot.handlers.main_router import main; print('OK')"
```

---

## Project layout

```
main.py                          Entry point. Single asyncio.run(boot()).
bot/
  dispatcher.py                  Bot + Dispatcher instances. Default parse_mode=HTML.
  middlewares.py                 FSMI18nMiddleware registration.
  handlers/
    __init__.py                  Includes main_router into dp.
    main_router.py               ALL message + callback handlers (25 + 9).
    functions.py                 send_comment_to_admin_group helper.
  functions/
    __init__.py                  Re-exports make_reply_button, UserStates, etc.
    States.py                    UserStates + LanguageStates FSM groups.
    make_reply_button.py         make_reply_button + make_back_button + make_language_button.
    make_inline_button.py        make_inline_button (callback_data = first emoji of label).
    nicknames.py                 Deterministic SHA-256 hash → "Adjective Animal #NNN".
    tokens.py                    generate_token() — base62 8-char.
database/
  models.py                      SQLAlchemy models: User, Comment, Message, Admin, Block, LinkToken.
  functions.py                   All DB helpers (queries, inserts).
  session.py                     get_db_session — @asynccontextmanager. ALWAYS use `async with`.
  create_tables.py               Base.metadata.create_all + idempotent ALTER TABLE.
locales/
  messages.pot                   Generated template.
  en|ru|uz/LC_MESSAGES/          Per-language .po (source) + .mo (compiled).
utils/
  config.py                      MainConfig — loads env vars (TOKEN, DB_*).
  path.py                        ENV_PATH helper.
Makefile                         pybabel shortcuts: extract / init / update / compile.
```

---

## Database schema (key tables)

- **`users`**: telegram_id PK, user_name, first_name, last_name, **welcome_message** (premium-ish, max 300 chars), **locale** (`'en'|'ru'|'uz'`, persisted so language survives bot restart), joined_date.
- **`messages`**: id PK, sender_id FK, receiver_id FK, telegram_message_id, text, created_at (indexed).
- **`comments`**: id PK, user_id FK, comment, created_at.
- **`admins`**: telegram_id PK. DB-managed admins (separate from hardcoded `SUPER_ADMIN`).
- **`blocks`**: blocker_id + blocked_id composite PK (both FK CASCADE to users), created_at.
- **`link_tokens`**: token VARCHAR(32) PK, user_id FK CASCADE, **is_custom** BOOL (foundation for future paid custom links), **label** VARCHAR(100), created_at, **hits** INT.

Migrations: there's no Alembic. `create_tables.py` does `Base.metadata.create_all` (creates missing tables) plus idempotent `ALTER TABLE users ADD COLUMN IF NOT EXISTS welcome_message TEXT` / `... locale VARCHAR(8)`. If you add new columns, add an ALTER there.

---

## Patterns to preserve

1. **DB sessions** — `async with get_db_session() as session:`. Never the old `session = await get_db_session()` then `await session.close()` pattern (it returns a closed session — that bug was already fixed; don't reintroduce).
2. **i18n templates** — `_("Hello {name}").format(name=...)`. **NEVER** `_(f"Hello {name}")` — Babel can't extract f-strings.
3. **Lazy gettext for filters** — `F.text == __("Back ◀️")`. Static gettext for runtime — `_(...)`.
4. **Receiver-side rendering** — when building a message for delivery to another user (in `send_anon`, `handle_reply`), wrap the caption build in `with i18n.use_locale(receiver_locale):` where `receiver_locale = await get_user_locale(session, receiver_id) or "en"`. The handler runs in the *sender's* locale by default; this is what flips it for receiver-facing strings while keeping sender notifications in the sender's locale.
5. **Anonymous nickname for repeat senders** — `make_nickname(sender_id, receiver_id)` from `bot/functions/nicknames.py`. Pure function, deterministic, no storage. Same pair always produces the same handle.
6. **Link generation** — never expose `telegram_id` in URLs. Use `get_or_create_default_link_token(session, user_id)` from `database/functions.py`. The result is a stable per-user base62 token.
7. **Token resolution in `start_handler`** — if `command.args.isdigit()`, treat as legacy bare-ID (kept working for backward-compat). Else `await resolve_link_token(session, arg)`.
8. **Admin reveal vs privacy** — outgoing anonymous messages have `protect_content=True` for normal receivers (Telegram blocks copying/forwarding). Set `protect_content=False` only when receiver is an admin so they can copy IDs/usernames. Wrap copyable fields in `<code>...</code>` with `html.escape` first.
9. **Sender-side strings stay outside `use_locale`** — the "💌 Message sent anonymously!" success notice, "🚫 This user has blocked you" rejection, etc. — those are for the sender and must render in the sender's own locale.

---

## Anti-patterns we already fixed — DO NOT reintroduce

- `message.from_user.idwai` — typo for `.id` (crashed the comments flow).
- `async with AsyncSessionLocal() as session: return session` — closes the session before returning.
- `select(...).where(telegram_message_id == X)` without filtering on `current_user_id` — caused silent wrong-partner replies when telegram_message_id collisions.
- `i18n.current_locale = code` — wrong API for `FSMI18nMiddleware`. Use `with i18n.use_locale(code):`.
- `datetime.utcnow()` against `DateTime(timezone=True)` columns — deprecated in 3.12 and inserts naive into TZ-aware. Use `datetime.now(timezone.utc)` (there's a `_utcnow()` helper in `database/functions.py`).
- Two separate `asyncio.run(...)` calls in `main.py`. Single `boot()` coroutine, single `asyncio.run`.
- Hardcoded English in admin panel / sender reveal — everything user-visible goes through `_()`.

---

## Configuration / hardcoded constants worth knowing

- `SUPER_ADMIN = [7634998249]` — in `bot/handlers/main_router.py`. Eventually move to `.env`.
- `ADMIN_GROUP_ID = -5099315325` — in `bot/handlers/functions.py` (forwards user-submitted "Comments and Offers"). Eventually move to `.env`.
- `WELCOME_MESSAGE_MAX_LEN = 300` — in `main_router.py`.
- `BROADCAST_RATE_DELAY = 0.05` — sleep between sends in admin broadcast (~20 msg/s, well under Telegram's 30/s flood limit).

---

## Current state (as of last session)

**The bot is in a known-good state. No half-finished features.**

Recent rounds shipped (in chronological order):
1. **Logic bug fixes** — 12 correctness bugs across `main_router.py`, `database/functions.py`, `database/session.py`, `main.py`.
2. **i18n completeness pass** — wrapped all hardcoded admin strings in `_()`, added missing `Back 🔙` handler for the language menu, full RU + UZ translations.
3. **Engagement push (6 features)** — custom welcome message, persistent locale (`users.locale`), personal stats, anonymous nicknames, block sender (`blocks` table + inline Block button on every received message), admin broadcast flow. Main menu reorganized into a Settings sub-menu.
4. **Locale-direction fix** — `send_anon` + `handle_reply` now render receiver-facing captions in the receiver's locale via `i18n.use_locale(...)`.
5. **People-metrics in My Stats** — Unique senders + Top sender nickname/count.
6. **Opaque link tokens** — `?start=<token>` instead of `?start=<telegram_id>`. New `link_tokens` table. Backward-compatible with legacy bare-ID URLs.
7. **Admin copyability** — admin-bound messages use `protect_content=False`, with name + username + ID all wrapped in `<code>` for tap-to-copy.

---

## Planned but NOT built (user said "later")

- **Paid features via Telegram Stars** — premium subscriptions (~50 ⭐/month), custom paid links (uses `LinkToken.is_custom=true`), tip-with-message, paid vanity nicknames. User wants this eventually; warned them off "View profile" (doxxing tool / Telegram ToS risk).
- **Referral system** — grow first, monetize second.
- **"Reset my link" button** — regenerates the user's token, kills the old one. Easy add (just delete the row, next `create_link_handler` press generates a fresh one).
- **Multi-link / per-platform analytics** — the `link_tokens.label` + `hits` columns already exist for this; UI is the missing piece.

---

## User preferences (carry these into how you respond)

- **Exploratory questions get text answers, not AskUserQuestion menus.** When user asks "what is X?" / "how does X work?" / "is X good or bad?", just answer in narrative. They pivot topics mid-thought; don't drag them back.
- **AskUserQuestion is welcome when they say "let's build X"** — choosing between concrete approaches is fine.
- **"No bugs" is a real bar.** Always run py_compile, import smoke test, and (for DB changes) a synthetic round-trip in a Python REPL before declaring done. State what was verified vs what still needs the user to test in real Telegram.
- **Honest pushback on risky features.** If a feature has ToS / privacy / doxxing risk, flag it before planning. Offer safer alternatives. The user values this and will pick a better path.
- **The user writes informal English with typos in three languages.** Interpret intent, don't fixate on spelling.

---

## When in doubt

- Don't expose Telegram IDs in URLs.
- Don't break the anonymity promise — that's the bot's value prop.
- Use plan mode for any non-trivial change. Write the plan to `/home/amirsaid123/.claude/plans/...md`, then `ExitPlanMode` for approval.
- Read this file. Then read the relevant code files. Then plan.
