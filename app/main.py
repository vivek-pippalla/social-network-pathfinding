import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from neo4j.exceptions import Neo4jError
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import routes_auth, routes_friends, routes_graph, routes_users
from app.api.errors import install_exception_handlers
from app.core.config import Settings, get_settings
from app.core.logging import request_id_var, setup_logging
from app.db.neo4j_db import close_driver, get_driver
from app.db.redis_cache import get_client
from app.domain.errors import UnavailableError

logger = logging.getLogger("app.access")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DESCRIPTION = "Social graph API for user profiles, friendship connections, pathfinding, and friend recommendations."


def create_app(
    settings: Settings | None = None,
    *,
    driver_provider=get_driver,
    redis_provider=get_client,
    driver_closer=close_driver,
) -> FastAPI:
    config = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            driver_provider()
            yield
        finally:
            driver_closer()

    application = FastAPI(
        title="Social Network Pathfinding API",
        description=DESCRIPTION,
        version="3.0.0",
        lifespan=lifespan,
        docs_url="/docs" if config.ENABLE_DOCS else None,
        redoc_url=None,
        openapi_url="/openapi.json" if config.ENABLE_DOCS else None,
    )
    application.state.driver_provider = driver_provider
    application.state.redis_provider = redis_provider
    install_exception_handlers(application)

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        candidate = request.headers.get("x-request-id", "")
        request_id = (
            candidate if REQUEST_ID_PATTERN.fullmatch(candidate) else uuid.uuid4().hex
        )
        request.state.request_id = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route = request.scope.get("route")
            route_template = getattr(route, "path", "unmatched")
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "route": route_template,
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                },
            )
            request_id_var.reset(token)

    if config.ALLOWED_ORIGINS:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=config.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )

    application.include_router(routes_auth.router)
    application.include_router(routes_graph.router)
    application.include_router(routes_users.router)
    application.include_router(routes_friends.router)
    application.mount("/static", StaticFiles(directory="app/static"), name="static")
    Instrumentator().instrument(application).expose(
        application, include_in_schema=False
    )

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/static/index.html")

    @application.get("/health", tags=["Health"], summary="Liveness check")
    async def health_check():
        return {"status": "ok"}

    @application.get(
        "/health/ready", tags=["Health"], summary="Dependency readiness check"
    )
    async def readiness_check(request: Request):
        try:
            driver = request.app.state.driver_provider()
            driver.verify_connectivity()
        except Exception as exc:
            if isinstance(exc, Neo4jError):
                raise UnavailableError("neo4j") from None
            raise UnavailableError("neo4j") from None

        redis_status = "ok"
        try:
            request.app.state.redis_provider().ping()
        except Exception:
            redis_status = "degraded"
        return {"status": "ok", "components": {"neo4j": "ok", "redis": redis_status}}

    return application


app = create_app()
