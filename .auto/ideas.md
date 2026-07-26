# Ideas Backlog

## Deferred (Product-level features — out of scope for current session)
- Full auth/user isolation — would require middleware, user models, session management
- TLS termination — nginx/Caddy/traefik for production deployment
- Result export (CSV/JSON) — paginated API endpoint
- Prompt templates/save-reuse
- Side-by-side comparison view
- Scheduling/automated runs

## Technical Improvements
- Add actual token counting with tiktoken instead of character count for `response_chars`
- Fetch OpenRouter free model list from API at startup instead of hardcoding in `model_lists.py`
- Switch from `psycopg2-binary` to `psycopg` (async PostgreSQL driver) for better performance
- Add SQL-level aggregation in insights endpoint (AVG, SUM) instead of loading rows into Python
- Add connection pooling config for PostgreSQL in database.py
- Add rate limiting per-endpoint instead of blanket 60/min
- Upgrade frontend to React 19 (requires compat testing)
- Add pre-commit checks to CI pipeline
- Write unit tests for provider error paths
