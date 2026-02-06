# Zendora Admin Panel Setup

## Overview

This document describes the Starlette Admin (SQLAdmin) integration for the Zendora project. The admin panel provides a web-based interface for SUPER_ADMIN users to manage all database entities.

## What Was Changed

### 1. Database Model Changes - Enum to String Migration

All PostgreSQL native enums have been converted to VARCHAR(50) columns to avoid compatibility issues with SQLAdmin:

- **User.role**: `ENUM(userrole)` → `VARCHAR(50)`
- **Wishlist.status**: `ENUM(wishliststatus)` → `VARCHAR(50)`
- **Order.status**: `ENUM(orderstatus)` → `VARCHAR(50)`

**Python enums are still used** for validation in Pydantic schemas and business logic, but the database now stores them as plain strings.

### 2. Code Changes for Enum Migration

All enum comparisons have been updated to use `.value`:

**Before:**
```python
if user.role == UserRole.ADMIN:
    # do something
```

**After:**
```python
if user.role == UserRole.ADMIN.value:
    # do something
```

**Files modified:**
- `app/models/user.py`
- `app/models/wishlist.py`
- `app/models/order.py`
- `app/services/user_service.py`
- `app/services/wishlist_service.py`
- `app/services/order_service.py`
- `app/dependencies/auth.py`
- `app/dependencies/permissions.py`

### 3. New Dependencies Added

Added to `requirements.txt`:
```
sqladmin>=0.16.0,<0.17.0
wtforms>=3.1.0,<3.2.0
```

### 4. New Admin Module

Created `app/admin/` directory with:
- `__init__.py` - Main admin setup and configuration
- `auth.py` - Authentication backend (SUPER_ADMIN only)
- `views.py` - Model views for all entities
- `formatters.py` - Custom field formatters for UUIDs, JSON, timestamps, etc.

### 5. Main App Integration

Updated `app/main.py` to mount the admin panel at `/admin`.

## Accessing the Admin Panel

### URL
```
http://localhost:8000/admin
```

### Authentication

The admin panel uses simple username/password authentication from environment variables.

**Environment Variables:**
- `ADMIN_USERNAME` - Admin username (default: "admin")
- `ADMIN_PASSWORD` - Admin password (default: "changeme")

**Setup in .env file:**
```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
```

**To login:**
1. Visit `http://localhost:8000/admin`
2. Enter the username and password from your `.env` file
3. Click "Login"

**⚠️ Security Warning:**
- Change the default password in production!
- Use a strong, unique password
- Share credentials only with trusted administrators
- Consider using a password manager for secure storage

## Available Admin Views

The admin panel provides full CRUD access to:

1. **Users** - Manage all user accounts (SUPER_ADMIN, MANAGER, ADMIN, VISITOR)
2. **Vendors** - Manage product suppliers
3. **Products** - Manage products with pricing, images, and vendor associations
4. **Wishlists** - Manage wishlists with customization options
5. **Orders** - View and manage orders with payment status

### Features by Model

#### User Admin
- Search by email and full name
- Filter by role, active status, and creation date
- View manager relationships
- Edit roles (dropdown with validation)
- Password hash management (use with caution)

#### Vendor Admin
- Search by name and description
- Filter by active status
- Logo URL management
- Product associations displayed

#### Product Admin
- Search by name and description
- Filter by active status and price
- Price displayed with currency formatting
- JSON image array management
- Validation for JSON format

#### Wishlist Admin
- Search by title, slug, and description
- Filter by status and dates
- Customization: colors, logos, header images
- JSON delivery address management
- URL preview for public slugs
- Admin and manager assignment

#### Order Admin
- Search by Stripe session ID
- Filter by status, currency, and dates
- Price formatting
- Payment status tracking
- Related user and wishlist information

## Common Admin Operations

### Managing JSON Fields

**Product Images** - Must be a JSON array:
```json
["https://example.com/image1.jpg", "https://example.com/image2.jpg"]
```

**Wishlist Delivery Address** - Must be a JSON object:
```json
{
    "street": "123 Main St",
    "city": "New York",
    "state": "NY",
    "zip": "10001",
    "country": "USA"
}
```

### Enum Fields

All enum fields (User.role, Wishlist.status, Order.status) are displayed as dropdown menus with the following values:

**User Roles:**
- SUPER_ADMIN
- MANAGER
- ADMIN
- VISITOR

**Wishlist Status:**
- DRAFT
- PUBLISHED

**Order Status:**
- PENDING
- PAID
- FAILED
- REFUNDED

## Security Considerations

1. **Session Management**: Admin sessions use secure cookies with 24-hour expiration
2. **Authentication**: Simple username/password authentication from environment variables
3. **HTTPS**: In production (`is_production=true`), session cookies are marked as `secure` and only transmitted over HTTPS
4. **CSRF Protection**: Enabled by default in SQLAdmin
5. **Password Hash**: Visible in edit forms but not in list views. Handle with care.
6. **Admin Credentials**: Store in `.env` file, never commit to version control. Use strong passwords in production.

## Troubleshooting

### "Invalid credentials" Error

Make sure:
- The username matches `ADMIN_USERNAME` in your `.env` file
- The password matches `ADMIN_PASSWORD` in your `.env` file
- No extra spaces in the credentials
- The environment variables are loaded correctly (restart the app after changing .env)

### 500 Error When Viewing/Editing Models

Common causes:
1. **Enum validation error**: Ensure all enum fields have valid values from the defined enums
2. **JSON parsing error**: Check that JSON fields contain valid JSON
3. **Foreign key constraint**: Verify related records exist (e.g., admin_id, manager_id must reference valid users)

### Cannot Access Admin Panel

Ensure:
1. The admin panel is mounted in `main.py`
2. Session middleware is properly configured
3. Database engine is passed to `setup_admin()`
4. You're using the correct admin credentials from `.env`
5. The application has been restarted after changing environment variables

## Database Migration

The migration files have been updated to use VARCHAR(50) instead of PostgreSQL enums from the start.

**For new installations:**
```bash
alembic upgrade head
```

**For existing databases with enums:**
See `MIGRATION_ENUM_TO_STRING.md` for detailed migration instructions.

**Note**: If you're starting fresh (no existing data), simply drop the database and recreate it with the new migrations.

## Future Enhancements

Potential improvements for the admin panel:

1. **Audit Logging**: Track all admin actions (create, update, delete)
2. **Dashboard**: Summary statistics and graphs
3. **Bulk Operations**: Mass updates and deletes
4. **CSV Export**: Export filtered data to CSV
5. **Custom Actions**: Add custom actions for common tasks
6. **File Upload**: Direct file upload for logos and images
7. **Rich Text Editor**: For description fields
8. **Inline Editing**: Edit junction tables inline within parent models

## Support

For issues or questions about the admin panel:
1. Check this documentation
2. Review the SQLAdmin documentation: https://aminalaee.dev/sqladmin/
3. Check application logs for detailed error messages
4. Verify database migration was completed successfully
