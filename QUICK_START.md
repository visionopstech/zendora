# Quick Start Guide

## Fresh Installation with Admin Panel

Follow these steps to get Zendora up and running with the admin panel.

### Prerequisites

- Docker and Docker Compose installed
- Python 3.11+ (if running outside Docker)
- PostgreSQL 15+ (if running outside Docker)

### Step 1: Clone and Configure

```bash
# Clone the repository (if not already done)
cd /home/peini/Projects/jacob/zendora

# Copy environment variables
cp .env.example .env

# Edit .env with your values
nano .env  # or use your preferred editor
```

**Important: Set your admin credentials in .env:**
```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here  # Change this!
```

### Step 2: Start with Docker Compose (Recommended)

```bash
# Remove old volumes (if restarting fresh)
docker-compose down -v

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f app
```

This will:
- Start PostgreSQL database
- Start Redis
- Run Alembic migrations automatically
- Start the FastAPI application
- Start Celery worker

### Step 3: Verify Installation

**Check API health:**
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "0.1.0"
}
```

**Access admin panel:**
1. Open browser: `http://localhost:8000/admin`
2. Login with credentials from your `.env` file
3. You should see the admin dashboard with all models

### Step 4: Create Initial Data (Optional)

Create some test users, products, and vendors through the admin panel or via API.

**Example: Create a SUPER_ADMIN user via API:**
```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "superadmin@example.com",
    "password": "securepassword",
    "full_name": "Super Admin",
    "role": "SUPER_ADMIN"
  }'
```

## Alternative: Manual Setup (Without Docker)

### 1. Set up Python environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Start PostgreSQL

```bash
# Using Docker
docker run -d \
  --name zendora-postgres \
  -e POSTGRES_DB=zendora \
  -e POSTGRES_USER=zendora \
  -e POSTGRES_PASSWORD=dev_password \
  -p 5432:5432 \
  postgres:15

# Or use your local PostgreSQL installation
```

### 3. Start Redis

```bash
# Using Docker
docker run -d \
  --name zendora-redis \
  -p 6379:6379 \
  redis:7

# Or use your local Redis installation
```

### 4. Run migrations

```bash
# Make sure DATABASE_URL in .env points to your PostgreSQL
alembic upgrade head
```

### 5. Start application

```bash
# Start FastAPI
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, start Celery worker
celery -A app.core.celery_app worker --loglevel=info
```

### 6. Access admin panel

Visit `http://localhost:8000/admin` and login with your credentials.

## Common Commands

### Database

```bash
# Create new migration
alembic revision -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

### Docker

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Remove volumes (fresh start)
docker-compose down -v

# View logs
docker-compose logs -f app

# Restart a service
docker-compose restart app

# Run migrations manually
docker-compose exec app alembic upgrade head

# Access Python shell in container
docker-compose exec app python
```

### Development

```bash
# Run tests
pytest

# Check linting
flake8 app/

# Format code
black app/

# Type checking
mypy app/
```

## Environment Variables Reference

### Required

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname

# JWT (for API authentication)
JWT_SECRET=your-secret-key-change-in-production

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# SendGrid
SENDGRID_API_KEY=SG...
SENDGRID_FROM_EMAIL=noreply@example.com

# Admin Panel
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change-this-password
```

### Optional

```bash
# JWT Configuration
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Redis
REDIS_URL=redis://localhost:6379/0

# Frontend
FRONTEND_URL=http://localhost:3000

# Environment
ENVIRONMENT=development  # or production

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Third-Party Auth
THIRD_PARTY_AUTH_URL=https://partner.com/verify
THIRD_PARTY_AUTH_TOKEN=optional-token
```

## Troubleshooting

### Database connection error

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL

# Test connection
docker-compose exec postgres psql -U zendora -d zendora
```

### Migration errors

```bash
# Check current migration status
docker-compose exec app alembic current

# View migration history
docker-compose exec app alembic history

# If stuck, reset database (WARNING: loses all data)
docker-compose down -v
docker-compose up -d
```

### Admin panel not accessible

1. Check app is running: `docker-compose ps`
2. Check logs: `docker-compose logs app`
3. Verify admin credentials in `.env`
4. Restart app: `docker-compose restart app`
5. Clear browser cache/cookies

### Redis connection error

```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
# Should return: PONG
```

## Next Steps

1. **Configure Stripe**: Add your Stripe keys to `.env`
2. **Configure SendGrid**: Add your SendGrid API key to `.env`
3. **Create test data**: Use the admin panel to create vendors, products, and wishlists
4. **Test checkout flow**: Create a wishlist and test the Stripe integration
5. **Set up frontend**: Configure the frontend to connect to the API

## Security Checklist for Production

- [ ] Change `ADMIN_PASSWORD` to a strong, unique password
- [ ] Change `JWT_SECRET` to a cryptographically secure random string
- [ ] Set `ENVIRONMENT=production` in `.env`
- [ ] Use HTTPS (set up SSL/TLS certificates)
- [ ] Configure firewall to restrict database access
- [ ] Enable PostgreSQL SSL connections
- [ ] Use strong database passwords
- [ ] Set up database backups
- [ ] Configure monitoring and logging
- [ ] Review and restrict CORS origins
- [ ] Set up rate limiting
- [ ] Enable Stripe webhook signature verification

## Documentation

- **API Documentation**: http://localhost:8000/docs
- **Admin Setup**: See `ADMIN_SETUP.md`
- **Migration Guide**: See `MIGRATION_ENUM_TO_STRING.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Full API Docs**: See `API_DOCUMENTATION.md`

## Support

For issues:
1. Check this guide and other documentation
2. Check application logs: `docker-compose logs -f`
3. Check PostgreSQL logs: `docker-compose logs postgres`
4. Verify environment variables are set correctly
5. Ensure all migrations have been applied: `alembic current`
