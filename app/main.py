from fastapi import FastAPI, Request, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
import logging

from app.core.config import settings
from app.core.database import engine
from app.core.exceptions import (
    ZendoraException,
    NotFoundException,
    ConflictError,
    PermissionDenied,
    UnauthorizedError,
    ValidationError,
)
from app.utils.logging import setup_logging
from app.admin import setup_admin

# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("🚀 Zendora API starting up...")
    logger.info(f"Environment: {settings.environment}")
    yield
    # Shutdown
    logger.info("👋 Zendora API shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Zendora API",
    description="Funeral-home gift collection platform with Stripe payments",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware for admin panel (must be before admin setup)
from starlette.middleware.sessions import SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret,
    session_cookie="admin_session",
    max_age=3600 * 24,  # 24 hours
    same_site="lax",
    https_only=settings.is_production,
)

# Setup admin panel
admin = setup_admin(app, engine)
logger.info("✅ Admin panel mounted at /admin")


# Exception handlers
@app.exception_handler(ZendoraException)
async def zendora_exception_handler(request: Request, exc: ZendoraException):
    """Handle custom Zendora exceptions."""
    logger.warning(f"Zendora exception: {exc.__class__.__name__} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "details": exc.details,
        },
    )


@app.exception_handler(UnicodeDecodeError)
async def unicode_decode_exception_handler(request: Request, exc: UnicodeDecodeError):
    """Binary uploads hitting a JSON body parser produce this error."""
    logger.warning("Binary body sent to a text/JSON endpoint: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        content={
            "error": "UnsupportedMediaType",
            "message": (
                "Received binary data on a JSON endpoint. "
                "Upload images with POST /api/files as multipart/form-data "
                "(field name: file), then send the returned url on the resource."
            ),
            "details": {"type": "UnicodeDecodeError"},
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected exception: {exc}", exc_info=True)
    if settings.is_production:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "message": str(exc),
                "details": {"type": exc.__class__.__name__},
            },
        )


@app.get("/openapi.json", include_in_schema=False)
@app.get("/api/openapi.json", include_in_schema=False)
async def openapi_json():
    return JSONResponse(app.openapi())


@app.get("/docs", include_in_schema=False)
@app.get("/api/docs", include_in_schema=False)
async def swagger_ui():
    # Relative URL so /api/docs fetches /api/openapi.json (works behind /api proxies).
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title=f"{app.title} - Swagger UI",
    )


@app.get("/redoc", include_in_schema=False)
@app.get("/api/redoc", include_in_schema=False)
async def redoc_ui():
    return get_redoc_html(
        openapi_url="openapi.json",
        title=f"{app.title} - ReDoc",
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": "0.1.0",
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Zendora API",
        "docs": "/api/docs",
        "health": "/health",
    }


# Import and include routers
from app.api import (
    auth,
    admin,
    wishlist_public,
    checkout,
    webhooks,
    tasks,
    vendors,
    products,
    users,
    orders,
    wallets,
    funeral_homes,
    gift_collections,
    default_gift_collections,
    families,
    director_settings,
    files,
)

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(wallets.router, prefix="/api", tags=["Wallets"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(funeral_homes.router, prefix="/api/funeral-homes", tags=["Funeral Homes"])
app.include_router(gift_collections.router, prefix="/api/gift-collections", tags=["Gift Collections"])
app.include_router(default_gift_collections.router, prefix="/api/default-gift-collections", tags=["Default Gift Collections"])
app.include_router(families.router, prefix="/api/families", tags=["Families"])
app.include_router(director_settings.router, prefix="/api", tags=["Director - Settings"])
app.include_router(files.router, prefix="/api/files", tags=["Files"])
app.include_router(admin.router, prefix="/admin", tags=["Admin - Vendors & Products"])
app.include_router(wishlist_public.router, prefix="/w", tags=["Public Gift Collection"])
app.include_router(checkout.router, prefix="/w", tags=["Checkout"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(tasks.router, prefix="/api", tags=["Background Tasks"])

upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
