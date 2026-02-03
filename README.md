# Zendora MVP Backend

A wishlist-based gifting platform with Stripe payments, role-based access control, and third-party authentication.

## Tech Stack

- **Backend Framework**: FastAPI (async)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Authentication**: JWT
- **Payments**: Stripe Checkout
- **Emails**: SendGrid
- **Architecture**: Modular monolith

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Poetry (for local development)

### Development Setup

1. Clone the repository
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start services with Docker Compose:
   ```bash
   docker-compose up -d
   ```
4. Run migrations:
   ```bash
   docker-compose exec api alembic upgrade head
   ```
5. Access the API at http://localhost:8000
6. View API documentation at http://localhost:8000/docs

### Local Development (without Docker)

1. Install dependencies:
   ```bash
   poetry install
   ```
2. Activate virtual environment:
   ```bash
   poetry shell
   ```
3. Run the development server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Project Structure

```
app/
├── core/           # Configuration, database, security
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic schemas
├── services/       # Business logic
├── api/            # API routers
├── dependencies/   # FastAPI dependencies
├── templates/      # Email templates
└── utils/          # Helper utilities
```

## User Roles

- **SUPER_ADMIN**: Manages vendors and products
- **MANAGER**: Creates and manages wishlists, assigns admins
- **ADMIN**: Edits and publishes their assigned wishlists
- **VISITOR**: Public users who can purchase from published wishlists

## API Documentation

Once running, visit http://localhost:8000/docs for interactive API documentation.

## Database Migrations

Create a new migration:
```bash
alembic revision --autogenerate -m "Description"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migrations:
```bash
alembic downgrade -1
```

## License

Proprietary
