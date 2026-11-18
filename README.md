# AutoPoster

AI-written social media posts, published on a schedule to **X (Twitter)** and **LinkedIn**.

You describe a topic (a "niche"), connect your accounts, and choose how many posts a day you want. AutoPoster writes
each day's posts with AI, spreads them across the day, and publishes them, after your approval if you ask for it.
Everything is managed from a password-protected web dashboard.

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Quick start](#quick-start)
- [Connecting accounts](#connecting-accounts)
- [Configuration](#configuration)
- [Running in production](#running-in-production)
- [Upgrading from the original version](#upgrading-from-the-original-version)
- [API](#api)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)

## Features

- **X and LinkedIn:** each schedule posts to the account you choose; posts are written to suit the platform
  (short and punchy for X, longer and more professional for LinkedIn)
- **AI that knows your topic:** prompts include the niche's description, key message and hashtags, plus recent
  posts so it doesn't repeat itself. Works with OpenRouter or OpenAI.
- **Approval workflow:** review, edit, approve or reject posts before they go out, or let them publish automatically
- **Reliable publishing:**
  - a post can never be published twice
  - rate limits are retried a limited number of times
  - failures are recorded with the reason and can be retried
  - if the AI fails, nothing is posted, never placeholder text
- **Security:**
  - the dashboard needs a login
  - account tokens are encrypted in the database and never sent to the browser
  - nothing secret lives in the code
- **Manual posts:** write and schedule your own posts from the dashboard too

## How it works

```
 Niche ──┐
         ├─ Schedule (posts/day, approval?) ──▶ Planner ──▶ AI writes posts ──▶ Posts table
 Account ┘                                    (every 30 min,                       │
                                               fills today's slots)                ▼
                                                     Publisher (every minute) ──▶ X / LinkedIn
```

1. **Planner** runs every 30 minutes and fills each schedule's time slots for today.
   - It splits the posting window (default 07:00–23:00) into equal slots, e.g. 4 posts a day: 07:00, 11:00, 15:00, 19:00.
   - It only writes posts for slots that haven't been filled and haven't passed yet.
   - Running it repeatedly is safe, and a run that failed (e.g. because the AI was down) is completed next time.
2. **Posts** that need approval wait as *Awaiting approval*. Others are *Scheduled*.
3. **Publisher** runs every minute and publishes scheduled posts whose time has come.

| Post status | Meaning |
|---|---|
| Awaiting approval | Written; waiting for you to approve, edit or reject it |
| Scheduled | Will publish at its time |
| Publishing | Being sent right now |
| Posted | Live; the dashboard links to it |
| Failed | Couldn't be published; the reason is shown, and you can edit and retry |
| Rejected | You rejected it; it won't be published or rewritten |

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/dawani519/autoposter.git
cd autoposter
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set at least:

```bash
ADMIN_PASSWORD=choose-a-strong-password
ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
AI_API_KEY=your-openrouter-or-openai-key
```

Then:

```bash
python main.py        # http://localhost:5000  (user: admin)
```

Without `DATABASE_URL`, data goes in a local SQLite file (`autoposter.db`).

In the dashboard:

1. **Accounts:** add your X or LinkedIn account. It's verified as soon as you save it.
2. **Niches:** add a topic, its description, key message and hashtags.
3. **Schedules:** pick a niche, an account, posts per day, and whether you want to approve posts.
4. **Scheduler > Write posts:** see today's posts straight away, or wait for the next automatic run.

## Connecting accounts

Account keys are entered in the dashboard (not in `.env`) and stored encrypted.

### X (Twitter)

1. In the [X developer portal](https://developer.x.com/en/portal/dashboard), create a project and app.
2. In the app's **User authentication settings**, set permissions to **Read and write**.
3. Under **Keys and tokens**, copy the API key and secret, then generate an access token and secret.
   Generate them *after* setting Read and write, or they'll be read-only.
4. Paste all four into **Accounts > Add account > X**.

X's free API tier allows only a small number of posts per month. Check your plan's limits before choosing posts per
day.

### LinkedIn

1. Create an app at [LinkedIn Developers](https://www.linkedin.com/developers/apps). It must be linked to a
   LinkedIn company page; any page you admin will do.
2. Under **Products**, add **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
3. Under **Auth**, open the **OAuth 2.0 tools** token generator and create a token with the scopes
   `openid profile w_member_social`.
4. Paste the token into **Accounts > Add account > LinkedIn**. Verifying fills in your author URN
   (`urn:li:person:...`) automatically.

**Posting as a company page** instead of yourself needs the `w_organization_social` scope. That requires LinkedIn's
Community Management API approval, and you must be an admin of the page. Enter the page's URN
(`urn:li:organization:12345`) as the author URN.

**LinkedIn tokens expire after 60 days.** When one expires, posts fail with "access token is invalid or expired".
Delete the account, add it again with a new token, then pick it again in its schedules.

Posts are sent with LinkedIn's Posts API (`POST /rest/posts`). Text is escaped for LinkedIn's "little" format, so
characters like `( ) @ * _` appear exactly as written, and `#hashtags` stay clickable.

## Configuration

All settings are environment variables; `.env.example` lists them with comments.

| Variable | Default | Description |
|---|---|---|
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / none | Dashboard login. **Required.** |
| `ENCRYPTION_KEY` | none | Encrypts stored tokens. **Required.** If it changes, accounts must be added again. |
| `DATABASE_URL` | `sqlite:///autoposter.db` | PostgreSQL URL (`postgres://` accepted) |
| `AI_BASE_URL` | `https://openrouter.ai/api/v1` | Any OpenAI-compatible API. `OPENAI_URL` also works. |
| `AI_API_KEY` | none | Needed to write posts. `OPENAI_API_KEY` also works. |
| `AI_MODEL` | `openai/gpt-4o-mini` (`gpt-4o-mini` for OpenAI) | Model name |
| `TIMEZONE` | `UTC` | Timezone of the posting window, e.g. `Africa/Lagos` |
| `POSTING_WINDOW_START` / `_END` | `07:00` / `23:00` | Daily posting window |
| `MAX_POST_ATTEMPTS` | `3` | Attempts before a rate-limited post is marked failed |
| `RATE_LIMIT_RETRY_MINUTES` | `15` | Wait after a rate limit |
| `LINKEDIN_API_VERSION` | `202609` | LinkedIn API version (YYYYMM). Update it about yearly. |
| `RUN_SCHEDULER` | `true` | Run background jobs in the web process |
| `PLAN_INTERVAL_MINUTES` | `30` | How often the planner runs |
| `PORT` | `5000` | Web port |

## Running in production

`python main.py` runs the dashboard and the scheduler in one process, which is fine for Replit or a small VM. For a
production web server:

```bash
gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT wsgi:app
```

Use **one** gunicorn worker when `RUN_SCHEDULER=true`. Otherwise each worker runs its own scheduler. Publishing would
still be safe, because each post is claimed before it's sent, but planning could write extra posts. For more web
workers, set `RUN_SCHEDULER=false` and run the scheduler as its own process:

```bash
python worker.py
```

`GET /health` (no login needed) returns `{"status": "ok"}` for uptime checks.

## Upgrading from the original version

- **Database:** existing tables are upgraded automatically on startup.
  - New columns are added.
  - Old statuses are renamed: `draft` becomes *Awaiting approval*, `approved` becomes *Scheduled*.
  - Account tokens stored in plain text are encrypted.
- **X keys** are no longer read from `.env` (`X_API_KEY` etc.). Add the account in the dashboard, then edit each
  schedule to choose it. Schedules without an account are skipped.
- **AI key:** set `AI_API_KEY`. The old code had an OpenRouter key written into it. **That key is public in Git
  history, so revoke it in your OpenRouter dashboard.**
- **Removed:** the `/run-assign-posts`, `/run-due-posts` and `/start-scheduler` URLs. The scheduler now starts by
  itself, and the Scheduler page has buttons for manual runs.

## API

The dashboard uses a JSON API under `/api`, protected by the same login (HTTP Basic auth).

| Method & path | Purpose |
|---|---|
| `GET /api/stats` | Counts by status, scheduler status |
| `GET/POST /api/niches`, `PUT/DELETE /api/niches/{id}` | Niches |
| `POST /api/niches/{id}/hashtags`, `DELETE /api/hashtags/{id}` | Hashtags |
| `GET/POST /api/accounts`, `DELETE /api/accounts/{id}` | Accounts (tokens are write-only) |
| `POST /api/accounts/{id}/verify` | Check an account's credentials with the platform |
| `GET /api/platforms` | Supported platforms and their length limits |
| `GET/POST /api/schedules`, `PUT/DELETE /api/schedules/{id}` | Schedules |
| `GET /api/posts?status=...`, `POST /api/posts` | List posts, write a manual post |
| `PUT/DELETE /api/posts/{id}` | Edit or delete a post |
| `POST /api/posts/{id}/approve` · `/reject` · `/retry` | Change a post's status |
| `POST /api/run/plan` · `/api/run/publish` | Run the planner or publisher now |

Example:

```bash
curl -u admin:$ADMIN_PASSWORD -X POST http://localhost:5000/api/posts \
  -H "Content-Type: application/json" \
  -d '{"account_id": 1, "content": "Hello from AutoPoster", "scheduled_time": "2030-01-01T09:00:00Z"}'
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

The 68 tests cover:

- login and the API
- token encryption, including upgrading plain-text tokens
- planning: time slots, timezones, repeat runs, AI failures
- publishing: no double posts, retries, failures
- the AI client and the X and LinkedIn publishers, including LinkedIn text escaping

They use fake HTTP and make no network calls.

## Project structure

| Path | Purpose |
|---|---|
| `main.py` | Run the dashboard and scheduler (`python main.py`) |
| `wsgi.py` | Entry point for gunicorn |
| `worker.py` | Run only the scheduler |
| `autoposter/app.py` | Flask app, login, static files |
| `autoposter/api.py` | JSON API |
| `autoposter/planner.py` | Writes each day's posts into time slots |
| `autoposter/poster.py` | Publishes due posts |
| `autoposter/scheduler.py` | Background jobs (APScheduler) |
| `autoposter/ai.py` | AI post writing |
| `autoposter/publishers.py` | X and LinkedIn publishing |
| `autoposter/models.py`, `db.py` | Database tables, setup and upgrades |
| `autoposter/crypto.py` | Token encryption |
| `autoposter/config.py` | Settings |
| `static/` | Dashboard (HTML, CSS, JavaScript) |
| `schema.sql` | Reference schema (the app creates tables itself) |
| `tests/` | Test suite |

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| App won't start: "ADMIN_PASSWORD is required" / "ENCRYPTION_KEY" | Set them in `.env` or your host's secrets |
| "Stored token can't be decrypted" | `ENCRYPTION_KEY` changed. Restore the old key, or delete and re-add the accounts. |
| No posts are written | `AI_API_KEY` missing or invalid (see the Dashboard warning), or the schedule has no account |
| Posts stay *Scheduled* | The scheduler isn't running. Check the Scheduler page; with `RUN_SCHEDULER=false`, run `worker.py`. |
| X: "rejected the account's keys" | Wrong keys, or the access token was made before enabling Read and write |
| X: "refused the post" | Duplicate post text, or the app lacks write permission |
| LinkedIn: "invalid or expired" | Tokens last 60 days; add the account again with a new token |
| LinkedIn: "needs the w_member_social permission" | Add the Share on LinkedIn product and regenerate the token |
| LinkedIn: "API version ... has been retired" | Set `LINKEDIN_API_VERSION` to a current version |
| A post stuck in *Publishing* | The app stopped mid-publish. Check the platform to see whether it went out, then delete or retry it. |

## Limitations

- Text posts only: images and video aren't published yet (the `media_url` column is kept for later).
- LinkedIn tokens must be renewed by hand every 60 days.
- X post length is checked as plain characters. X counts links and some emoji differently, so a post near 280
  characters may still be rejected.
