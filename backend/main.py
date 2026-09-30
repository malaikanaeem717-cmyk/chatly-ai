"""
Chatly AI — Application Entry Point
=====================================
Run from the project root with: uvicorn backend.main:app --reload
"""
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.config import settings
from backend.logging_config import logger
from backend.exceptions import ChatlyError
from backend import auth_routes, chat_routes, document_routes, image_routes, health_routes

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = [k for k in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "SUPABASE_SERVICE_KEY") if not getattr(settings, k)]
    if missing:
        logger.warning("Missing Supabase config: %s — auth and database calls will fail until .env is set.", missing)
    logger.info("%s started (env=%s)", settings.APP_NAME, settings.ENV)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ChatlyError)
def handle_chatly_error(request: Request, exc: ChatlyError):
    logger.warning("Handled error on %s: %s", request.url.path, exc.message)
    return JSONResponse(status_code=exc.status_code, content={"success": False, "error": exc.message})


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"success": False, "error": "An unexpected error occurred. Please try again."})


app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(chat_routes.router)
app.include_router(document_routes.router)
app.include_router(image_routes.router)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/login")
def serve_login():
    return FileResponse(str(STATIC_DIR / "login.html"))
