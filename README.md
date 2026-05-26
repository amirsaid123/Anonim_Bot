# 🤖 Anonim_Bot

> A Telegram bot that lets anyone send you **anonymous messages** through your personal link — and reply back, still anonymously.

Every user gets a unique `https://t.me/<bot>?start=<token>` link they can share anywhere. Anyone who opens it can write to you without revealing their identity. You reply by swiping right on a message — Telegram's native reply gesture — and your reply goes back anonymously too.

Built with care for **privacy, multi-language users, and small-scale community moderation**.

---

## ✨ Features

- 💌 **Anonymous messaging via personal links** — share once, receive forever.
- ↩️ **Two-way anonymous conversations** — reply by swiping right, just like a normal chat.
- 🎭 **Stable per-pair nicknames** — repeat senders look consistent (`Curious Falcon #842`) to receivers without exposing identity.
- ✏️ **Custom welcome message** — greet anyone who opens your link (up to 300 chars).
- 🌍 **Multi-language UI** — English, Russian, Uzbek; locale persists across restarts.
- 📊 **Personal stats** — total / weekly received & sent, unique senders, top sender.
- 🚫 **One-tap block** — block any anonymous sender right from the message they sent.
- 🔗 **Opaque link tokens** — Telegram IDs never appear in URLs; tokens are base62, 8 chars.
- 👑 **Admin panel** — DB-managed admins + a super-admin. Admin reveal shows real identity *and* the anonymous handle side-by-side for moderation.
- 📢 **Broadcasts** — preview / confirm flow with rate-limited delivery.
- 📈 **Admin dashboard v2** — 7-day growth chart, activation rate, weekly cohort retention, top senders / receivers, viral links, locale distribution.

---

## 🛠 Tech stack

| | |
|---|---|
| Language | **Python 3.12** (asyncio) |
| Telegram | **aiogram 3.22** |
| Database | **PostgreSQL** via **SQLAlchemy 2** + **asyncpg** |
| i18n | **Babel 2.17** (`.po` / `.mo`) |
| Secrets | **python-dotenv** |

---

## 🚀 Quick start

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/amirsaid123/Anonim_Bot.git
cd Anonim_Bot
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
TOKEN=123456789:your_telegram_bot_token
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=anonim_bot
DB_HOST=localhost
DB_PORT=5432
```

### 3. Start PostgreSQL

If you have Docker:

```bash
docker run -d --name postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=anonim_bot \
  -p 5432:5432 \
  postgres:alpine
```

### 4. Run the bot

```bash
.venv/bin/python main.py
```

Tables are created automatically on first boot — there is no Alembic. `create_tables.py` runs `Base.metadata.create_all` plus idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements for newer columns.

---

## 🗂 Project layout

```
main.py                      Entry point (single asyncio.run)
bot/
  dispatcher.py              Bot + Dispatcher instances
  middlewares.py             FSMI18nMiddleware
  handlers/main_router.py    All message + callback handlers
  functions/                 FSM states, button builders, nicknames, tokens
database/
  models.py                  User, Comment, Message, Admin, Block, LinkToken
  functions.py               All DB helpers (queries, inserts, stats)
  session.py                 async context manager for sessions
locales/
  en|ru|uz/LC_MESSAGES/      Per-language .po (source) + .mo (compiled)
utils/                       Config + env loading
Makefile                     pybabel shortcuts
```

---

## 🌍 Working with translations

After adding or editing any `_("…")` / `__("…")` string:

```bash
# 1. Extract translatable strings into the template
.venv/bin/pybabel extract --input-dirs=. -o locales/messages.pot

# 2. Sync per-language .po files with the new template
.venv/bin/pybabel update -d locales -D messages -i locales/messages.pot

# 3. Edit locales/{en,ru,uz}/LC_MESSAGES/messages.po — fill in msgstr entries

# 4. Compile .po → .mo
.venv/bin/pybabel compile -d locales -D messages
```

Or use the shortcuts: `make extract`, `make update`, `make compile`.

> ⚠️ Babel can't extract f-strings. Use `_("Hello {name}").format(name=value)` — **never** `_(f"Hello {name}")`.

---

## 🛡 Privacy & moderation

- Sender Telegram IDs **never** appear in URLs — opaque tokens are used.
- Outgoing anonymous messages have `protect_content=True` for normal receivers (Telegram blocks copy / forward).
- Admin receivers see **both** the real identity (name, username, ID, profile link) **and** the anonymous nickname the receiver-side sees — so admins can correlate moderation conversations without breaking the privacy contract for everyone else.
- Block button is attached to every received message; blocks are stored in `blocks` (composite PK) and enforced before delivery.

---

## 🗺 Roadmap

Planned but not yet built:

- 💎 **Premium via Telegram Stars** — paid custom links, vanity nicknames, tip-with-message.
- 🤝 **Referral system** — grow first, monetize second.
- 🔄 **Reset my link** — rotate token to kill old shared links.
- 🧮 **Per-link analytics UI** — `link_tokens.label` + `hits` columns already exist; UI is the missing piece.

---

## 📄 License

TBD — pick a license before going public. MIT or Apache-2.0 are the usual choices for small open-source Telegram bots.
