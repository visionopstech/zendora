# Admin Panel - Quick Reference

## 🚀 Quick Start

### 1. Configure Admin Credentials

Edit your `.env` file:
```bash
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here
```

### 2. Start Fresh

```bash
# Remove old volumes and start fresh
docker-compose down -v
docker-compose up -d

# Wait for migrations to complete
docker-compose logs -f app
```

### 3. Access Admin Panel

- **URL**: http://localhost:8000/admin
- **Username**: (from your .env)
- **Password**: (from your .env)

## 📋 What Changed

### Database Schema
- ✅ All enum columns converted to VARCHAR(50)
- ✅ No more PostgreSQL native enums
- ✅ Migration file updated (`alembic/versions/001_initial.py`)

### Authentication
- ✅ Simple username/password from environment variables
- ✅ No JWT dependency for admin access
- ✅ Secure session-based authentication

### Admin Features
- ✅ Manage Users (all roles)
- ✅ Manage Vendors
- ✅ Manage Products (with images)
- ✅ Manage Wishlists (with customization)
- ✅ View Orders (with payment status)
- ✅ Search, filter, export data

## 📚 Documentation

| File | Purpose |
|------|---------|
| `QUICK_START.md` | Complete setup guide |
| `ADMIN_SETUP.md` | Admin panel usage |
| `CHANGES_SUMMARY.md` | All changes made |
| `IMPLEMENTATION_SUMMARY.md` | Technical details |
| `MIGRATION_ENUM_TO_STRING.md` | For existing databases |

## ✅ Verification Checklist

After starting:
- [ ] App starts: `docker-compose ps` shows all services running
- [ ] Migrations ran: Check logs for "Running upgrade"
- [ ] Admin accessible: Visit http://localhost:8000/admin
- [ ] Login works: Enter credentials from .env
- [ ] Models visible: See User, Vendor, Product, Wishlist, Order
- [ ] CRUD works: Try creating a test vendor
- [ ] API works: Visit http://localhost:8000/docs

## 🔧 Troubleshooting

**Can't login?**
- Check credentials match .env exactly
- Restart app: `docker-compose restart app`
- Clear browser cookies

**Migrations failed?**
- Remove volumes: `docker-compose down -v`
- Start fresh: `docker-compose up -d`

**Admin not loading?**
- Check logs: `docker-compose logs app`
- Verify DATABASE_URL in .env

## 🔒 Security

**⚠️ IMPORTANT**
- Change default password in production!
- Never commit .env to version control
- Use HTTPS in production
- Keep admin credentials secret

## 📞 Quick Commands

```bash
# View logs
docker-compose logs -f app

# Restart app
docker-compose restart app

# Fresh start
docker-compose down -v && docker-compose up -d

# Run migrations manually
docker-compose exec app alembic upgrade head

# Check migration status
docker-compose exec app alembic current
```

## 🎯 Next Steps

1. Login to admin panel
2. Create test vendors and products
3. Create test users with different roles
4. Test creating wishlists
5. Verify API still works (`/docs`)
6. Read full documentation for advanced features

---

**All documentation files are in the root directory.**  
**For detailed information, see `QUICK_START.md`**
