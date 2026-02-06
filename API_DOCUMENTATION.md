# Zendora API Documentation

**Version:** 1.0.0  
**Base URL:** `http://localhost:8000` (development)  
**API Type:** RESTful JSON API

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [User Roles](#user-roles)
4. [API Endpoints](#api-endpoints)
   - [Authentication](#authentication-endpoints)
   - [Vendor Management](#vendor-management-super_admin-only)
   - [Product Management](#product-management-super_admin-only)
   - [Manager Wishlist Operations](#manager-wishlist-operations)
   - [Admin Wishlist Operations](#admin-wishlist-operations)
   - [Public Wishlist Access](#public-wishlist-access)
   - [Webhooks](#webhooks)
5. [Data Models](#data-models)
6. [Error Handling](#error-handling)
7. [Workflow Examples](#workflow-examples)

---

## Overview

Zendora is a wishlist-based gifting platform that enables:
- **Managers** to create wishlists and assign them to admins
- **Admins** to customize and publish their wishlists
- **Visitors** to view public wishlists and purchase products
- **Super Admins** to manage the product catalog

### Key Features

- Role-based access control (4 user roles)
- JWT authentication with multiple login methods
- Stripe payment integration
- Automated email notifications via SendGrid
- Public wishlist sharing with unique URLs

---

## Authentication

### Authentication Methods

The API supports three authentication methods:

1. **Email + Password** - Standard login
2. **Magic Link** - Passwordless email link
3. **Third-Party Redirect** - SSO-style authentication

### Authorization Header

For protected endpoints, include the JWT token in the Authorization header:

```
Authorization: Bearer <your_jwt_token>
```

### Token Structure

JWT tokens contain:
- `sub` - User ID (UUID)
- `email` - User email address
- `role` - User role (SUPER_ADMIN, MANAGER, ADMIN, VISITOR)
- `exp` - Token expiration timestamp

---

## User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| **SUPER_ADMIN** | System administrator | Manage vendors, products, all system data |
| **MANAGER** | Wishlist manager | Create wishlists, assign admins, view all their wishlists |
| **ADMIN** | Wishlist owner | Edit and publish their assigned wishlists |
| **VISITOR** | Public user | View public wishlists and make purchases |

### Role Relationships

- Each **ADMIN** belongs to exactly one **MANAGER**
- **VISITORS** are created automatically on first purchase
- **VISITORS** do not have passwords (passwordless accounts)

---

## API Endpoints

### Health Check

#### `GET /health`

Check API health status.

**Authentication:** None required

**Response:**
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "0.1.0"
}
```

---

## Authentication Endpoints

### 1. Email + Password Login

#### `POST /auth/login`

Authenticate with email and password.

**Authentication:** None required

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "ADMIN",
    "is_active": true,
    "manager_id": "uuid",
    "created_at": "2026-02-01T12:00:00Z"
  }
}
```

**Errors:**
- `401 Unauthorized` - Invalid credentials

---

### 2. Request Magic Link

#### `POST /auth/magic-link/request`

Request a magic link for passwordless login.

**Authentication:** None required

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response (200 OK):**
```json
{
  "message": "If the email exists, a magic link has been sent",
  "status": "success",
  "debug_token": "token_here"  // Only in development
}
```

---

### 3. Verify Magic Link

#### `GET /auth/magic-link/verify?token={token}`

Verify magic link token and receive JWT.

**Authentication:** None required

**Query Parameters:**
- `token` (required) - Magic link token from email

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { /* user object */ }
}
```

**Errors:**
- `401 Unauthorized` - Invalid or expired token

---

### 4. Third-Party Redirect Login

#### `POST /auth/redirect-login`

Authenticate using third-party token (SSO-style).

**Authentication:** None required

**Request Body:**
```json
{
  "token": "third_party_token_here"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": { /* user object */ }
}
```

**Notes:**
- Auto-creates user if not exists
- Token is verified with configured third-party endpoint

---

## Vendor Management (SUPER_ADMIN Only)

### 1. Create Vendor

#### `POST /admin/vendors`

Create a new vendor.

**Authentication:** Required (SUPER_ADMIN)

**Request Body:**
```json
{
  "name": "Premium Gifts Co.",
  "description": "High-quality gift items",
  "logo_url": "https://example.com/logo.png"
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "name": "Premium Gifts Co.",
  "description": "High-quality gift items",
  "logo_url": "https://example.com/logo.png",
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z"
}
```

---

### 2. List Vendors

#### `GET /admin/vendors?include_inactive=false`

List all vendors.

**Authentication:** Required (SUPER_ADMIN)

**Query Parameters:**
- `include_inactive` (optional, boolean) - Include inactive vendors (default: false)

**Response (200 OK):**
```json
[
  {
    "id": "uuid",
    "name": "Premium Gifts Co.",
    "description": "High-quality gift items",
    "logo_url": "https://example.com/logo.png",
    "is_active": true,
    "created_at": "2026-02-01T12:00:00Z"
  }
]
```

---

### 3. Get Vendor

#### `GET /admin/vendors/{vendor_id}`

Get vendor details.

**Authentication:** Required (SUPER_ADMIN)

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "Premium Gifts Co.",
  "description": "High-quality gift items",
  "logo_url": "https://example.com/logo.png",
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z"
}
```

---

### 4. Update Vendor

#### `PUT /admin/vendors/{vendor_id}`

Update vendor information.

**Authentication:** Required (SUPER_ADMIN)

**Request Body:**
```json
{
  "name": "Updated Vendor Name",
  "description": "Updated description",
  "logo_url": "https://example.com/new-logo.png",
  "is_active": true
}
```

**Note:** All fields are optional. Only provided fields will be updated.

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "Updated Vendor Name",
  "description": "Updated description",
  "logo_url": "https://example.com/new-logo.png",
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z"
}
```

---

## Product Management (SUPER_ADMIN Only)

### 1. Create Product

#### `POST /admin/products`

Create a new product.

**Authentication:** Required (SUPER_ADMIN)

**Request Body:**
```json
{
  "name": "Elegant Watch",
  "description": "Luxury timepiece with leather strap",
  "price": 299.99,
  "images": [
    "https://example.com/watch1.jpg",
    "https://example.com/watch2.jpg"
  ]
}
```

**Response (201 Created):**
```json
{
  "id": "uuid",
  "name": "Elegant Watch",
  "description": "Luxury timepiece with leather strap",
  "price": 299.99,
  "images": ["https://example.com/watch1.jpg", "https://example.com/watch2.jpg"],
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z"
}
```

---

### 2. List Products

#### `GET /admin/products?include_inactive=false`

List all products.

**Authentication:** Required (SUPER_ADMIN)

**Query Parameters:**
- `include_inactive` (optional, boolean) - Include inactive products (default: false)

**Response (200 OK):**
```json
[
  {
    "id": "uuid",
    "name": "Elegant Watch",
    "description": "Luxury timepiece with leather strap",
    "price": 299.99,
    "images": ["https://example.com/watch1.jpg"],
    "is_active": true,
    "created_at": "2026-02-01T12:00:00Z"
  }
]
```

---

### 3. Get Product

#### `GET /admin/products/{product_id}`

Get product details with associated vendors.

**Authentication:** Required (SUPER_ADMIN)

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "Elegant Watch",
  "description": "Luxury timepiece with leather strap",
  "price": 299.99,
  "images": ["https://example.com/watch1.jpg"],
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z",
  "vendor_ids": ["vendor_uuid_1", "vendor_uuid_2"]
}
```

---

### 4. Update Product

#### `PUT /admin/products/{product_id}`

Update product information.

**Authentication:** Required (SUPER_ADMIN)

**Request Body:**
```json
{
  "name": "Updated Product Name",
  "description": "Updated description",
  "price": 349.99,
  "images": ["https://example.com/new-image.jpg"],
  "is_active": true
}
```

**Note:** All fields are optional.

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "Updated Product Name",
  "description": "Updated description",
  "price": 349.99,
  "images": ["https://example.com/new-image.jpg"],
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z"
}
```

---

### 5. Associate Vendors with Product

#### `POST /admin/products/{product_id}/vendors`

Associate multiple vendors with a product (replaces existing associations).

**Authentication:** Required (SUPER_ADMIN)

**Request Body:**
```json
{
  "vendor_ids": ["vendor_uuid_1", "vendor_uuid_2"]
}
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  "name": "Elegant Watch",
  "description": "Luxury timepiece with leather strap",
  "price": 299.99,
  "images": ["https://example.com/watch1.jpg"],
  "is_active": true,
  "created_at": "2026-02-01T12:00:00Z",
  "vendor_ids": ["vendor_uuid_1", "vendor_uuid_2"]
}
```

---

## Manager Wishlist Operations

### 1. Create Wishlist

#### `POST /manager/wishlists`

Create a new wishlist and assign it to an admin.

**Authentication:** Required (MANAGER)

**Request Body:**
```json
{
  "admin_email": "admin@example.com",
  "admin_full_name": "John Doe",
  "title": "John's Wedding Registry",
  "description": "Gifts for our special day",
  "logo_url": "https://example.com/logo.png",
  "header_image_url": "https://example.com/header.jpg",
  "primary_color": "#FF5733",
  "secondary_color": "#C70039",
  "delivery_address": {
    "street": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "country": "USA",
    "additional_info": "Apt 4B"
  }
}
```

**Notes:**
- If admin email doesn't exist, creates new admin user with generated password
- Sends credentials email to admin
- All fields except `admin_email` and `admin_full_name` are optional

**Response (201 Created):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "abc123xyz",
  "status": "DRAFT",
  "title": "John's Wedding Registry",
  "description": "Gifts for our special day",
  "logo_url": "https://example.com/logo.png",
  "header_image_url": "https://example.com/header.jpg",
  "primary_color": "#FF5733",
  "secondary_color": "#C70039",
  "delivery_address": {
    "street": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "country": "USA"
  },
  "created_at": "2026-02-01T12:00:00Z",
  "published_at": null
}
```

---

### 2. List Manager's Wishlists

#### `GET /manager/wishlists`

List all wishlists managed by the current manager.

**Authentication:** Required (MANAGER)

**Response (200 OK):**
```json
[
  {
    "id": "uuid",
    "admin_id": "uuid",
    "manager_id": "uuid",
    "public_slug": "abc123xyz",
    "status": "DRAFT",
    "title": "John's Wedding Registry",
    "description": "Gifts for our special day",
    "logo_url": "https://example.com/logo.png",
    "header_image_url": "https://example.com/header.jpg",
    "primary_color": "#FF5733",
    "secondary_color": "#C70039",
    "delivery_address": { /* address object */ },
    "created_at": "2026-02-01T12:00:00Z",
    "published_at": null
  }
]
```

---

### 3. Get Wishlist Details

#### `GET /manager/wishlists/{wishlist_id}`

Get detailed information about a specific wishlist.

**Authentication:** Required (MANAGER)

**Response (200 OK):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "abc123xyz",
  "status": "PUBLISHED",
  "title": "John's Wedding Registry",
  "description": "Gifts for our special day",
  "logo_url": "https://example.com/logo.png",
  "header_image_url": "https://example.com/header.jpg",
  "primary_color": "#FF5733",
  "secondary_color": "#C70039",
  "delivery_address": { /* address object */ },
  "created_at": "2026-02-01T12:00:00Z",
  "published_at": "2026-02-05T10:30:00Z"
}
```

---

### 4. Update Wishlist

#### `PUT /manager/wishlists/{wishlist_id}`

Update wishlist information.

**Authentication:** Required (MANAGER)

**Request Body:**
```json
{
  "title": "Updated Title",
  "description": "Updated description",
  "logo_url": "https://example.com/new-logo.png",
  "header_image_url": "https://example.com/new-header.jpg",
  "primary_color": "#0000FF",
  "secondary_color": "#00FF00",
  "delivery_address": {
    "street": "456 Oak Ave",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "90001",
    "country": "USA"
  }
}
```

**Note:** All fields are optional.

**Response (200 OK):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "abc123xyz",
  "status": "DRAFT",
  "title": "Updated Title",
  "description": "Updated description",
  /* ... other fields ... */
}
```

---

## Admin Wishlist Operations

### 1. List My Wishlists

#### `GET /admin/wishlists`

List all wishlists owned by the current admin.

**Authentication:** Required (ADMIN)

**Response (200 OK):**
```json
[
  {
    "id": "uuid",
    "admin_id": "uuid",
    "manager_id": "uuid",
    "public_slug": "abc123xyz",
    "status": "DRAFT",
    "title": "My Wedding Registry",
    /* ... other wishlist fields ... */
  }
]
```

---

### 2. Create My Own Wishlist

#### `POST /admin/wishlists`

Admin creates their own wishlist.

**Authentication:** Required (ADMIN)

**Request Body:**
```json
{
  "title": "My Birthday Wishlist",
  "description": "Things I'd love for my birthday",
  "logo_url": "https://example.com/logo.png",
  "header_image_url": "https://example.com/header.jpg",
  "primary_color": "#FF5733",
  "secondary_color": "#C70039",
  "delivery_address": {
    "street": "123 Main St",
    "city": "San Francisco",
    "state": "CA",
    "zip_code": "94102",
    "country": "USA"
  }
}
```

**Note:** All fields are optional. Wishlist is created in DRAFT status.

**Response (201 Created):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "xyz789abc",
  "status": "DRAFT",
  "title": "My Birthday Wishlist",
  /* ... other fields ... */
}
```

---

### 3. Get My Wishlist

#### `GET /admin/wishlists/{wishlist_id}`

Get details of admin's own wishlist.

**Authentication:** Required (ADMIN)

**Response (200 OK):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "abc123xyz",
  "status": "DRAFT",
  /* ... wishlist fields ... */
}
```

---

### 4. Update My Wishlist

#### `PUT /admin/wishlists/{wishlist_id}`

Update admin's own wishlist.

**Authentication:** Required (ADMIN)

**Request Body:**
```json
{
  "title": "Updated Title",
  "description": "Updated description",
  /* ... other optional fields ... */
}
```

**Response (200 OK):**
```json
{
  "id": "uuid",
  /* ... updated wishlist fields ... */
}
```

---

### 5. Add Products to Wishlist

#### `POST /admin/wishlists/{wishlist_id}/products`

Add one or more products to the wishlist.

**Authentication:** Required (ADMIN)

**Request Body:**
```json
{
  "products": [
    {
      "product_id": "product_uuid_1",
      "quantity": 2
    },
    {
      "product_id": "product_uuid_2",
      "quantity": 1
    }
  ]
}
```

**Response (200 OK):**
```json
{
  "message": "Products added successfully",
  "count": 2
}
```

---

### 6. Remove Product from Wishlist

#### `DELETE /admin/wishlists/{wishlist_id}/products/{product_id}`

Remove a product from the wishlist.

**Authentication:** Required (ADMIN)

**Response (200 OK):**
```json
{
  "message": "Product removed successfully"
}
```

---

### 7. Publish Wishlist

#### `POST /admin/wishlists/{wishlist_id}/publish`

Publish a wishlist (makes it publicly accessible).

**Authentication:** Required (ADMIN)

**Important Rules:**
- An admin can only have **ONE** published wishlist at a time
- If another wishlist is already published, this request will fail
- Sends notification email to manager

**Response (200 OK):**
```json
{
  "id": "uuid",
  "admin_id": "uuid",
  "manager_id": "uuid",
  "public_slug": "abc123xyz",
  "status": "PUBLISHED",
  "title": "My Wedding Registry",
  "published_at": "2026-02-01T15:30:00Z",
  /* ... other fields ... */
}
```

**Errors:**
- `409 Conflict` - Admin already has a published wishlist

---

## Public Wishlist Access

### 1. View Public Wishlist

#### `GET /w/{public_slug}`

View a published wishlist (public, no authentication required).

**Authentication:** None required

**Response (200 OK):**
```json
{
  "id": "uuid",
  "title": "John's Wedding Registry",
  "description": "Gifts for our special day",
  "customization": {
    "logo_url": "https://example.com/logo.png",
    "header_image_url": "https://example.com/header.jpg",
    "primary_color": "#FF5733",
    "secondary_color": "#C70039"
  },
  "products": [
    {
      "id": "uuid",
      "name": "Elegant Watch",
      "description": "Luxury timepiece",
      "price": 299.99,
      "images": ["https://example.com/watch1.jpg", "https://example.com/watch2.jpg"],
      "quantity": 1
    },
    {
      "id": "uuid",
      "name": "Coffee Maker",
      "description": "Premium espresso machine",
      "price": 599.99,
      "images": ["https://example.com/coffee1.jpg"],
      "quantity": 1
    }
  ]
}
```

**Errors:**
- `404 Not Found` - Wishlist not found or not published

---

### 2. Initiate Checkout

#### `POST /w/{public_slug}/checkout`

Initiate checkout for selected products from a public wishlist.

**Authentication:** None required

**Request Body:**
```json
{
  "visitor_name": "Jane Smith",
  "visitor_email": "jane.smith@example.com",
  "product_ids": ["product_uuid_1", "product_uuid_2"]
}
```

**Process:**
1. Creates or retrieves visitor user account
2. Creates pending order
3. Generates Stripe Checkout session
4. Returns checkout URL

**Response (200 OK):**
```json
{
  "order_id": "order_uuid",
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "total_amount": 899.98
}
```

**Notes:**
- Visitor accounts are created automatically
- Visitors do not have passwords
- All products must be in the wishlist
- Redirect user to `checkout_url` to complete payment

**Errors:**
- `404 Not Found` - Wishlist not found or not published
- `400 Bad Request` - Product not in wishlist

---

## Webhooks

### Stripe Webhook

#### `POST /webhooks/stripe`

Receives payment notifications from Stripe.

**Authentication:** Stripe signature verification

**Headers:**
```
stripe-signature: t=1234567890,v1=signature_hash
```

**Handled Events:**
- `checkout.session.completed` - Payment successful
- `checkout.session.expired` - Payment session expired

**Process (checkout.session.completed):**
1. Verifies webhook signature
2. Updates order status to PAID
3. Records payment timestamp
4. Sends confirmation emails to admin and manager

**Response (200 OK):**
```json
{
  "status": "success"
}
```

**Important:**
- Configure webhook in Stripe Dashboard
- Point to: `https://your-domain.com/webhooks/stripe`
- Select events: `checkout.session.completed`, `checkout.session.expired`

---

## Data Models

### User

```typescript
{
  id: UUID
  email: string
  full_name?: string
  role: "SUPER_ADMIN" | "MANAGER" | "ADMIN" | "VISITOR"
  is_active: boolean
  manager_id?: UUID  // Only for ADMIN users
  created_at: timestamp
}
```

### Wishlist

```typescript
{
  id: UUID
  admin_id: UUID
  manager_id: UUID
  public_slug: string  // Unique identifier for public URL
  status: "DRAFT" | "PUBLISHED"
  title?: string
  description?: string
  logo_url?: string
  header_image_url?: string
  primary_color?: string  // Hex color, e.g., "#FF5733"
  secondary_color?: string  // Hex color
  delivery_address?: {
    street: string
    city: string
    state: string
    zip_code: string
    country: string
    additional_info?: string
  }
  created_at: timestamp
  published_at?: timestamp
}
```

### Product

```typescript
{
  id: UUID
  name: string
  description?: string
  price: number  // Decimal, e.g., 299.99
  images: string[]  // Array of image URLs
  is_active: boolean
  created_at: timestamp
}
```

### Vendor

```typescript
{
  id: UUID
  name: string
  description?: string
  logo_url?: string
  is_active: boolean
  created_at: timestamp
}
```

### Order

```typescript
{
  id: UUID
  visitor_id: UUID
  wishlist_id: UUID
  admin_id: UUID
  stripe_session_id: string
  status: "PENDING" | "PAID" | "FAILED" | "REFUNDED"
  total_amount: number
  currency: string  // Default: "USD"
  created_at: timestamp
  paid_at?: timestamp
  products: [
    {
      product_id: UUID
      product_name: string  // Snapshot at time of purchase
      product_price: number  // Snapshot at time of purchase
      quantity: number
    }
  ]
}
```

---

## Error Handling

### Error Response Format

All errors return JSON in this format:

```json
{
  "error": "ErrorType",
  "message": "Human-readable error message",
  "details": {}  // Optional additional context
}
```

### HTTP Status Codes

| Code | Description | When Used |
|------|-------------|-----------|
| `200` | OK | Successful GET, PUT, DELETE requests |
| `201` | Created | Successful POST requests |
| `400` | Bad Request | Invalid request data |
| `401` | Unauthorized | Missing or invalid authentication |
| `403` | Forbidden | Insufficient permissions |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Business rule violation (e.g., duplicate published wishlist) |
| `422` | Unprocessable Entity | Validation errors |
| `500` | Internal Server Error | Unexpected server error |

### Common Error Types

**NotFoundException** (404)
```json
{
  "error": "NotFoundException",
  "message": "Wishlist not found",
  "details": {}
}
```

**UnauthorizedError** (401)
```json
{
  "error": "UnauthorizedError",
  "message": "Invalid authentication token",
  "details": {}
}
```

**PermissionDenied** (403)
```json
{
  "error": "PermissionDenied",
  "message": "You can only access your own wishlists",
  "details": {}
}
```

**ConflictError** (409)
```json
{
  "error": "ConflictError",
  "message": "Admin already has a published wishlist",
  "details": {}
}
```

**ValidationError** (422)
```json
{
  "error": "ValidationError",
  "message": "Invalid email format",
  "details": {
    "field": "email",
    "constraint": "email_format"
  }
}
```

---

## Workflow Examples

### Complete Manager-Admin-Visitor Flow

#### 1. Manager Creates Wishlist

```http
POST /manager/wishlists
Authorization: Bearer {manager_jwt_token}
Content-Type: application/json

{
  "admin_email": "newadmin@example.com",
  "admin_full_name": "John Doe",
  "title": "John's Wedding Registry"
}
```

**Result:**
- New admin user created
- Password generated and emailed to admin
- Wishlist created in DRAFT status

---

#### 2. Admin Logs In

```http
POST /auth/login
Content-Type: application/json

{
  "email": "newadmin@example.com",
  "password": "password_from_email"
}
```

**Result:**
- Receives JWT token
- Can now access admin endpoints

---

#### 3. Admin Customizes Wishlist

```http
PUT /admin/wishlists/{wishlist_id}
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json

{
  "title": "Our Dream Wedding Registry",
  "description": "Help us celebrate our special day!",
  "primary_color": "#FF69B4",
  "secondary_color": "#FFB6C1"
}
```

---

#### 4. Admin Adds Products

```http
POST /admin/wishlists/{wishlist_id}/products
Authorization: Bearer {admin_jwt_token}
Content-Type: application/json

{
  "products": [
    {"product_id": "uuid1", "quantity": 1},
    {"product_id": "uuid2", "quantity": 2}
  ]
}
```

---

#### 5. Admin Publishes Wishlist

```http
POST /admin/wishlists/{wishlist_id}/publish
Authorization: Bearer {admin_jwt_token}
```

**Result:**
- Wishlist status changed to PUBLISHED
- Manager receives email notification
- Wishlist now accessible at `/w/{public_slug}`

---

#### 6. Visitor Views Public Wishlist

```http
GET /w/abc123xyz
```

**Result:**
- Receives wishlist with products
- No authentication required

---

#### 7. Visitor Initiates Purchase

```http
POST /w/abc123xyz/checkout
Content-Type: application/json

{
  "visitor_name": "Jane Smith",
  "visitor_email": "jane@example.com",
  "product_ids": ["uuid1", "uuid2"]
}
```

**Result:**
- Visitor account created (if new)
- Order created with PENDING status
- Receives Stripe checkout URL

---

#### 8. Visitor Completes Payment

- Redirects to Stripe Checkout
- Enters payment information
- Stripe processes payment

---

#### 9. Webhook Confirms Payment

```http
POST /webhooks/stripe
stripe-signature: t=...,v1=...

{
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "metadata": {"order_id": "uuid"}
    }
  }
}
```

**Result:**
- Order status updated to PAID
- Admin receives email: "You have a new purchase!"
- Manager receives email: "Purchase notification"

---

## Integration Notes for Frontend Developers

### Authentication Flow

1. **Store JWT Token**: After successful login, store the `access_token` in memory or secure storage (not localStorage for security)
2. **Include in Headers**: Add `Authorization: Bearer {token}` to all protected API requests
3. **Handle 401 Errors**: Token expired or invalid - redirect to login
4. **Handle 403 Errors**: Insufficient permissions - show appropriate message

### Public Wishlist Display

1. **Extract Slug**: From URL path `/w/{public_slug}`
2. **Fetch Wishlist**: `GET /w/{public_slug}` (no auth required)
3. **Display Products**: Show product images, names, prices
4. **Checkout Button**: Collect visitor name/email, then POST to `/w/{public_slug}/checkout`
5. **Redirect to Stripe**: Use `checkout_url` from response

### Stripe Integration

1. **Receive Checkout URL**: From `/w/{public_slug}/checkout` endpoint
2. **Redirect User**: `window.location.href = checkout_url`
3. **Success Page**: Stripe redirects to `{FRONTEND_URL}/order/{order_id}/success`
4. **Cancel Page**: Stripe redirects to `{FRONTEND_URL}/order/{order_id}/cancel`

### Color Customization

Wishlists include `primary_color` and `secondary_color` as hex values:
- Use for buttons, headers, accents
- Ensure sufficient contrast for accessibility
- Provide fallback colors if not set

### Image Display

- Products and wishlists may have multiple images
- First image is primary/thumbnail
- Images are URLs (hosted externally)
- Handle missing images gracefully

---

## Rate Limiting

Currently not implemented. Consider implementing rate limiting on:
- Authentication endpoints (prevent brute force)
- Checkout endpoint (prevent spam)

---

## CORS Configuration

Development: Allows `http://localhost:3000` and `http://localhost:8000`

Production: Configure allowed origins in environment variables.

---

## Environment Variables

Frontend needs to know:

- `API_BASE_URL` - Base URL for API requests
- `STRIPE_PUBLISHABLE_KEY` - For Stripe Elements (if implementing custom checkout UI)

Backend requires (inform devops):

- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - Secret key for JWT tokens
- `STRIPE_SECRET_KEY` - Stripe API secret key
- `STRIPE_WEBHOOK_SECRET` - Stripe webhook signing secret
- `SENDGRID_API_KEY` - SendGrid API key
- `SENDGRID_FROM_EMAIL` - Email sender address
- `FRONTEND_URL` - Frontend application URL (for redirects)

---

## Support & Questions

For technical questions or API issues, contact the backend team.

**API Documentation Version:** 1.0.0  
**Last Updated:** February 1, 2026
