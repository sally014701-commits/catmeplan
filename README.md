# FocusPlan

FocusPlan is organized as a small monorepo with a Next.js frontend and a FastAPI backend.

```text
frontend/   Next.js 15, React, TypeScript, Tailwind CSS
backend/    FastAPI, Python services, SQLite
run.sh      Starts both applications
```

## Structure

```text
frontend/
├── app/                    Next.js pages and layouts
├── components/             Reusable UI components
├── public/                 Static assets
├── globals.css             Global Tailwind CSS
├── next.config.ts
├── package.json
├── tailwind.config.ts
└── tsconfig.json

backend/
├── app/
│   ├── main.py             FastAPI entry point and CORS
│   ├── database.py         SQLite connection and initialization
│   ├── routers/tasks.py    Task API routes
│   ├── schemas/task.py     Pydantic API schemas
│   └── services/
│       ├── normalize.py
│       └── task_service.py
├── tests/
├── focusplan.db
├── schema.sql
└── requirements.txt
```

## Run

Install the dependencies once:

```bash
npm --prefix frontend install --cache .npm
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Then start both applications:

```bash
./run.sh
```

The frontend uses `$PORT` (default `8000`) and proxies `/api/*` to the backend on
`$BACKEND_PORT` (default `8001`). The SQLite database is stored at
`backend/focusplan.db`.
