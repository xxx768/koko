import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.database.connection import init_db, dispose_db
from app.routes import auth, users, admin, dashboard, notifications, withdrawal, insights, referral, analytics


BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — initialising database…")
    await init_db()
    logger.info("Database ready.")
    yield
    logger.info("Shutting down…")
    await dispose_db()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Nova Earns",
    description="Production-ready role-based authentication & user management system.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Security headers middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    if not settings.debug:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response


# ---------------------------------------------------------------------------
# Audit logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def audit_log(request: Request, call_next):
    response = await call_next(request)
    logger.info(
        "method=%s path=%s status=%s ip=%s",
        request.method,
        request.url.path,
        response.status_code,
        get_remote_address(request),
    )
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
TEMPLATE_DIR = Path(__file__).parent / "templates"

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(withdrawal.router)
app.include_router(insights.router)
app.include_router(referral.router)  
app.include_router(analytics.router)  # add




# ---------------------------------------------------------------------------
# HTML page routes
# ---------------------------------------------------------------------------

@app.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse(TEMPLATE_DIR / "login.html")


@app.get("/signup", include_in_schema=False)
async def signup_page():
    return FileResponse(TEMPLATE_DIR / "signup.html")


@app.get("/verify-email", include_in_schema=False)
async def verify_email_page():
    return FileResponse(TEMPLATE_DIR / "verify_email.html")


@app.get("/dashboard", include_in_schema=False)
async def dashboard_page():
    return FileResponse(TEMPLATE_DIR / "dashboard.html")


@app.get("/withdraw", include_in_schema=False)
async def withdraw_page():
    return FileResponse(TEMPLATE_DIR / "withdraw.html")


@app.get("/admin-dashboard", include_in_schema=False)
async def admin_dashboard_page():
    return FileResponse(TEMPLATE_DIR / "admin_dashboard.html")


@app.get("/survey-admin", include_in_schema=False)
async def survey_admin_page():
    return FileResponse(TEMPLATE_DIR / "survey_admin.html")


@app.get("/survey-user", include_in_schema=False)
async def survey_user_page():
    return FileResponse(TEMPLATE_DIR / "survey_user.html")


@app.get("/notifications-page", include_in_schema=False)
async def notifications_page():
    return FileResponse(TEMPLATE_DIR / "notifications.html")

@app.get("/insights", include_in_schema=False)
async def insights_page():
    return FileResponse(TEMPLATE_DIR / "insights.html")

# Add the page route:
@app.get("/admin-analytics", include_in_schema=False)
async def admin_analytics_page():
    return FileResponse(TEMPLATE_DIR / "admin_analytics.html")


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(TEMPLATE_DIR / "login.html")


# Some browsers request /favicon.ico automatically
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse(TEMPLATE_DIR / "favicon.svg")


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )
