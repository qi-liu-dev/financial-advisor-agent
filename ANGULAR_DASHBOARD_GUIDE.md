# Angular Dashboard Implementation Guide

This repository contains a complete Angular operations dashboard for the typed FastAPI backend. It is designed to demonstrate the full lifecycle of an investment-management AI agent:

```text
Choose benchmark or synthetic workspace
        ↓
Run a schema-validated agent
        ↓
Inspect trace and structured output
        ↓
Evaluate quality, safety, latency and cost
        ↓
Run asynchronous prompt optimisation
        ↓
Review candidates and Pareto trade-offs
        ↓
Explicitly activate an approved selected prompt
```

## Technology choices

- Angular 21 standalone components
- Strict TypeScript and strict Angular templates
- Signals for local view state and computed metrics
- Reactive Forms for all user input
- RxJS for API composition and asynchronous job polling
- Relative `/api/v1` URLs with an Angular development proxy
- Typed API models matching the backend Pydantic/OpenAPI contract
- Native SVG for the Pareto scatter chart
- SCSS design system with responsive light and dark themes
- Vitest through Angular's unit-test builder
- No runtime UI framework or charting dependency

## Complete page set

### 1. Overview

- Total run count and evaluation coverage
- Sampled average quality and safety
- Average latency and tracked estimated cost
- API, database, LLM, migration and encryption health
- Per-agent run/evaluation metrics
- Current active prompt for all three agents
- Recent trace list
- Current and recent optimisation jobs

### 2. Benchmark Tasks

- Full-text search
- Agent, difficulty and tag filters
- Task payload inspection
- `must_mention`, `must_not_mention` and citation expectations
- One-click handoff to the Agent Playground

### 3. Agent Playground

- Select Client Summary, Meeting Notes or Investment Review
- Run a benchmark task or submit custom JSON
- Import a complete synthetic client workspace
- Select an explicit prompt version or use the current active prompt
- Configure advisor style, detail, risk focus and language
- Render the typed structured output by section
- Display latency, tokens and provider/client request IDs
- Deep-link the completed run into Run Evaluation

### 4. Run Evaluation

- Paginated run history
- Agent, advisor and evaluated-state filters
- Full trace and input snapshot
- Typed output viewer
- Seven score dimensions
- Benchmark expectation score
- Rule/benchmark/LLM-judge provenance
- Latency and estimated cost
- Re-evaluation through the shared backend EvaluationService
- Authorized run deletion

### 5. Prompt Optimizer

- Submit a `202 Accepted` asynchronous optimisation job
- Configure candidates, benchmark limit and repetitions
- Poll queued/running/completed/failed progress
- Review reflection on weak benchmark cases
- Compare repeated-run mean and standard deviation
- Inspect selection policy and reasons
- Plot quality against latency in an SVG Pareto chart
- Compare baseline and candidate prompt text
- Inspect candidate run evidence
- Browse job, result and prompt-version history
- Explicitly activate only an eligible `selected` prompt

### 6. Advisor Preferences

- Load, update and delete persistent advisor memory
- Configure summary style, detail, risk focus and language
- Store an optional development API key only in `sessionStorage`
- Link to Azure Easy Auth login/logout endpoints
- Browse synthetic clients, portfolios, meetings and proposals
- Send a chosen client workspace directly to the Playground

## Frontend structure

```text
frontend/src/app/
├── core/
│   ├── api/             Typed models, helpers and the only HTTP service
│   ├── auth/            Browser session/advisor context
│   ├── interceptors/    Request IDs, optional API key and safe API errors
│   └── services/        Toast and theme state
├── features/
│   ├── dashboard/
│   ├── tasks/
│   ├── agent-runner/
│   ├── runs/
│   ├── optimiser/
│   └── preferences/
├── layout/              Responsive navigation shell
└── shared/components/   Output, metrics, score, JSON, status, paging and chart UI
```

## Run locally

Start FastAPI from the repository root:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --env-file .env
```

Start Angular in another terminal:

```bash
cd frontend
npm ci
npm start
```

Open:

```text
http://localhost:4200
```

`proxy.conf.json` forwards `/api/*` to `http://127.0.0.1:8000`, while production continues to use relative `/api/v1` routes.

## Validate

```bash
cd frontend
npm run verify
```

This runs:

1. all frontend unit tests;
2. an optimized production build;
3. a Prettier formatting check.

Backend regression checks remain:

```bash
python -m pytest -q
python -m compileall -q backend tests scripts
```

## Authentication behavior

- `AUTH_MODE=disabled`: no browser credential is required.
- `AUTH_MODE=api_key`: enter the key on Advisor Preferences. It remains in `sessionStorage` for the current tab and is sent as `X-API-Key`.
- `AUTH_MODE=azure_easy_auth`: use `/.auth/login/aad`; the trusted Azure layer injects the authenticated principal for the backend.

Every `/api/` request receives a browser-generated `X-Request-ID`. Backend/provider correlation IDs are also rendered on completed runs.

## Azure Static Web Apps

The application includes `frontend/public/staticwebapp.config.json` with:

- SPA route fallback;
- API exclusions;
- security headers;
- Microsoft Entra login redirection for unauthorized responses.

Suggested build settings:

```text
App location: /frontend
Build command: npm ci && npm run build
Output location: dist/frontend/browser
```

The frontend bundle uses relative URLs, so it can be linked to the Container Apps backend without embedding an environment-specific API hostname.

## API contract maintenance

The hand-written types in `frontend/src/app/core/api/api.models.ts` mirror the named schemas in `docs/openapi.json`. When backend response models change:

```bash
python scripts/export_openapi.py
cd frontend
npm run build
npm run test:ci
```

The `ApiService` isolates endpoints from feature code, making it straightforward to replace the hand-written layer with an OpenAPI-generated Angular client later.

## Safety properties represented in the UI

- Candidate prompts never appear as active merely because they are the newest row.
- Only `selected` prompts are offered for activation.
- Activation requires a separate confirmation and backend authorization.
- Long optimisation work is polled rather than held open in one browser request.
- Run lists show summaries; sensitive full inputs are fetched only on explicit detail selection.
- Synthetic data is visibly labelled and the UI does not present outputs as investment advice.
