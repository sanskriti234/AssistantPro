# CoreSight Backend

FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL (Supabase-compatible, with pgvector).

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL etc.
```

### Local development database

The commands below mirror what's already been run and verified in this
repo's own dev sandbox (Ubuntu 24.04, PostgreSQL 16, pgvector 0.6.0):

```bash
sudo apt-get install -y postgresql postgresql-contrib postgresql-16-pgvector
sudo service postgresql start
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'postgres';"
sudo -u postgres psql -c "CREATE DATABASE coresight;"
```

### Migrations

```bash
alembic upgrade head       # applies migrations/versions/*, enables
                            # the vector + uuid-ossp extensions, creates
                            # the HNSW index and the partial unique index
```

Verified: this has been run against a **freshly dropped and recreated**
local database to confirm the schema is fully reproducible from migrations
alone (no manually-created tables outside Alembic's knowledge).

### Seed data (development only)

```bash
python -m app.seed
```

Creates 1 admin, 2 faculty, 1 academic session, 2 departments, 2 batches,
faculty-batch assignments, and 5 students (4 enrolled in one batch, with
face-enrollment *status* only - no fabricated embeddings). Login:
`admin@coresight.edu` / `admin`, `faculty@coresight.edu` / `faculty`,
`student@coresight.edu` / `student`.

### Run

```bash
uvicorn app.main:app --reload --port 8000
```

### Tests

```bash
# Uses a separate coresight_test database, created/dropped automatically
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/coresight_test \
  pytest tests/ -v
```

17 tests, all passing against a real Postgres instance - checking actual
database state and constraint violations (unique constraints, role
authorization, duplicate-attendance prevention, Google Form sync
idempotency), not just HTTP status codes.

## Deploying against Supabase

1. Create a Supabase project.
2. In Project Settings, enable the `vector` extension (Database →
   Extensions → search "vector" → Enable), or run
   `CREATE EXTENSION IF NOT EXISTS vector;` in the SQL editor once - Alembic's
   first migration also does this defensively.
3. Set `DATABASE_URL` to the Session or Transaction pooler connection string
   from Project Settings → Database → Connection string (use the `psycopg`
   driver form: `postgresql+psycopg://...`).
4. Set `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (server-side only -
   **never** send this to the frontend), `SUPABASE_ANON_KEY`.
5. Run `alembic upgrade head` against the Supabase connection string.
6. Run `python -m app.seed` only in a non-production project if you want
   demo data; skip it for a real deployment.

## Frontend feature -> API -> database mapping

| Frontend feature | Former mock (removed) | Real endpoint | Table(s) |
|---|---|---|---|
| Login | `mockDb.users` | `POST /api/auth/login` | `users`, `admins`/`faculty`/`students` |
| Admin dashboard | `mockDb.batches`, computed inline | `GET /api/dashboard/admin` | computed from `student_enrollments`, `face_enrollments`, `attendance_records` |
| Academic sessions | `mockDb.sessions` | `GET/POST /api/sessions`, `POST /api/sessions/{id}/toggle` | `academic_sessions` |
| Batches list/detail | `mockDb.batches` | `GET/POST /api/batches`, `GET /api/batches/{id}` | `batches`, `departments`, `courses` |
| Google Form generation | `mockDb.batches.form*` fields (fake status flip) | `POST /api/batches/{id}/generate-form` | `registration_forms` |
| Google Form response sync (manual/webhook, per-response) | N/A | `POST /api/registration/forms/{id}/submissions` | `registration_submissions` -> normalized tables |
| Google Form response sync (live, all active forms) | N/A | `POST /api/registration/sync` | same, plus `registration_forms.last_synced_at` |
| Google Form response sync (live, one form) | N/A | `POST /api/registration/forms/{id}/sync` | same |
| Automatic scheduled sync | N/A | (no endpoint - runs in-process) | `app/services/sync_scheduler.py`, or `python -m app.sync_worker` for cron |
| Student account activation | N/A | `POST /api/auth/activate` | `account_activation_tokens`, `users.is_active`/`password_hash` |
| Batch student roster | `mockDb.students` | `GET /api/batches/{id}/students` | `students`, `student_enrollments`, `face_enrollments` |
| Faculty management | `mockDb.faculty` | `GET /api/faculty` | `faculty`, `faculty_batches` |
| Face enrollment (per-sample) | `mockDb` random accept/reject | `POST /api/enrollment/validate-sample` | (no persistence per-sample; see limitations) |
| Face enrollment (finalize) | `mockDb.students.faceEnrolled` | `POST /api/enrollment/finalize` | `face_enrollments`, `face_embeddings` (pgvector) |
| Start/end attendance session | in-memory array | `POST /api/attendance/sessions/start`, `/end` | `attendance_sessions`, `subjects` |
| Live recognition frame | random mock outcome | `POST /api/attendance/frame` | `recognition_events`, `attendance_records` |
| Faculty attendance history | `mockDb.attendanceRecords` | `GET /api/attendance/history` | `attendance_records` (joined) |
| Student's own attendance | `mockDb.attendanceRecords` | `GET /api/attendance/my-history` | `attendance_records`, `attendance_sessions` (implied absences) |
| Admin/faculty analytics | hardcoded trend array | `GET /api/analytics/institution`, `/faculty` | computed from `attendance_records`, `recognition_events` |
| Settings | `mockDb.settings` object | `GET/PUT /api/settings` | `system_settings` |

## Google Cloud setup (registration form auto-generation)

`POST /api/batches/{id}/generate-form` creates a real Google Form via the
official Google Forms API - never by scraping or browser automation.
CoreSight authenticates as a single institutional Google account (OAuth 2.0
with an offline refresh token), not a service account: a bare service
account's forms are owned by an invisible-to-admins service-account Drive,
and the usual fix (Domain-Wide Delegation) requires a Google Workspace
domain, which not every CoreSight deployment will have. A one-time OAuth
grant against a real account (e.g. a registrar account) works for both
Workspace and plain Gmail accounts and keeps created forms visible in that
account's own Drive.

**1. Create/select a Google Cloud project** at
[console.cloud.google.com](https://console.cloud.google.com).

**2. Enable required APIs** (APIs & Services -> Library):
- **Google Forms API** - create/edit forms, read responses
- **Google Drive API** - required alongside Forms API for the `drive.file`
  scope (form files are Drive objects)

**3. Configure the OAuth consent screen** (APIs & Services -> OAuth consent
screen): External or Internal (Internal if using Google Workspace), app
name "CoreSight", add the account that will own the forms as a test user if
the app is in Testing mode.

**4. Create OAuth client credentials** (APIs & Services -> Credentials ->
Create Credentials -> OAuth client ID -> Application type: **Desktop app**).
Download the client ID and client secret.

**5. Obtain a refresh token** (one-time, from a machine with a browser,
logged into the Google account CoreSight should use):

```bash
cd backend
pip install -r requirements.txt   # includes google-auth-oauthlib
python scripts/get_google_refresh_token.py \
    --client-id YOUR_CLIENT_ID \
    --client-secret YOUR_CLIENT_SECRET
```

This opens a browser consent screen and prints a refresh token - copy it
into `.env`.

**6. Set environment variables** in `backend/.env`:

```
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_OAUTH_REFRESH_TOKEN=...
```

**7. Run the backend** (`uvicorn app.main:app --reload`) and, as an admin,
call `POST /api/batches/{id}/generate-form` (or click "Generate registration
form" on a batch's detail page in the UI).

**8. Verify the form exists** in the Drive of the Google account you
authorized - it will be titled "CoreSight Student Registration \u2014
\<batch name\> \u2014 Section \<section\>".

**9. Submit a test response** by opening the returned `formUrl` and filling
it in as a student would.

**10. Verify response synchronization**: the Forms API supports reading
responses directly via `forms.responses.list()` - no linked Google Sheet is
created or required (see `app/services/google_forms_service.py` module
docstring for why). `POST /api/registration/forms/{id}/submissions`
accepts one normalized row at a time and is idempotent on
`google_response_id`; a worker that polls `forms.responses.list()` and
calls this endpoint per new response is the only remaining piece (see
"Known limitations" below).

**Do not commit** `.env`, `credentials.json`, `token.json`, or any
`client_secret*.json` / `service-account*.json` file - `.gitignore` already
excludes these.

## Automatic Google Form response synchronization

Once a batch has a registration form (see above), CoreSight can pull new
responses in three ways - all going through the same underlying logic
(`app/services/registration_sync_orchestrator.py`), so they can't drift out
of sync with each other:

1. **In-process scheduler** (`app/services/sync_scheduler.py`) - runs every
   `GOOGLE_FORM_SYNC_INTERVAL_SECONDS` (default 300) inside the FastAPI
   process using APScheduler's `BackgroundScheduler`. Disabled by default;
   enable with `ENABLE_SYNC_SCHEDULER=true`. An in-process lock
   (`threading.Lock`) plus APScheduler's `max_instances=1` guarantee a slow
   sync never overlaps with the next scheduled tick - the tick is skipped,
   not queued.

   **Multi-worker warning**: if CoreSight runs with more than one
   uvicorn/gunicorn worker (`--workers N`), each worker is a separate
   process and would run its own scheduler if this were enabled everywhere.
   That's not unsafe (see "Duplicate prevention" below - concurrent syncs
   can't create duplicate students), but it wastes Google API quota running
   the same sync N times. Recommended: either run a single worker, or set
   `ENABLE_SYNC_SCHEDULER=true` on exactly one designated worker/process and
   `false` on the rest.

2. **Cron-friendly one-shot worker** (`python -m app.sync_worker`) - does
   one sync pass and exits. Use this instead of the in-process scheduler if
   your deployment platform already has a cron/scheduled-task feature, or
   for the same "exactly one triggering process" reason as above.

3. **Manual admin trigger** - `POST /api/registration/sync` (all active
   forms) or `POST /api/registration/forms/{id}/sync` (one form, useful for
   debugging). The "Sync Now" button on a batch's detail page in the admin
   UI calls the latter.

### How a sync pass works

```
registration_forms (status=ACTIVE)
        |
        v
google_forms_service.fetch_responses()   <- forms.responses.list()
        |
        v
registration_response_parser.parse_response()   <- pure, uses field_mapping
        |                                            (questionId -> field),
        |                                            never question text
        v
registration_sync.sync_submission()   <- one DB transaction per response
        |
        v
registration_submissions row (terminal status) + normalized student rows
```

### Question ID mapping

Each generated form's `registration_forms.field_mapping` JSONB column holds
`{field_key: google_question_id}`, captured from the **actual** `questionId`
values the Forms API returns when the questions are created
(`google_forms_service.create_registration_form`) - never guessed, never
matched by question title (titles can change; questionIds don't).
`registration_response_parser.parse_response()` uses this mapping, and only
this mapping, to read a response's answers.

### Submission states

```
PENDING -> PROCESSING -> SYNCED            (success)
PENDING -> PROCESSING -> REJECTED          (validation failed - permanent, never retried)
PENDING -> PROCESSING -> DUPLICATE         (roll number/email conflict - permanent, never retried)
PENDING -> PROCESSING -> FAILED            (DB/transient error - retried on next sync pass)
```

`SYNCED`, `REJECTED`, and `DUPLICATE` are terminal: a response in one of
these states is never reprocessed, even if it's fetched again (Google
doesn't offer a "since" filter on `responses.list`, so every sync pass
re-fetches the full response list and relies on this state check - not on
response order or timestamps - to decide what's actually new).
`registration_submissions.error_message` records why a `REJECTED`/
`DUPLICATE`/`FAILED` row ended up that way.

### Duplicate prevention (defense in depth)

1. `registration_submissions.google_response_id` - `UNIQUE` at the database
   level. The idempotency check in `sync_submission()`/`sync_form()` is a
   convenience; this constraint is what actually prevents two rows for the
   same response even under a race.
2. `students.roll_number` - `UNIQUE`. A second response with an
   already-used roll number under a **different** email is recorded as
   `DUPLICATE`, not silently merged or overwritten.
3. `users.email` - `UNIQUE`. Same handling for an email conflict.
4. Every multi-table write (user + student + enrollment + contacts +
   address + qualifications) happens inside one transaction
   (`sync_submission`) - a failure partway through rolls back everything,
   never leaving a user without a student or an enrollment pointing at
   nothing.
5. Concurrency: two sync passes (e.g. the scheduler and a manual trigger)
   processing the same response at the same time will have one succeed and
   one hit the `UNIQUE` constraint on `google_response_id` - handled as a
   `FAILED` (retryable) outcome for the loser, never a duplicate student.

### Profile photo handling

A Google Form file-upload answer is a Drive `fileId`, not a public URL or
inline binary data. `storage_service.upload_profile_photo_from_drive()`
downloads it server-side (using CoreSight's own OAuth credentials - the
student never needs Drive access) and re-uploads it to Supabase Storage,
storing only the resulting path in `students.profile_photo_path`. This step
is **best-effort**: a photo failure (wrong file type, Storage not
configured, etc.) is logged and skipped - it never fails the registration
itself. This is explicitly the student's profile photo, never used to
generate face embeddings - biometric enrollment stays a fully separate flow
initiated by the student from their own phone (`/enrollment/*`).

### Student account activation

A student created via sync has no usable password
(`registration_sync._temp_password_hash()`) and `users.is_active=False`.
`app/services/activation_service.py` issues a single-use, SHA-256-hashed,
48-hour-expiring token (`account_activation_tokens`) - the *raw* token is
generated once, in memory, and handed directly to
`send_activation_email()`; it is never stored, logged, or returned from any
API. `POST /api/auth/activate {token, newPassword}` (public - the student
has no credentials yet) redeems it, sets a real password, and flips
`is_active=True`.

`send_activation_email()` is a **documented stub** - it raises
`NotImplementedError`, which `registration_sync.py` catches and ignores
(the token still exists in the database either way). No SMTP/transactional
email provider is configured in this environment; a real deployment
implements that function to actually send the link.

### Retry behavior

| Failure type | Outcome | Retried? |
|---|---|---|
| Missing/invalid field (bad email, bad date, etc.) | `REJECTED` | No - permanent |
| Roll number/email conflict | `DUPLICATE` | No - permanent, needs a human to resolve |
| Database integrity error / transient DB issue | `FAILED` | Yes - next sync pass reprocesses the same row in place |
| Google API error fetching one form's responses | form skipped this pass, `REGISTRATION_SYNC_FAILED` audit logged | Yes - next scheduled/manual sync tries that form again; other forms are unaffected |

### Environment variables

```
GOOGLE_FORM_SYNC_INTERVAL_SECONDS=300   # scheduler interval, if enabled
ENABLE_SYNC_SCHEDULER=false             # see "multi-worker warning" above
```

(Google OAuth variables are shared with form generation - see "Google
Cloud setup" above; no additional Google config is needed for sync.)

## Real AI model integration

`POST /enrollment/validate-sample` and `POST /attendance/frame` are backed
by real inference - no random/simulated results remain anywhere in this
codebase (search for "random" in `app/services/attendance_service.py` or
`enrollment_service.py` and you'll find none).

```
image
  |
  v
SCRFD (app/ml/scrfd_detector.py)      <- face detection
  |
  v
MiniFASNetV2 (app/ml/liveness_detector.py)   <- liveness/anti-spoofing
  |
  v
ArcFace/AdaFace-slot (app/ml/face_embedder.py)   <- 512-d embedding
  |
  v
pgvector cosine-distance match against this batch's
enrolled students (attendance_service._find_nearest_enrolled_student)
  |
  v
existing attendance decision engine (unchanged)
```

`app/services/face_pipeline_service.py` is the only place the rest of the
app talks to the ML layer - `app/ml/*` details never leak into
`enrollment_service.py` or `attendance_service.py`.

### Model provenance - what's real and what's substituted

| Model | Status | Source |
|---|---|---|
| **SCRFD** (detection) | Real pretrained weights | `det_500m.onnx`, the InsightFace "buffalo" model pack, via a public GitHub Release |
| **Face embedding** (recognition) | Real pretrained weights, **not AdaFace** | `w600k_mbf.onnx` - a real ArcFace (MobileFaceNet) checkpoint, same GitHub Release |
| **MiniFASNetV2** (liveness) | Real pretrained weights | The official `.pth` checkpoint from `minivision-ai/Silent-Face-Anti-Spoofing` (Apache 2.0), converted to ONNX once (see below) |

**Why not AdaFace's own weights?** AdaFace's official checkpoints
(https://github.com/mk-minchul/AdaFace) are distributed via Google Drive or
Hugging Face Hub - neither is reachable from this environment's network
egress (only `github.com`/`raw.githubusercontent.com`/package registries
are). ArcFace and AdaFace are both margin-based face recognition losses
trained toward the same goal - a 512-d embedding compared by cosine
similarity - so `face_embedder.py` is written against that shared contract:
dropping in a real AdaFace ONNX export later requires no code changes,
only pointing `ADAFACE_MODEL_PATH` at the new file.

### Getting the weights

```bash
cd backend
bash scripts/download_model_weights.sh          # SCRFD + embedding model (ONNX, ready to use)
pip install -r requirements-dev.txt              # torch, only for the next step
python scripts/convert_minifas_to_onnx.py \
    --checkpoint models/2.7_80x80_MiniFASNetV2.pth \
    --output models/minifasnet_v2.onnx
```

The running application never needs `torch` - only `onnxruntime` (already
in `requirements.txt`). `requirements-dev.txt` is a one-time, throwaway
dependency for the conversion script only.

Set in `backend/.env`:
```
SCRFD_MODEL_PATH=models/det_500m.onnx
ADAFACE_MODEL_PATH=models/w600k_mbf.onnx
MINIFAS_MODEL_PATH=models/minifasnet_v2.onnx
```

If any of these three paths is empty or the file is missing,
`model_registry.load_models()` logs a clear `FACE_MODELS_NOT_CONFIGURED` /
`FACE_MODELS_LOAD_FAILED` message at startup and every recognition/
enrollment endpoint returns **HTTP 503** with a clear message - the
application never silently falls back to a fake result (verified: see
`tests/test_enrollment_and_attendance_ml.py`'s
`test_submit_frame_propagates_pipeline_unavailable` and the matching
503-via-API test).

### What's been verified, and how

Run against the **real, downloaded weights and the reference project's own
labeled sample images** (`tests/test_ml_pipeline_real.py` - skipped
automatically if the weight files aren't present):

- **Detection**: correctly finds exactly one face in a real photo; finds
  zero faces in a blank image; returns a real confidence score.
- **Embedding**: the same image processed twice yields >0.999 cosine
  similarity (deterministic); two different people's photos yield <0.6
  similarity (a real 512-d embedding that actually discriminates identity -
  this is the core "who is this" capability, and it works).
- **Liveness**: runs end-to-end and returns a real, structured score in
  [0, 1] for both a live and a spoof sample.

Also verified live (manually, not by an automated test): a full
enroll → start session → submit frame → verify → duplicate-attendance-blocked
walkthrough using synthetic-but-realistic embeddings, exercising every
branch of the real decision path in `attendance_service.submit_frame`.

**Known limitation - liveness discrimination is not yet calibrated.**
MiniFASNetV2's preprocessing was ported exactly from the reference
implementation (pixel scaling, BGR channel order, crop-box expansion
factor - all double-checked against the source). Despite that, running it
on the reference repo's own three labeled sample images (one live, two
spoof) does **not** currently produce correct live-vs-spoof separation: all
three score similarly low on the "live" class. The most likely cause is
that the reference project's crop-expansion parameter was empirically
tuned against **its own** face detector (RetinaFace), and SCRFD (used here,
per this task's requirement) produces a differently-shaped box that,
scaled by the same factor, may crop a meaningfully different region than
the model was trained on. This is a real, open integration/calibration gap
- not a fabricated result and not silently hidden: `LIVENESS_THRESHOLD` is
fully configurable, and `MiniFASLivenessDetector.check()` always returns
its real, honestly-computed score, never a forced pass. Until recalibrated
(e.g. by tuning the crop scale, or supplying a same-detector-trained
liveness model), do not treat `is_live` as a trustworthy security boundary
in production - the detection and identity-matching stages are solid, but
this one stage needs further work with visual/dataset access this
environment didn't have.

### Threshold units - a real seam, documented rather than papered over

The admin-configurable `system_settings` table (`recognition_threshold`,
`liveness_threshold`) predates this integration and uses a 0-100
percentage scale (from when scores were simulated in that same range). The
real pipeline's natural units are different - cosine similarity and
softmax probability, both 0-1 - so `attendance_service.submit_frame` uses
the new `FACE_SIMILARITY_THRESHOLD`/`LIVENESS_THRESHOLD` **environment**
variables for the actual decision, not the admin Settings page's stored
percentages (which would require an arbitrary, undocumented calibration
curve to reconcile - the task explicitly says not to invent one). The
admin Settings page and its underlying table are unchanged and still work
exactly as before; they just don't currently drive the real pipeline's
threshold. Reconciling these under one unit system (e.g. migrating
`system_settings` to store real 0-1 values, or calibrating a
percentage-to-similarity mapping against a validation dataset) is
follow-up work, not done here.

`recognitionScore`/`livenessScore` returned to the frontend and stored in
`recognition_events`/`attendance_records` **are** rescaled to 0-100
(`similarity * 100`) purely for display continuity with the existing UI's
"87%" style labels - only the threshold *comparison* happens in native 0-1
units internally.

### Performance

Models are loaded once at FastAPI startup (`app/main.py`'s `_startup` ->
`model_registry.load_models()`) and reused for every request - never
reloaded per call. `FACE_DEVICE=auto` (default) uses GPU only if
`onnxruntime-gpu` is installed and a CUDA device is actually available
(checked via `onnxruntime.get_available_providers()`, not assumed); the
plain `onnxruntime` package in `requirements.txt` is CPU-only and works
everywhere.

## Known limitations

These are the pieces the task explicitly asked to be called out rather than
silently faked:

1. **Google Form generation is real, tested code - not yet exercised
   against live Google APIs.** `app/services/google_forms_service.py` calls
   the actual Forms API v1 (`forms.create`, `forms.batchUpdate`,
   `forms.get`, `forms.responses.list`) with the documented request/response
   shapes, and `app/services/registration_form_service.py` handles
   idempotency (one form per batch, enforced additionally by a database
   UNIQUE constraint), transactional persistence (no DB row on API failure),
   and audit logging. This sandbox's network egress does not include
   `googleapis.com`, so no live call has been made from here - see "Google
   Cloud setup" above for the real path, and `tests/test_google_form_generation.py`
   for full coverage with the Google client mocked (form definition content,
   idempotency, failure handling, and role authorization all pass against a
   real Postgres database without any Google credentials).
2. **Live Google Forms/Drive API calls are not exercised in this
   environment.** This sandbox's network egress does not include
   `googleapis.com`, so `google_forms_service.fetch_responses()`,
   `create_registration_form()`, and `storage_service`'s Drive download are
   written against the documented API shapes but have not made a real
   network call from here. Everything downstream of a response object -
   question-ID mapping capture, parsing, validation, duplicate prevention,
   transactional student creation, activation token issuance - **is** real
   and tested against a real PostgreSQL database with the Google client
   mocked (`tests/test_registration_response_parser.py`,
   `tests/test_registration_sync_orchestrator.py`,
   `tests/test_activation.py`). `POST /api/registration/forms/{id}/submissions`
   also remains available as a direct, already-normalized entry point
   (useful for testing or a webhook-style integration).
3. **Real SCRFD + ArcFace(AdaFace-slot) + MiniFASNetV2 models are now
   integrated** - see "Real AI model integration" above for full details,
   provenance, what's been verified against real weights, and the one open
   item (liveness discrimination needs further calibration). This
   supersedes the earlier "no real models" limitation from a previous
   pass - `enrollment_service.py` and `attendance_service.py` no longer
   contain any random/simulated results.
4. **Face embedding dimension (512)** matches the real ArcFace checkpoint
   in use (`Settings.face_embedding_dim`) - confirmed via
   `FaceEmbedder.embedding_dim` at load time, not assumed.
5. **Frontend-side embedding collection**: resolved differently than
   originally anticipated. Rather than having the browser compute or relay
   embeddings, `enrollment_service.validate_sample` runs the real pipeline
   server-side on each captured frame and buffers the resulting embedding
   in memory, keyed by student ID; `finalize_enrollment` reads from that
   buffer and explicitly ignores any embeddings the client claims to
   supply (never trust client-supplied biometric data) - see
   `tests/test_enrollment_and_attendance_ml.py`'s
   `test_finalize_enrollment_ignores_client_supplied_embeddings`. The
   existing frontend contract (`POST .../finalize` with just a sample
   count) needed no changes.
6. **No subjects UI.** The existing frontend only ever had a free-text
   "subject" field, never a subject management page. To keep
   `attendance_sessions` normalized without adding UI the frontend never
   had, `subjects` is minimal (name-only) and rows are found-or-created by
   name when a session starts.
7. **Course inference.** The existing UI has no separate "course" concept
   - only a batch `name` (e.g. "CSE AIML 2027"). `Course` rows are
   found-or-created from that same batch name to satisfy the normalized
   schema without adding a field the frontend never collected.
8. **Activation email delivery is a documented stub.** The secure
   token/hashing/expiry/single-use mechanics in `activation_service.py` are
   real and tested (`tests/test_activation.py`), including a full
   token-to-login round trip via the API. What's not implemented is
   actually *sending* the email - no SMTP/transactional-email provider is
   configured in this environment. `send_activation_email()` raises
   `NotImplementedError` to make that explicit rather than pretending
   delivery happened; a real deployment implements that one function.
9. **Profile photo pipeline (Drive -> Supabase Storage) is real, unverified
   live code.** `storage_service.upload_profile_photo_from_drive()` is
   written against the documented Drive `files().get_media()` and Supabase
   Storage `upload()` APIs, and is wired into sync as a best-effort,
   non-blocking step - but has not been exercised against live credentials
   here for the same network-access reason as item 2.
10. **No timetable/class-schedule entity.** The spec doesn't define one, so
   the faculty dashboard's "today's classes" reflects assigned batches
   without a fixed time; the faculty member supplies the subject when
   starting a session, matching the existing UI.
