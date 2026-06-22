# Financial Advisor Agent Dashboard

A complete Angular dashboard for the typed FastAPI backend in the parent repository. It is an operations and evaluation console rather than a chat UI: users can run structured financial-advisory agents, inspect traces, evaluate output quality, optimise prompts and explicitly promote selected prompt versions.

## Pages

- **Overview** — aggregate run count, sampled quality/safety/cost, latency, active prompts, API readiness and recent runs.
- **Benchmark Tasks** — search and filter the synthetic benchmark library, inspect payloads and expectations, then open a task in the playground.
- **Agent Playground** — run benchmark tasks, custom JSON or imported synthetic client workspaces with a selected prompt and advisor preferences.
- **Run Evaluation** — paginate/filter traces, inspect stored input and typed output, run the shared evaluator, review seven score dimensions and provenance.
- **Prompt Optimizer** — launch asynchronous jobs, poll progress, compare repeated-run metrics, inspect reflection/candidates, view a Pareto plot and explicitly activate selected prompts.
- **Advisor Preferences** — persist advisor memory, configure optional development authentication and browse synthetic client/portfolio/meeting/proposal workspaces.

## Requirements

- Node.js `^20.19.0`, `^22.12.0` or `>=24.0.0`
- npm 8+
- The FastAPI backend running on `http://127.0.0.1:8000`

This project uses Angular 21 LTS standalone components, strict TypeScript, signals, reactive forms and the built-in application builder.

## Local development

From the repository root, start the backend:

```bash
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --env-file .env
```

In another terminal:

```bash
cd frontend
npm ci
npm start
```

Open `http://localhost:4200`. `proxy.conf.json` forwards `/api/*` to FastAPI, so local browser requests remain same-origin from Angular's perspective.

## Build and test

```bash
npm run build
npm run test:ci
```

The production output is written to `dist/frontend/browser`.

## Authentication

- With backend `AUTH_MODE=disabled`, no browser credential is needed.
- With `AUTH_MODE=api_key`, the Preferences page can keep an API key in **sessionStorage** for the current tab and the interceptor sends it as `X-API-Key`.
- With Azure Easy Auth, use the platform `/.auth/login/aad` and `/.auth/logout` endpoints. Do not expose Azure principal headers from an untrusted reverse proxy.

## Azure Static Web Apps

`public/staticwebapp.config.json` provides SPA navigation fallback and security headers. Deploy the `frontend` directory with:

- App location: `/frontend`
- Output location: `dist/frontend/browser`
- Build command: `npm ci && npm run build`

When linking an Azure Container App as the Static Web Apps API backend, preserve the backend's `/api/v1` route prefix. The frontend uses relative URLs and therefore requires no environment-specific host in the bundle.

## Typed API contract

`src/app/core/api/api.models.ts` mirrors the named Pydantic response models from `docs/openapi.json`. `ApiService` is the only feature-facing HTTP layer. To regenerate a client instead, run the backend and use an OpenAPI generator against `http://127.0.0.1:8000/openapi.json`.
