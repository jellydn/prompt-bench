# Deploying PromptBench to Dokku

|        |                                  |
| ------ | -------------------------------- |
| Host   | `dokku@docklight.itman.fyi`      |
| App    | `prompt-bench`                   |
| Domain | `https://prompt-bench.itman.fyi` |

PromptBench ships as a **single container**: `backend/Dockerfile` is a multi-stage build that compiles the frontend and copies it into `/app/static`, then the FastAPI app serves both the API (`/api/*`) and the UI (`/`) from one origin. The container `EXPOSE`s `8000`.

> **⚠️ Required before the first push.** The Dockerfile lives at `backend/Dockerfile`, not the repo root. Dokku's auto-detection only selects the dockerfile builder when a `Dockerfile` exists at the repo root; otherwise it falls back to Herokuish buildpacks and the build fails with `Unable to select a buildpack`. Two commands fix this — force the dockerfile builder, then point it at the non-root path:
>
> ```sh
> dokku builder:set prompt-bench selected dockerfile
> dokku builder-dockerfile:set prompt-bench dockerfile-path backend/Dockerfile
> ```

## How Dokku builds it

Dokku uses the repo root as the Docker build context (so `COPY frontend/...` and `COPY backend/...` in the Dockerfile resolve correctly). The production Dockerfile lives at `backend/Dockerfile`, so tell Dokku to use the dockerfile builder and where to find it (run this **before** the first `git push`):

```sh
dokku builder:set prompt-bench selected dockerfile
dokku builder-dockerfile:set prompt-bench dockerfile-path backend/Dockerfile
```

`builder:set ... selected dockerfile` overrides auto-detection (which would pick Herokuish, since there's no root `Dockerfile`). `builder-dockerfile:set ... dockerfile-path` points the builder at the non-root Dockerfile. This mirrors the old `fly.toml` setup (`[build] dockerfile = "backend/Dockerfile"`) — no new Dockerfile, no duplication.

## One-time server setup

Run on the Dokku server (`ssh dokku@docklight.itman.fyi`):

```sh
# 1. Create the app
dokku apps:create prompt-bench

# 2. Force the dockerfile builder + point it at the non-root Dockerfile
#    ⚠️ REQUIRED before the first push. Without this, Dokku auto-detects
#    Herokuish (no root Dockerfile) and fails: "Unable to select a buildpack".
dokku builder:set prompt-bench selected dockerfile
dokku builder-dockerfile:set prompt-bench dockerfile-path backend/Dockerfile

# 3. Add the domain
dokku domains:add prompt-bench prompt-bench.itman.fyi

# 4. Persistent storage for SQLite (survives redeploys)
dokku storage:ensure-directory --ignore-paths '' promptbench-data 2>/dev/null \
  || mkdir -p /var/lib/dokku/data/storage/promptbench-data
dokku storage:mount prompt-bench /var/lib/dokku/data/storage/promptbench-data:/app/data
dokku config:set prompt-bench DATABASE_URL=sqlite:////app/data/promptbench.db

# 5. Hide local-only providers (Ollama/vLLM) in production
dokku config:set prompt-bench ENABLE_LOCAL_PROVIDERS=false

# 6. Provider API keys (optional — BYOK works without any of these)
dokku config:set prompt-bench OPENROUTER_API_KEY=sk-or-v1-...
# dokku config:set prompt-bench OPENAI_API_KEY=sk-proj-...
# dokku config:set prompt-bench ANTHROPIC_API_KEY=sk-ant-...
# dokku config:set prompt-bench GEMINI_API_KEY=...

# 7. SSL via Let's Encrypt (requires the letsencrypt plugin)
dokku letsencrypt:set prompt-bench email you@example.com
dokku letsencrypt:enable prompt-bench
```

### Optional: Redis (cache) and Postgres (DB)

The app runs fine without either — it falls back to an in-memory cache and SQLite. To use managed services:

```sh
# Redis for caching (response + embedding cache)
dokku redis:create promptbench-redis
dokku redis:link promptbench-redis prompt-bench   # sets REDIS_URL automatically

# Postgres instead of SQLite
dokku postgres:create promptbench-pg
dokku postgres:link promptbench-pg prompt-bench   # sets DATABASE_URL automatically
# If you previously set the SQLite DATABASE_URL, clear it:
# dokku config:unset prompt-bench DATABASE_URL
```

## Deploy

### From your machine

```sh
git remote add dokku dokku@docklight.itman.fyi:prompt-bench
git push dokku main
```

### Via GitHub Actions (CI)

`.github/workflows/deploy.yml` auto-deploys every push to `main` by `git push`-ing to Dokku. It needs one repo secret:

| Secret          | Value                                                                |
| --------------- | -------------------------------------------------------------------- |
| `DOKKU_SSH_KEY` | Private SSH key whose public counterpart is registered on the server |

Register the CI key on the server once:

```sh
# on the Dokku server
dokku ssh-keys:add github-deploy < ci_deploy_key.pub
```

## Verifying the deployment

```sh
curl https://prompt-bench.itman.fyi/api/health
# {"status":"ok","name":"PromptBench"}

# open https://prompt-bench.itman.fyi  → UI loads from the same origin
```

## Notes / gotchas

- **Port:** the container `EXPOSE`s `8000` and binds `0.0.0.0`; Dokku's nginx routes `80/443 → 8000` automatically. If routing is off, run `dokku proxy:ports-add prompt-bench http:80:8000 https:443:8000`.
- **DB persistence:** without the storage mount in step 4, SQLite lives in the ephemeral container FS and is wiped on every redeploy.
- **SPA routing:** the backend serves `/app/static` via Starlette `StaticFiles(html=True)`. Deep-linking/refresh on a client-side route may 404 (pre-existing behavior, unchanged from the Fly.io deployment).
- **API keys:** BYOK lets users benchmark without any server-side keys. Server keys are only needed if you want the provider cards to show "Configured" by default.
