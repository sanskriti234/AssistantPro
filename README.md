# CoreSight

Role-based AI attendance system (Admin / Faculty / Student): React + TypeScript
frontend, FastAPI + SQLAlchemy + PostgreSQL/pgvector backend.

```
coresight/
├── src/            # frontend (Vite + React + TS + Tailwind)
└── backend/         # FastAPI + SQLAlchemy 2.x + Alembic + Postgres/pgvector
```

## Quick start

**1. Backend** — see `backend/README.md` for full setup, migrations, seed
data, and the Supabase deployment steps. Short version:

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL (Supabase or local Postgres)
alembic upgrade head
python -m app.seed      # optional: demo data
uvicorn app.main:app --reload --port 8000
```

**2. Frontend**

```bash
cp .env.example .env    # points VITE_API_BASE_URL at the backend above
npm install
npm run dev
```

## Demo accounts

Created by `backend/app/seed.py` (development only):

| Role    | Email                  | Password |
|---------|-------------------------|----------|
| Admin   | admin@coresight.edu    | admin    |
| Faculty | faculty@coresight.edu  | faculty  |
| Student | student@coresight.edu  | student  |

## How the frontend talks to the backend

Every page imports only from `src/api/*.ts` — no component calls `fetch`
directly. Those files call `src/api/client.ts`'s `request()`, which attaches
the JWT from login and hits the real FastAPI service at
`VITE_API_BASE_URL`. The backend is the source of truth for the actual
attendance decision, role authorization, and duplicate-attendance
prevention (enforced again at the database level) — the frontend only
renders whatever it returns.

## Structure

```
src/
├── api/           # backend-facing functions (real HTTP calls)
├── pages/         # admin/, faculty/, student/, auth/
├── components/
│   ├── layout/     # Sidebar, MobileNav, TopBar, AppLayout, RoleRoute
│   ├── camera/     # shared camera view (no business logic)
│   ├── enrollment/ # student face enrollment capture flow
│   ├── attendance/ # faculty live attendance + records table
│   └── common/     # Card, Button, StatCard, StatusPill, EmptyState
├── hooks/          # useCamera, useAttendanceSession
├── types/          # types mirroring backend response shapes
└── context/        # AuthContext (session/token handling)

backend/
├── app/
│   ├── database/models/  # SQLAlchemy models (normalized schema)
│   ├── schemas/           # Pydantic request/response shapes
│   ├── services/          # business logic (one file per domain)
│   ├── api/routes/        # FastAPI routers
│   └── core/               # config, security, auth dependencies
├── migrations/             # Alembic
└── tests/                  # pytest, run against a real Postgres db
```

`RoleRoute` (frontend) is a UX convenience only — the backend enforces
authorization server-side on every route; see `backend/app/core/deps.py`.

See `backend/README.md` for the full frontend-feature → API → database
table mapping and the documented known limitations (Google Sheets live
sync, real ML models, embedding dimension).
