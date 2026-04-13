# Error Reference

## Authentication Errors

### 401 Unauthorized
The request is missing a valid Authorization header.

**Cause:** The access token is absent, expired, or malformed.  
**Fix:** Re-authenticate via `POST /api/login` to obtain a fresh token.

### 403 Forbidden
The authenticated user does not have permission to access this resource.

**Cause:** The endpoint requires admin-level access. Regular user tokens are rejected.  
**Fix:** Contact your administrator to request elevated permissions.

### 422 Token Expired
The access token was valid but has exceeded its `TOKEN_LIFETIME_SECONDS` lifespan.

**Fix:** Call `POST /api/refresh` with your refresh token to get a new access token.

## Database Errors

### 500 Internal Server Error (Database Connection)
The application could not connect to the database.

**Cause:** `DATABASE_URL` is not set, or the database server is unreachable.  
**Fix:** Verify the `DATABASE_URL` environment variable and that the database server is running.

### 409 Conflict
A unique constraint violation occurred (e.g., duplicate email on registration).

**Cause:** A record with the same unique key already exists.  
**Fix:** Use a different value or look up the existing record first.

## General Errors

### 400 Bad Request
The request body is missing required fields or contains invalid data.

**Fix:** Check the API Reference for required fields and valid data formats.

### 404 Not Found
The requested resource does not exist.

**Fix:** Verify the ID or URL path is correct.
