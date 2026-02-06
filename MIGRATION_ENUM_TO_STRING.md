# Database Migration: PostgreSQL Enum to String

## Overview

This migration converts native PostgreSQL enum types to VARCHAR(50) columns for compatibility with SQLAdmin while preserving all existing data.

## Why This Change?

PostgreSQL native enums can cause issues with SQLAdmin:
1. **500 errors** when rendering enum dropdowns
2. **Type mismatch** issues with SQLAlchemy 2.0
3. **Migration complexity** when adding/removing enum values
4. **Better portability** - works with all databases, not just PostgreSQL

## Affected Tables and Columns

1. **users.role** - `ENUM(userrole)` → `VARCHAR(50)`
2. **wishlists.status** - `ENUM(wishliststatus)` → `VARCHAR(50)`
3. **orders.status** - `ENUM(orderstatus)` → `VARCHAR(50)`

## Migration Steps

### Option 1: Direct SQL (Fastest)

Connect to your PostgreSQL database and run:

```sql
-- Start transaction
BEGIN;

-- 1. Convert users.role
ALTER TABLE users 
    ALTER COLUMN role TYPE VARCHAR(50) USING role::TEXT;

-- 2. Convert wishlists.status
ALTER TABLE wishlists 
    ALTER COLUMN status TYPE VARCHAR(50) USING status::TEXT;

-- 3. Convert orders.status
ALTER TABLE orders 
    ALTER COLUMN status TYPE VARCHAR(50) USING status::TEXT;

-- 4. Drop the enum types (CASCADE will drop any remaining dependencies)
DROP TYPE IF EXISTS userrole CASCADE;
DROP TYPE IF EXISTS wishliststatus CASCADE;
DROP TYPE IF EXISTS orderstatus CASCADE;

-- Commit transaction
COMMIT;
```

**Verify the migration:**
```sql
-- Check column types
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name IN ('users', 'wishlists', 'orders')
  AND column_name IN ('role', 'status');

-- Should show: data_type = 'character varying', character_maximum_length = 50

-- Check existing data is preserved
SELECT role, COUNT(*) FROM users GROUP BY role;
SELECT status, COUNT(*) FROM wishlists GROUP BY status;
SELECT status, COUNT(*) FROM orders GROUP BY status;
```

### Option 2: Using Alembic Migration

Create a new Alembic migration:

```bash
cd /home/peini/Projects/jacob/zendora
alembic revision -m "convert_enums_to_strings"
```

Edit the generated migration file (in `alembic/versions/`):

```python
"""convert_enums_to_strings

Revision ID: xxxxx
Revises: xxxxx
Create Date: 2026-xx-xx

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'xxxxx'
down_revision = 'xxxxx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Convert users.role
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN role TYPE VARCHAR(50) USING role::TEXT
    """)
    
    # Convert wishlists.status
    op.execute("""
        ALTER TABLE wishlists 
        ALTER COLUMN status TYPE VARCHAR(50) USING status::TEXT
    """)
    
    # Convert orders.status
    op.execute("""
        ALTER TABLE orders 
        ALTER COLUMN status TYPE VARCHAR(50) USING status::TEXT
    """)
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS userrole CASCADE")
    op.execute("DROP TYPE IF EXISTS wishliststatus CASCADE")
    op.execute("DROP TYPE IF EXISTS orderstatus CASCADE")


def downgrade() -> None:
    # Recreate enum types
    op.execute("""
        CREATE TYPE userrole AS ENUM (
            'SUPER_ADMIN', 'MANAGER', 'ADMIN', 'VISITOR'
        )
    """)
    op.execute("""
        CREATE TYPE wishliststatus AS ENUM ('DRAFT', 'PUBLISHED')
    """)
    op.execute("""
        CREATE TYPE orderstatus AS ENUM (
            'PENDING', 'PAID', 'FAILED', 'REFUNDED'
        )
    """)
    
    # Convert back to enums
    op.execute("""
        ALTER TABLE users 
        ALTER COLUMN role TYPE userrole USING role::userrole
    """)
    op.execute("""
        ALTER TABLE wishlists 
        ALTER COLUMN status TYPE wishliststatus USING status::wishliststatus
    """)
    op.execute("""
        ALTER TABLE orders 
        ALTER COLUMN status TYPE orderstatus USING status::orderstatus
    """)
```

Run the migration:
```bash
alembic upgrade head
```

## Rollback Plan

If you need to rollback to enum types:

```sql
BEGIN;

-- Recreate enum types
CREATE TYPE userrole AS ENUM ('SUPER_ADMIN', 'MANAGER', 'ADMIN', 'VISITOR');
CREATE TYPE wishliststatus AS ENUM ('DRAFT', 'PUBLISHED');
CREATE TYPE orderstatus AS ENUM ('PENDING', 'PAID', 'FAILED', 'REFUNDED');

-- Convert columns back
ALTER TABLE users 
    ALTER COLUMN role TYPE userrole USING role::userrole;
ALTER TABLE wishlists 
    ALTER COLUMN status TYPE wishliststatus USING status::wishliststatus;
ALTER TABLE orders 
    ALTER COLUMN status TYPE orderstatus USING status::orderstatus;

COMMIT;
```

**Note**: Also revert code changes in the Git repository.

## Data Validation

After migration, verify data integrity:

```sql
-- Verify all user roles are valid
SELECT role, COUNT(*) 
FROM users 
WHERE role NOT IN ('SUPER_ADMIN', 'MANAGER', 'ADMIN', 'VISITOR')
GROUP BY role;
-- Should return 0 rows

-- Verify all wishlist statuses are valid
SELECT status, COUNT(*) 
FROM wishlists 
WHERE status NOT IN ('DRAFT', 'PUBLISHED')
GROUP BY status;
-- Should return 0 rows

-- Verify all order statuses are valid
SELECT status, COUNT(*) 
FROM orders 
WHERE status NOT IN ('PENDING', 'PAID', 'FAILED', 'REFUNDED')
GROUP BY status;
-- Should return 0 rows
```

## Testing After Migration

1. **API Tests**: Ensure all endpoints still work
   ```bash
   # Run your test suite
   pytest
   ```

2. **Manual Tests**:
   - Create a new user with each role
   - Create a wishlist and change its status
   - Create an order and verify status updates

3. **Admin Panel Tests**:
   - Login to `/admin`
   - View each model's list page
   - Edit records and verify enum dropdowns work
   - Create new records with different enum values

## Performance Impact

- **Minimal**: VARCHAR(50) has similar performance to enum types for small value sets
- **Indexes**: Existing indexes on these columns are preserved
- **Queries**: No changes needed to existing queries

## Storage Impact

- **Before**: ENUM (4 bytes per value)
- **After**: VARCHAR(50) (actual string length + 1-4 bytes overhead)
- **Typical values**: 5-12 characters, so 6-16 bytes per value
- **Impact**: ~10-12 bytes increase per row (negligible for most use cases)

## Common Issues

### Issue: "type X does not exist"
**Solution**: The enum types have already been dropped. This is expected after migration.

### Issue: "invalid input value for enum"
**Solution**: Check that all values in the database match the enum definitions exactly (case-sensitive).

### Issue: SQLAdmin still shows 500 error
**Solution**: 
1. Restart the application to reload models
2. Clear browser cache
3. Verify migration completed successfully

### Issue: Pydantic validation fails
**Solution**: Pydantic schemas still use enum types (UserRole, WishlistStatus, OrderStatus). This is correct - Pydantic handles string→enum conversion automatically.

## Production Deployment Checklist

- [ ] Backup database before migration
- [ ] Test migration on staging environment
- [ ] Schedule maintenance window (migration is fast but be safe)
- [ ] Run migration during low-traffic period
- [ ] Monitor application logs after deployment
- [ ] Verify admin panel works correctly
- [ ] Run smoke tests on critical endpoints
- [ ] Keep rollback SQL ready (just in case)

## Questions?

If you encounter any issues:
1. Check PostgreSQL logs: `tail -f /var/log/postgresql/postgresql-*.log`
2. Check application logs for SQLAlchemy errors
3. Verify all code changes from this PR are deployed
4. Ensure database and code are in sync (both migrated or both not migrated)
