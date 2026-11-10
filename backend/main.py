from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi

from app.database import init_db
from app.routes.upload import router as upload_router
from app.routes.history import router as history_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    yield

    print("EvidentPay backend shutting down...")


app = FastAPI(
    title="EvidentPay API",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ANALYSIS_DIR = Path(__file__).resolve().parent / "uploads" / "analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/analysis", StaticFiles(directory=str(ANALYSIS_DIR)), name="analysis")


app.include_router(upload_router)
app.include_router(history_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        routes=app.routes
    )

    schema_name = (
        "Body_upload_screenshots_api_events__event_id__screenshots_post"
    )

    request_schema = (
        openapi_schema
        .get("components", {})
        .get("schemas", {})
        .get(schema_name, {})
    )

    file_items = (
        request_schema
        .get("properties", {})
        .get("files", {})
        .get("items", {})
    )

    file_items.pop("contentMediaType", None)
    file_items["format"] = "binary"

    app.openapi_schema = openapi_schema

    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/")
def home():
    return {
        "message": "EvidentPay backend is running!"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "application": "EvidentPay"
    }
