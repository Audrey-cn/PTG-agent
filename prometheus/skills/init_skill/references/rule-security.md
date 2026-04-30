# Security Rules

## General

- Never log sensitive information (API keys, passwords, PII)
- Validate all external input before processing
- Use least privilege principle when accessing resources
- Sanitize output to prevent injection attacks

## Secrets

- Never hardcode secrets in source code
- Use environment variables or secret managers
- Never commit .env files or similar to git
- Rotate compromised secrets immediately

## Input Validation

- Validate all user input
- Use schema validation libraries (zod, pydantic, etc.)
- Sanitize data before storage or display
- Reject unexpected or malformed input

## Authentication & Authorization

- Always authenticate users before allowing access
- Implement proper authorization checks
- Use secure session management
- Never trust client-side validation alone
