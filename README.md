# Chatly AI — Full Stack RAG Assistant (Supabase + Python Auth)

## Folder structure (flat, on purpose)

```
chatly_ai/
├── backend/           <- every Python file lives directly here, no sub-folders
│   ├── main.py               entry point (run this with uvicorn)
│   ├── config.py              reads .env
│   ├── auth.py                  Python authentication logic (see below)
│   ├── auth_routes.py            /api/auth/*
│   ├── database.py                all Supabase table reads/writes
│   ├── models.py                   Pydantic request/response schemas
│   ├── chat_service.py               chat orchestration + RAG blending
│   ├── chat_routes.py                 /api/chat/*
│   ├── document_processing.py          PDF/DOCX/TXT -> text
│   ├── chunking.py                      sentence-aware chunking
│   ├── embeddings.py                     local sentence-transformers
│   ├── retrieval.py                       hybrid search + reranking + citations
│   ├── document_service.py                 upload orchestration
│   ├── document_routes.py                   /api/documents/*
│   ├── image_providers.py                    Pollinations + Hugging Face
│   ├── image_service.py                       prompt enhancement + fallback
│   ├── image_routes.py                         /api/images/*
│   ├── memory_service.py                        conversation memory/summary
│   ├── query_understanding.py                    intent detection
│   ├── exceptions.py, logging_config.py            shared utilities
│   └── health_routes.py                             /api/health
├── static/            <- every frontend file lives directly here, no sub-folders
│   ├── index.html, login.html
│   ├── styles.css
│   └── auth.js, api.js, state.js, ui.js, chat.js, documents.js, images.js, app.js
├── schema.sql           <- run this once in Supabase's SQL Editor
├── requirements.txt
├── .env.example
└── README.md
```

Every file is either directly in `backend/` or directly in `static/` — no
folder-inside-a-folder anywhere. Each file still has one clear job (that's
what keeps `main.py` from becoming a 1000-line dumping ground), it's just
that the "one job per file" organization is flat instead of nested.

## How Python-side authentication works (for explaining to your instructor)

Previously, the frontend called the Supabase JavaScript SDK directly for
login/signup — so there was no Python code doing authentication, which is
why that question was hard to answer. **That's changed.** Now:

1. The browser never talks to Supabase directly for auth. It calls **your
   FastAPI backend**: `POST /api/auth/signup` and `POST /api/auth/login`
   (see `static/auth.js` and `backend/auth_routes.py`).
2. `backend/auth.py` is the Python code that does the actual work, using
   the official `supabase-py` client:
   - `supabase.auth.sign_up({...})` — creates the account
   - `supabase.auth.sign_in_with_password({...})` — logs in, returns a JWT
     **access token**
3. The backend hands that access token back to the browser, which stores
   it (`localStorage`) and sends it as `Authorization: Bearer <token>` on
   every request afterward.
4. On every protected route, a FastAPI dependency —
   `auth.get_current_user()` in `backend/auth.py` — calls
   `supabase.auth.get_user(token)`, which asks Supabase to verify that JWT
   is valid and returns who it belongs to. If it's invalid or expired,
   the request is rejected with 401 automatically.

So the honest answer to "authentication kaise ho rahi hai, Python ki kya
use ki hai": **FastAPI (Python web framework) + the official `supabase-py`
client library**, using Supabase Auth's `sign_up` / `sign_in_with_password`
/ `get_user` methods, with the JWT passed as a Bearer token on each
request. No password ever touches your own database — Supabase handles
storing/hashing credentials; your Python code only ever handles the token.

## Setting up Supabase (you don't need to know Supabase beforehand)

1. Go to [supabase.com](https://supabase.com), sign up free, click **New
   project**. Pick any name/password/region and wait ~2 minutes for it to
   provision.
2. In your new project, go to **Settings → API**. You'll see three things
   you need for `.env`:
   - **Project URL** → `SUPABASE_URL`
   - **anon / public key** → `SUPABASE_ANON_KEY`
   - **service_role key** (click "reveal") → `SUPABASE_SERVICE_KEY`
   Never share the service_role key or put it in frontend code — it has
   full database access. It's only ever read by the Python backend.
3. Go to **SQL Editor → New query**, paste the entire contents of
   `schema.sql` from this project, and click **Run**. This creates all
   four tables (`conversations`, `messages`, `documents`, `chunks`) plus
   security policies.
4. (Optional, makes testing easier) Go to **Authentication → Providers →
   Email** and turn **off** "Confirm email" if you don't want to verify a
   real inbox while testing signup. Leave it on for anything real.

That's it — no manual table clicking, no separate auth setup. Supabase's
built-in Auth (email + password) is already active by default.

## Setup / Run

```bash
cd chatly_ai
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt   # you already have most of these cached — only
                                    # `supabase` and `pydantic[email]` are new

copy .env.example .env       # Windows: copy, Mac/Linux: cp
# edit .env: paste your SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY,
# and your GROQ_API_KEY

uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000` → you'll land on the login page automatically
(no token yet) → sign up → you're in.

## What the frontend/backend flow actually does

1. **Login/signup** (`static/login.html` + `auth.js`) → Python backend →
   Supabase Auth → JWT stored in the browser.
2. **Every other page** (`static/index.html` + `app.js`) checks for that
   token on load; no token → redirected straight back to `/login`.
3. **Sending a chat message** → `POST /api/chat` (with the Bearer token) →
   `chat_service.py` retrieves relevant document chunks (if any), calls
   Groq, saves both messages to Supabase, returns the reply.
4. **Uploading a file** → `POST /api/documents/upload` → text extracted →
   chunked → embedded locally → chunks saved to the `chunks` table in
   Supabase. The file itself is never saved as a file anywhere — its
   *content* goes into the database as text + embeddings, which is why it
   won't show up in your file explorer, only inside the chat UI as a file
   card (exactly like ChatGPT/Claude show an attachment).
5. **Generating an image** → `POST /api/images/generate` → tries
   Pollinations first, then Hugging Face → both the prompt and the
   resulting image get saved as messages, so it reappears correctly if you
   reopen that conversation later.
6. **Conversation history sidebar** → `GET /api/chat/conversations`,
   scoped to your logged-in user only (every query is filtered by
   `user_id`, and `_verify_ownership()` blocks you from ever loading
   someone else's conversation by guessing an ID).

## Notes

- `RERANK_ENABLED=true` by default downloads a small cross-encoder model
  on first use. Set it to `false` in `.env` if you'd rather skip that.
- Row Level Security is enabled in `schema.sql` as a second layer of
  protection, even though the backend already enforces per-user access in
  Python — if the service key ever leaked, RLS still stops cross-user
  reads at the database level.
