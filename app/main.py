import logging
import ipaddress
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from neo4j.exceptions import Neo4jError
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api import routes_auth, routes_friends, routes_graph, routes_users
from app.api.errors import install_exception_handlers
from app.api.openapi import route_errors
from app.api.request_size import RequestBodyLimitMiddleware
from app.api.deps import get_current_user
from app.core.config import Settings, get_settings
from app.core.logging import request_id_var, setup_logging
from app.db.neo4j_db import close_driver, get_driver
from app.db.redis_cache import get_client
from app.db.schema import ensure_schema
from app.domain.errors import UnavailableError
from app.models.schemas import HealthResponse, ReadinessResponse
from app.services.cache_service import CacheService
from app.services.friend_service import FriendService

logger = logging.getLogger("app.access")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
INTERNAL_NETWORKS = tuple(
    ipaddress.ip_network(network)
    for network in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "::1/128",
        "fc00::/7",
    )
)
DESCRIPTION = (
    "Social graph API for user profiles, friendship connections, pathfinding, and "
    "friend recommendations. Request bodies are limited by MAX_REQUEST_BODY_BYTES "
    "(1 MiB by default)."
)


def require_internal_metrics_client(request: Request) -> None:
    """Allow loopback/private-network peers; ignore forwarded client headers."""
    host = request.client.host if request.client else ""
    try:
        address = ipaddress.ip_address(host.split("%", 1)[0])
    except ValueError:
        raise HTTPException(status_code=403, detail="Metrics are internal only.")
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if not any(address in network for network in INTERNAL_NETWORKS):
        raise HTTPException(status_code=403, detail="Metrics are internal only.")


def create_app(
    settings: Settings | None = None,
    *,
    driver_provider=get_driver,
    redis_provider=get_client,
    driver_closer=close_driver,
    schema_bootstrapper=ensure_schema,
) -> FastAPI:
    config = settings or get_settings()
    setup_logging()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            driver = driver_provider()
            if config.AUTO_SCHEMA:
                schema_bootstrapper(driver)
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
    application.state.settings = config
    cache_service = CacheService(
        redis_provider,
        positive_ttl=config.CACHE_TTL_SECONDS,
        negative_ttl=config.NEGATIVE_CACHE_TTL_SECONDS,
    )
    application.state.cache_service = cache_service
    application.state.friend_service = FriendService(
        on_graph_changed=cache_service.bump_version
    )
    install_exception_handlers(application)

    # Install before the request-context middleware below so rejections still receive
    # an access log and request ID from that outer middleware.
    application.add_middleware(
        RequestBodyLimitMiddleware, max_bytes=config.MAX_REQUEST_BODY_BYTES
    )

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
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; img-src 'self' data:; font-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Frame-Options"] = "DENY"
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
    instrumentator = Instrumentator().instrument(application)

    @application.get(
        "/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_internal_metrics_client)],
    )
    async def metrics():
        return Response(
            content=generate_latest(instrumentator.registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    @application.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/static/index.html")

    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Liveness check",
        operation_id="getHealth",
        responses=route_errors(),
    )
    async def health_check():
        return {"status": "ok"}

    @application.get(
        "/health/ready",
        response_model=ReadinessResponse,
        tags=["Health"],
        summary="Dependency readiness check",
        operation_id="getReadiness",
        responses=route_errors("UNAVAILABLE"),
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
