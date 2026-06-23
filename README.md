# Advisor Agent Lab

An Azure-deployed AI agent evaluation and prompt-optimisation platform for **synthetic investment-management workflows**.

The project demonstrates how specialised LLM agents can be run, evaluated, compared, monitored, and promoted safely instead of being exposed as an ungoverned chat interface.

> **Synthetic data only.** This project does not provide investment advice and is not designed for real client data without additional security, compliance, persistence, and operational controls.

## 1. Project overview

Advisor Agent Lab contains three structured financial-advisory agents:

- **Client Summary** — prepares a concise client and portfolio overview for an advisor.
- **Meeting Notes** — converts a synthetic transcript into decisions, risks, follow-ups, and next actions.
- **Investment Review** — reviews a synthetic investment proposal for suitability context, risks, missing information, and compliance concerns.

Each agent returns a schema-validated Pydantic response rather than unrestricted text.

| Layer | Technology |
|---|---|
| Frontend | Angular 21, TypeScript, SCSS, Nginx |
| Backend | Python 3.11, FastAPI, Pydantic |
| LLM access | OpenAI or Azure OpenAI through one provider-neutral client |
| Evaluation | Deterministic rules, benchmark checks, optional LLM judge |
| Storage | SQLite with migrations, indexes, optional Fernet encryption |
| Cloud | Azure Container Apps and Azure Container Registry |



## 2. Live architecture

The current Azure deployment uses two container applications in the same Azure Container Apps environment:

```text
Browser
   |
   | HTTPS
   v
Angular + Nginx Container App
fa-agent-web-qi
   |
   | /api/v1/* through the environment service name
   v
FastAPI Container App
fa-agent-api-qi
   |
   +--> OpenAI API or Azure OpenAI
   |
   `--> SQLite demo database
```

Azure Container Registry stores the backend and frontend images.

Nginx serves the Angular application, supports client-side routes, and forwards `/api/v1/*` requests to FastAPI. Secrets and runtime settings are configured in Azure Container Apps rather than committed to the repository.

The demo uses:

- one active revision per application;
- one replica per application;
- API-key authentication between the browser and FastAPI;
- field-level encryption when `DATA_ENCRYPTION_KEY` is configured;
- public OpenAI at present, with Azure OpenAI and Managed Identity supported by the code.

## 3. Main capabilities

### Angular operations dashboard

The frontend contains six complete feature areas:

- **Overview** — runs, quality, safety, latency, estimated cost, active prompts, and system readiness.
- **Benchmark Tasks** — searchable synthetic tests with expectations and one-click playground handoff.
- **Agent Playground** — benchmark or custom JSON input, prompt selection, advisor preferences, and typed output rendering.
- **Run Evaluation** — run history, trace metadata, seven evaluation dimensions, feedback, and provenance.
- **Prompt Optimizer** — asynchronous jobs, reflection, repeated-run statistics, Pareto view, policy reasons, and prompt review.
- **Advisor Preferences** — persistent output preferences, development authentication, and synthetic client workspaces.

### Structured and traceable LLM calls

All model requests pass through `backend/llm/client.py`, which centralises:

- OpenAI and Azure OpenAI provider selection;
- API-key and Azure Managed Identity authentication;
- timeouts and SDK retry policy;
- Pydantic structured-output validation;
- safe metadata-only logging;
- application and provider request IDs;
- provider-neutral error handling.

### Evaluation and governance

A shared evaluation service combines:

1. multilingual deterministic safety and format checks;
2. concept-aware benchmark expectations;
3. an optional LLM judge with provenance;
4. latency and estimated-cost metadata.

Prompt versions follow a controlled lifecycle:

```text
baseline  -> initial active prompt
candidate -> generated and evaluated, never active automatically
selected  -> passed policy and Pareto filtering
rejected  -> evaluated but not accepted
```

Only a `baseline` or `selected` prompt can be explicitly activated. A newly generated candidate cannot silently replace the active prompt.

### Typed API and data controls

- Versioned API under `/api/v1`.
- Named Pydantic request and response models for reliable Angular typing.
- Pagination and owner isolation.
- API-key or Azure Easy Auth modes.
- Rate limiting, audit events, retention, and deletion endpoints.
- Versioned SQLite migrations and optional encrypted JSON fields.

## 4. End-to-end workflow

```text
Select synthetic task or client workspace
                |
                v
Load advisor preferences and active prompt
                |
                v
Run a specialised agent
                |
                v
Validate and store structured output, token usage,
latency, prompt version, and request IDs
                |
                v
Evaluate quality, safety, format, and expectations
                |
                v
Start asynchronous prompt optimisation
                |
                v
Reflect on weak cases and generate candidates
                |
                v
Repeat benchmarks and compare mean/stddev metrics
                |
                v
Apply quality, safety, latency, and cost gates
                |
                v
Review selected/rejected candidates
                |
                v
Explicitly activate an approved prompt
                |
                v
Monitor the result on the Overview dashboard
```

The optimisation endpoint returns `202 Accepted` with a job ID. The Angular client polls the job-status endpoint until the job is completed or failed, so a long-running optimisation does not block one HTTP request.

`No candidate selected` is a valid result: the current active prompt remains unchanged when candidates do not pass the configured policy.

## 5. Local setup

### Prerequisites

- Python 3.11
- Node.js `>=22.12.0 <23`
- npm 10.9.x
- an OpenAI API key, or an Azure OpenAI deployment

### Clone and install the backend

```bash
git clone https://github.com/qi-liu-dev/financial-advisor-agent.git
cd financial-advisor-agent

python3.11 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt

cp .env.example .env
```

For local development with public OpenAI, configure `.env`:

```dotenv
LLM_PROVIDER=openai
LLM_AUTH_MODE=api_key
OPENAI_API_KEY=replace-with-your-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_JUDGE_MODEL=gpt-4.1-mini

AUTH_MODE=disabled
CORS_ALLOWED_ORIGINS=http://localhost:4200
RATE_LIMIT_ENABLED=false
REQUIRE_LLM_FOR_READINESS=false
```

Never commit `.env` or place an OpenAI key in the Angular application.

Start FastAPI:

```bash
./.venv/bin/python -m uvicorn backend.main:app --reload --env-file .env
```

Backend URLs:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
http://127.0.0.1:8000/health
```

### Install and run Angular

In a second terminal:

```bash
cd frontend
npm ci
npm start
```

Open:

```text
http://localhost:4200
```

The development proxy forwards `/api/*` to FastAPI, so browser requests remain same-origin during local development.

## 6. Configuration

Copy `.env.example` and choose one LLM configuration.

### Public OpenAI

```dotenv
LLM_PROVIDER=openai
LLM_AUTH_MODE=api_key
OPENAI_API_KEY=replace-with-your-key
OPENAI_MODEL=gpt-4.1-mini
OPENAI_JUDGE_MODEL=gpt-4.1-mini
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

### Application authentication

```dotenv
# Convenient local development
AUTH_MODE=disabled

# Shared application key for a demo deployment
AUTH_MODE=api_key
API_KEYS_JSON={"replace-with-random-key":{"principal_id":"demo-advisor","roles":["admin","advisor"]}}

# Azure platform identity headers
AUTH_MODE=azure_easy_auth
```

The application API key is not the OpenAI key:

```text
Application API key -> browser calls FastAPI
OpenAI API key      -> FastAPI calls OpenAI
Managed Identity    -> Azure-hosted FastAPI calls Azure resources
```

### Optional controls

```dotenv
DATA_ENCRYPTION_KEY=replace-with-a-Fernet-key
DATA_RETENTION_DAYS=90
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=600
RATE_LIMIT_WINDOW_SECONDS=60
REQUIRE_DISTINCT_JUDGE_MODEL=false
```

Generate a Fernet key with:

```bash
./.venv/bin/python -c \
  'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

## 7. Tests

Backend tests use mocked provider calls and do not require a real model credential:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m compileall -q backend tests scripts
```

Expected backend result:

```text
43 passed
```

Frontend verification runs unit tests, a production build, and Prettier:

```bash
cd frontend
npm run verify
```

Expected frontend result:

```text
5 test files passed
8 tests passed
production build passed
format check passed
```

On systems with multiple Python installations, prefer `./.venv/bin/python -m pytest` over a bare `pytest` command.

## 8. Azure deployment

### Current deployment model

```text
Azure Container Registry
   |-- financial-advisor-agent-api:<git-sha>
   `-- financial-advisor-agent-web:<git-sha>

Azure Container Apps Environment
   |-- FastAPI Container App
   `-- Angular + Nginx Container App
```

Images are built locally with Docker Buildx and pushed to Azure Container Registry. This also works for subscriptions where ACR Tasks are unavailable.

Set deployment variables:

```bash
export RG="rg-fa-agent-demo"
export LOCATION="swedencentral"
export ACA_ENV="fa-agent-env"
export API_APP="fa-agent-api-qi"
export WEB_APP="fa-agent-web-qi"
export ACR_NAME="your-registry-name"

export ACR_SERVER="$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)"
export TAG="$(git rev-parse --short HEAD)"
```

Log in to the registry:

```bash
az acr login --name "$ACR_NAME"
```

### Build and push the backend

```bash
export API_IMAGE="$ACR_SERVER/financial-advisor-agent-api:$TAG"

docker buildx build \
  --platform linux/amd64 \
  --tag "$API_IMAGE" \
  --push \
  .
```

Update the backend Container App:

```bash
az containerapp update \
  --name "$API_APP" \
  --resource-group "$RG" \
  --image "$API_IMAGE"
```

### Build and push the frontend

```bash
export WEB_IMAGE="$ACR_SERVER/financial-advisor-agent-web:$TAG"

docker buildx build \
  --platform linux/amd64 \
  --file frontend/Dockerfile \
  --tag "$WEB_IMAGE" \
  --push \
  frontend
```

Update the web Container App:

```bash
az containerapp update \
  --name "$WEB_APP" \
  --resource-group "$RG" \
  --image "$WEB_IMAGE"
```

The web application must receive the internal API service name:

```text
API_UPSTREAM=http://fa-agent-api-qi
```

### Runtime settings

Configure sensitive values as Container Apps secrets and reference them from environment variables. The deployed backend uses settings such as:

```text
LLM_PROVIDER=openai
LLM_AUTH_MODE=api_key
OPENAI_API_KEY=secretref:openai-api-key
AUTH_MODE=api_key
API_KEYS_JSON=secretref:app-api-keys
DATA_ENCRYPTION_KEY=secretref:data-encryption-key
SQLITE_DB_PATH=/data/optimizer.sqlite3
OPTIMISATION_WORKER_COUNT=1
```

Keep both applications in single-revision, single-replica mode for the current architecture:

```bash
for APP in "$API_APP" "$WEB_APP"; do
  az containerapp revision set-mode \
    --name "$APP" \
    --resource-group "$RG" \
    --mode single

  az containerapp update \
    --name "$APP" \
    --resource-group "$RG" \
    --min-replicas 1 \
    --max-replicas 1
done
```

After validating the Nginx proxy, the FastAPI ingress can be restricted to internal access within the Container Apps environment.

The deployed Dashboard uses the **application API key** in:

```text
Advisor Preferences
-> Connection and identity
-> Development API key
```

Do not enter the OpenAI API key in the browser.

## 9. Current limitations

- **Synthetic data only.** The application is not approved for real client or investment data.
- **Ephemeral SQLite storage.** Data can be lost when the backend replica or revision is replaced. A production version should use Azure PostgreSQL or Azure SQL.
- **Process-local optimisation worker.** A running job can fail if the backend process restarts. A production version should use Service Bus or Storage Queue with a dedicated worker or Container Apps Job.
- **Single-replica architecture.** SQLite, the in-process worker, and the local rate limiter are not designed for horizontal scaling.
- **Demo authentication.** API-key mode is suitable for a controlled demo; Microsoft Entra ID and role assignment should be completed for multi-user deployment.
- **Possible same-model judge bias.** Using the same model as agent and judge can inflate or correlate scores; a distinct judge model and human review are preferable.
- **Benchmark ceiling effect.** On the current small synthetic benchmark set, the baseline prompt frequently reaches the maximum score of 5.00 / 5.00. Because the default acceptance policy requires candidates to improve quality by at least +0.05, no candidate can pass this threshold once the baseline is already at the scoring ceiling. Revised prompts may therefore be rejected even when they preserve quality or improve latency or cost. This reflects a limitation of the current benchmark set and selection policy, rather than a general failure of prompt optimisation.
- **Planned evaluation improvements.** Add harder and adversarial benchmark cases, ceiling-aware selection, early stopping when no weak cases exist, efficiency-focused mutations, and larger repeated samples.


---

The central design principle is simple:

```text
Run -> Evaluate -> Optimise -> Review -> Explicitly promote -> Monitor
```

A candidate is never deployed merely because it is newer.
