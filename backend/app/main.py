from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import departments
from app.api.routes import analytics, attendance, auth, batches, dashboard, enrollment, registration, settings, students
from app.core.config import get_settings

settings_obj = get_settings()

app = FastAPI(title="CoreSight API", version="0.1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_obj.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(batches.router, prefix="/api")
app.include_router(enrollment.router, prefix="/api")
app.include_router(attendance.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(students.router, prefix="/api")
app.include_router(registration.router, prefix="/api")
app.include_router(departments.router, prefix="/api")

@app.get("/api/health")
def health():
    from app.services import model_registry

    return {"status": "ok", "faceModelsReady": model_registry.is_ready()}


@app.on_event("startup")
def _startup():
    from app.services.sync_scheduler import start_scheduler
    from app.services import model_registry

    # Never raises - a missing/broken model leaves recognition endpoints
    # returning 503 rather than crashing the whole application (Step 9).
    model_registry.load_models()
    start_scheduler()


@app.on_event("shutdown")
def _shutdown():
    from app.services.sync_scheduler import stop_scheduler

    stop_scheduler()
