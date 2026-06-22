# Financial Advisor Agent Optimizer

A FastAPI prototype for building, evaluating, and improving structured LLM agents in synthetic investment-management workflows. The project supports public OpenAI and Azure OpenAI, typed API contracts, repeatable quality evaluation, controlled prompt promotion, traceability, and an Azure-ready deployment path.

> The bundled client, portfolio, meeting, and proposal records are synthetic. The prototype is not investment advice and is not a production system for real client data without the additional controls described below.

## What the project demonstrates

- Three specialised agents: client summary, meeting notes, and investment proposal review.
- Provider-neutral LLM access through one gateway supporting OpenAI, Azure OpenAI API keys, and Azure Managed Identity.
- Pydantic validation for inputs, structured model outputs, API responses, benchmark data, job records, and stored evaluation results.
- Rule-based, benchmark-expectation, and LLM-as-judge evaluation with provenance.
- Multilingual safety checks and concept-aware benchmark matching rather than English-only substring checks.
- GEPA-inspired prompt reflection and mutation with repeated benchmark runs, mean/standard-deviation metrics, policy tolerances, and Pareto selection.
- Explicit prompt lifecycle: `baseline`, `candidate`, `selected`, and `rejected`; only a baseline or selected prompt can be activated.
- Persistent asynchronous optimisation jobs with queue/running/completed/failed status and progress polling.
- Versioned database migrations, indexed queries, pagination, owner isolation, retention/delete operations, audit events, and optional field-level encryption.
- Versioned `/api/v1` API, Angular-compatible CORS, API-key or Azure Easy Auth identity, request IDs, safe error responses, and a demo rate limiter.
- Docker support and 43 automated tests.

## Architecture

```text
Angular / API consumer
        |
        |  typed JSON over /api/v1
        v
FastAPI routes + auth + owner isolation + rate limiting
        |
        +--> agent service -----------> unified LLM gateway
        |                                  |-- OpenAI API key
        |                                  |-- Azure OpenAI API key
        |                                  `-- Azure Managed Identity
        |
        +--> central evaluation service
        |      |-- multilingual deterministic rules
        |      |-- benchmark expectation checks
        |      `-- optional LLM judge + provenance
        |
        +--> prompt optimiser
        |      |-- persistent async job
        |      |-- repeated benchmark runs
        |      |-- mean/stddev metrics
        |      `-- tolerance + Pareto selection
        |
        `--> SQLite repositories
               |-- versioned migrations and indexes
               |-- ownership and pagination
               |-- audit and retention
               `-- optional Fernet encryption
```

For a production Azure deployment, the process-local optimiser worker should be replaced with a durable queue and worker/Container Apps Job, and SQLite should be replaced with a managed database or constrained to a single-replica demo deployment.

## Project structure

```text
backend/
  agents/             Financial-advisory agent definitions
  api/                Versioned routers, dependencies, converters, error mapping
  data/               Synthetic benchmark and mock datasets
  evaluation/         Rules, benchmark checks, judge, metrics, shared service
  llm/                Provider-neutral OpenAI/Azure gateway
  memory/             Advisor-preference repository
  models/             Pydantic API/domain schemas and database record types
  optimisation/       Prompt lifecycle, selection policy, loop, async jobs
  security/           Authentication, authorization, encryption, middleware
  traces/             Run persistence, pagination, deletion, retention
  audit.py            Access/change audit repository
  config.py           Environment-backed settings
  database.py         SQLite connections and versioned migrations
  main.py             FastAPI application factory and lifespan

tests/                Unit and API/integration tests
```

## Local setup

Use Python 3.11:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Run the API:

```bash
python -m uvicorn backend.main:app --reload --env-file .env
```

Open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

Run tests and static checks:

```bash
python -m pytest -q
python -m compileall -q backend tests
# Optional after installing Ruff:
python -m ruff check backend tests
```

The automated tests mock provider calls and do not require a real OpenAI or Azure credential.

## Provider configuration

### Public OpenAI

```dotenv
LLM_PROVIDER=openai
LLM_AUTH_MODE=api_key
OPENAI_API_KEY=replace-me
OPENAI_MODEL=gpt-4.1-mini
OPENAI_JUDGE_MODEL=gpt-4.1-mini
```

### Azure OpenAI with an API key

```dotenv
LLM_PROVIDER=azure
LLM_AUTH_MODE=api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_KEY=replace-me
OPENAI_MODEL=your-agent-deployment-name
OPENAI_JUDGE_MODEL=your-judge-deployment-name
```

### Azure OpenAI with Managed Identity

```dotenv
LLM_PROVIDER=azure
LLM_AUTH_MODE=managed_identity
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
OPENAI_MODEL=your-agent-deployment-name
OPENAI_JUDGE_MODEL=your-judge-deployment-name
# Set only for a user-assigned identity:
# AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
```

All model calls pass through `backend/llm/client.py`, which owns authentication, timeouts, SDK retries, structured-output validation, safe logging, application request IDs, and provider request IDs. See `LLM_CLIENT_REFACTOR.md` for details.

## API authentication and data isolation

### Local development

The default is intentionally convenient for local work:

```dotenv
AUTH_MODE=disabled
DEV_PRINCIPAL_ID=demo-advisor
DEV_PRINCIPAL_ROLES=admin,advisor
```

### API key mode

```dotenv
AUTH_MODE=api_key
API_KEYS_JSON={"replace-with-random-key":{"principal_id":"advisor-001","roles":["advisor"]}}
```

Send either:

```http
X-API-Key: replace-with-random-key
```

or:

```http
Authorization: Bearer replace-with-random-key
```

### Azure authentication mode

```dotenv
AUTH_MODE=azure_easy_auth
```

This mode reads the authenticated principal and roles from headers injected by Azure Container Apps/App Service authentication. Do not enable it on an endpoint that can be reached while bypassing that trusted authentication layer.

Non-admin principals only see their own run, memory, optimisation, and result data. Sensitive run-detail reads and data-changing actions produce audit events.

## Browser and Angular integration

The API is versioned under `/api/v1`. Local Angular development is allowed by default:

```dotenv
CORS_ALLOWED_ORIGINS=http://localhost:4200
```

For multiple origins, use a comma-separated value. Do not use a wildcard origin together with credentialed browser requests.

Every route has a named Pydantic response model, so Angular generation does not collapse business responses to `any`. Export a checked-in snapshot when the API changes:

```bash
python scripts/export_openapi.py
```

Then generate an Angular client from the running API or from `docs/openapi.json`. For example:

```bash
npx @openapitools/openapi-generator-cli generate \
  -i http://127.0.0.1:8000/openapi.json \
  -g typescript-angular \
  -o frontend/src/app/generated-api
```

A simple Angular development proxy can forward `/api` to FastAPI:

```json
{
  "/api": {
    "target": "http://127.0.0.1:8000",
    "secure": false,
    "changeOrigin": true
  }
}
```

## Prompt lifecycle and activation

The active prompt is no longer inferred from the newest database row.

```text
baseline  ── active at first seed
candidate ── produced by optimisation; never active automatically
selected  ── passed the acceptance policy and Pareto filter
rejected  ── evaluated but not selected
```

Only `baseline` and `selected` versions can be explicitly activated:

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/prompts/client_summary/VERSION/activate
```

This fixes the previous failure mode where an unselected candidate could silently become the default prompt for `/run-agent`.

## Evaluation and optimisation policy

One shared `EvaluationService` is used by both `/evaluate-run` and the optimiser. It combines:

1. deterministic multilingual safety and format rules;
2. concept-aware benchmark expectation checks;
3. an optional LLM judge;
4. latency and estimated cost metadata.

Evaluation responses include provenance, model identities, whether the judge is distinct, and a caveat when the same model is judging itself. To reject same-model judging:

```dotenv
REQUIRE_DISTINCT_JUDGE_MODEL=true
```

Optimisation repeats each benchmark run and stores mean, standard deviation, and sample count. A candidate first has to satisfy:

```text
quality >= baseline + minimum_quality_delta
safety  >= baseline - safety_tolerance
latency <= baseline * latency_tolerance_ratio
cost    <= baseline * cost_tolerance_ratio
```

The default policy is:

```dotenv
OPTIMISATION_MINIMUM_QUALITY_DELTA=0.05
OPTIMISATION_SAFETY_TOLERANCE=0.0
OPTIMISATION_LATENCY_TOLERANCE_RATIO=1.20
OPTIMISATION_COST_TOLERANCE_RATIO=1.10
```

Pareto filtering is then applied among policy-qualified candidates. A selected prompt is still not activated automatically; promotion is a separate administrator action.

## Asynchronous optimisation workflow

Create a job:

```bash
curl -X POST \
  http://127.0.0.1:8000/api/v1/optimisations/client_summary \
  -H 'Content-Type: application/json' \
  -d '{
    "max_variants": 2,
    "benchmark_limit": 2,
    "repetitions": 2
  }'
```

The API returns `202 Accepted` with an `OptimisationJobResponse`. Poll:

```bash
curl http://127.0.0.1:8000/api/v1/optimisations/JOB_ID
```

When `status` is `completed`, use `result_id`:

```bash
curl http://127.0.0.1:8000/api/v1/optimisation-results/RESULT_ID
```

Only one queued/running job is allowed per owner and agent type. Jobs left queued or running after a process restart are marked failed rather than appearing permanently active.

## Storage, privacy, and migrations

SQLite remains appropriate for this local prototype. On startup the application applies idempotent schema migrations recorded in `schema_migrations`. The current migrations add:

- LLM request IDs;
- prompt lifecycle and one-active-prompt enforcement;
- owner/advisor fields;
- optimisation jobs and audit events;
- query indexes;
- concurrent-job protection.

Back up the database before applying a new version:

```bash
cp optimizer.sqlite3 optimizer.sqlite3.backup
```

### Optional field-level encryption

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then configure:

```dotenv
DATA_ENCRYPTION_KEY=replace-with-generated-key
```

New JSON fields containing inputs, outputs, preferences, evaluations, job requests, and audit metadata are encrypted at rest. Existing plaintext rows remain readable to support gradual migration. Store the encryption key in Azure Key Vault or another secret manager; losing it makes encrypted rows unreadable.

### Retention and deletion

```dotenv
DATA_RETENTION_DAYS=90
```

Expired runs are purged at application startup. Owners can also delete individual runs or purge their own old runs through the API. Administrators can request an all-owner purge.

## Main endpoints

All business routes are prefixed by `/api/v1`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Root platform health probe |
| GET | `/api/v1/health` | Typed database/LLM readiness details |
| GET | `/api/v1/tasks` | Validated synthetic benchmark tasks |
| GET | `/api/v1/mock-data/{dataset}` | Synthetic clients, portfolios, meetings, or proposals |
| GET | `/api/v1/mock-data/workspaces/{client_id}` | Aggregated synthetic client workspace |
| POST | `/api/v1/run-agent` | Run an agent using an active or explicit prompt |
| POST | `/api/v1/evaluate-run/{run_id}` | Evaluate a stored run through the shared service |
| GET | `/api/v1/runs` | Paginated, owner-filtered run summaries |
| GET | `/api/v1/runs/{run_id}` | Authorized full run detail |
| DELETE | `/api/v1/runs/{run_id}` | Delete one authorized run |
| DELETE | `/api/v1/runs` | Retention purge |
| GET/POST/DELETE | `/api/v1/memory/{advisor_id}` | Read, update, or delete advisor preferences |
| GET | `/api/v1/prompt-versions/{agent_type}` | Paginated prompt history |
| GET | `/api/v1/prompts/{agent_type}/active` | Current active prompt |
| POST | `/api/v1/prompts/{agent_type}/{version}/activate` | Admin-only explicit promotion |
| POST | `/api/v1/optimisations/{agent_type}` | Queue asynchronous optimisation |
| GET | `/api/v1/optimisations` | Paginated job history |
| GET | `/api/v1/optimisations/{job_id}` | Job status and progress |
| GET | `/api/v1/optimisation-results` | Paginated result history |
| GET | `/api/v1/optimisation-results/{id}` | Typed optimisation result |
| GET | `/api/v1/audit-events` | Admin-only audit history |

## Example agent request

```bash
curl -X POST http://127.0.0.1:8000/api/v1/run-agent \
  -H 'Content-Type: application/json' \
  -d '{
    "agent_type": "client_summary",
    "task_id": "client-summary-001"
  }'
```

The response contains a schema-validated agent output plus `client_request_id` and `provider_request_id` for trace correlation.

## Docker

```bash
docker compose up --build
```

The compose file mounts `/data` for SQLite persistence. This is a single-process demo design. Do not scale multiple replicas against the same SQLite file.

## Test coverage

The suite includes:

- Pydantic schemas and OpenAPI response names;
- OpenAI/Azure client configuration, Managed Identity, retry, and request IDs;
- benchmark and multilingual safety evaluation;
- policy tolerance and Pareto selection;
- prompt activation safety;
- database migrations, indexes, encryption, isolation, retention, and audit behavior;
- CORS, API-key auth, Azure principal headers, rate limiting, run/evaluation APIs;
- persistent async optimisation jobs and concurrency protection;
- GEPA-inspired loop behavior with mocked providers.

```text
43 passed
```

## Remaining production work

- Replace the local `ThreadPoolExecutor` with a durable Azure queue and worker/Container Apps Job.
- Replace SQLite with PostgreSQL or Azure SQL for multi-replica operation.
- Put authentication enforcement, rate limiting, and network restrictions at the Azure ingress/API-management layer as well as in the app.
- Store keys and encryption material in Key Vault and use Managed Identity.
- Add OpenTelemetry/Application Insights, alerting, data-classification policy, and compliance review before using real client data.
