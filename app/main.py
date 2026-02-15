from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
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
    description="Wishlist-based gifting platform with Stripe payments",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
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
        "docs": "/docs",
        "health": "/health",
    }


# Import and include routers
from app.api import auth, admin, manager, admin_wishlist, wishlist_public, checkout, webhooks, tasks, vendors, products, users, orders, wishlists, manager_settings, wishlist_settings

app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(vendors.router, prefix="/api/vendors", tags=["Vendors"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(wishlists.router, prefix="/api/wishlists", tags=["Wishlists"])
app.include_router(admin.router, prefix="/admin", tags=["Admin - Vendors & Products"])
app.include_router(manager.router, prefix="/manager", tags=["Manager - Wishlists"])
app.include_router(manager_settings.router, prefix="/api", tags=["Manager - Settings"])
app.include_router(wishlist_settings.router, prefix="/api", tags=["Wishlist Settings"])
app.include_router(admin_wishlist.router, prefix="/admin", tags=["Admin - Wishlists"])
app.include_router(wishlist_public.router, prefix="/w", tags=["Public Wishlist"])
app.include_router(checkout.router, prefix="/w", tags=["Checkout"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(tasks.router, prefix="/api", tags=["Background Tasks"])
