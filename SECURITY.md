# Security

## Authentication and account data

- Registration and login are the only public account endpoints. Registration validates the email, display name and password before creating data.
- Passwords are hashed with Argon2id. Email and password hashes are stored on a private `Account` node, linked to a public `User` node; public profile and search responses expose only `id`, `name` and `source`.
- Access tokens use HS256 with required `sub`, `iat` and `exp` claims and a 30-minute lifetime. The signing secret and Neo4j password have no code defaults; configuration rejects missing, short or documented placeholder values.
- Login, registration and user search use Redis fixed-window rate limits. Login and registration fail closed when Redis cannot enforce the limit. Search is read-only and fails open when Redis is unavailable.
- A request's client IP is taken from the direct socket peer. The application does not trust `X-Forwarded-For` itself. If deployed behind a proxy, configure Uvicorn's trusted proxy address list deliberately before allowing forwarded headers.
- A valid token is rejected when its subject no longer maps to a `User` node.

## Known limitations

Email verification, password reset, multi-factor authentication, token revocation and refresh tokens are not implemented. A stolen access token remains usable until it expires. The authenticated graph is visible to every authenticated user, as described in the project plan.

## Reporting

Do not include access tokens, passwords, signing secrets, database credentials or private account data in an issue. Report a suspected vulnerability privately to the repository owner and include a concise reproduction that uses synthetic data.
