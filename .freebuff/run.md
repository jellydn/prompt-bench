# PromptBench — Preview Run Doc

## Reproduce artifacts

### Frontend
```bash
cd frontend && npm install
```

### Backend
```bash
cd backend && uv sync
```

## Run the servers

### Frontend (Vite dev server)
```bash
# Vite auto-picks the next free port if 5173 is occupied.
cd frontend && nohup ./node_modules/.bin/vite --host 0.0.0.0 --port 5173 \
  > .freebuff/preview-thms3eix37uhwp.log 2>&1 &
```

If port 5173 is taken, Vite will auto-select 5174 (or higher).
Check the log for the actual port: `grep "Local:" .freebuff/preview-thms3eix37uhwp.log`

### Backend (Uvicorn on port 8000)
```bash
# screen keeps it alive after the shell exits:
cd backend && screen -dmS pb-backend \
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Stop: screen -S pb-backend -X quit
```

The frontend Vite dev server proxies `/api` to `http://localhost:8000`.

### Seed test data
```bash
cd backend && uv run python -c "
from app.database import SessionLocal, init_db
init_db()
db = SessionLocal()
# ... (see conversation for full seed script)
db.commit()
db.close()
"
```
