# Implementation and repository migration guide

This version implements the API, evaluation, prompt-lifecycle, privacy, asynchronous-job, and test recommendations on top of the unified LLM gateway refactor.

## Safe way to apply it to the existing repository

Create a branch in the existing `financial-advisor-agent` repository:

```bash
git switch main
git pull
git switch -c feat/production-ready-api-and-optimisation
```

Apply the supplied patch from the repository root:

```bash
git apply --check financial-advisor-agent-complete.patch
git apply financial-advisor-agent-complete.patch
```

Alternatively, copy the contents of the supplied complete ZIP into the repository while preserving the existing `.git/` directory. Never copy `.env`, `.venv`, a SQLite database, or another `.git/` directory.

Install and validate:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m pytest -q
python -m compileall -q backend tests
```

Expected test result:

```text
43 passed
```

Then review and commit:

```bash
git status
git diff --stat
git add backend tests README.md IMPLEMENTATION_GUIDE.md requirements.txt .env.example
git commit -m "Add typed API, safe prompt promotion and async optimisation"
git push -u origin feat/production-ready-api-and-optimisation
```

Open a pull request into `main`.

## Breaking API changes

Business endpoints moved from root paths to `/api/v1`:

```text
/tasks                         -> /api/v1/tasks
/run-agent                     -> /api/v1/run-agent
/evaluate-run/{run_id}         -> /api/v1/evaluate-run/{run_id}
/runs                          -> /api/v1/runs
/prompt-versions/{agent_type}  -> /api/v1/prompt-versions/{agent_type}
/memory/{advisor_id}           -> /api/v1/memory/{advisor_id}
```

The old synchronous endpoint:

```text
POST /optimise/{agent_type}
```

is replaced by:

```text
POST /api/v1/optimisations/{agent_type}   -> 202 + job
GET  /api/v1/optimisations/{job_id}       -> poll status
GET  /api/v1/optimisation-results/{id}    -> completed result
```

`GET /health` remains available for Docker/Azure probes.

## Existing database migration

The application upgrades existing SQLite files automatically and records each change in `schema_migrations`. Before first startup:

```bash
cp optimizer.sqlite3 optimizer.sqlite3.backup
```

The migration intentionally does not activate the most recently inserted prompt. It activates `baseline` when no explicit active prompt exists and marks historically selected versions where old optimisation results contain them.

## Prompt promotion rule

Optimisation candidates are stored as `candidate`, then marked `selected` or `rejected`. Selection never changes production/default behavior. An administrator must explicitly call the activation endpoint. The database has a partial unique index that permits only one active prompt per agent type.

## Authentication modes

- `disabled`: local development principal.
- `api_key`: application-level API keys defined by `API_KEYS_JSON`.
- `azure_easy_auth`: consumes identity headers injected by Azure's authentication layer.

Do not expose `azure_easy_auth` mode through an ingress path that bypasses Azure authentication, because raw identity headers must not be accepted from untrusted clients.

## SQLite and local worker boundaries

The custom migration runner, encryption, indexes, retention, and local job manager make the prototype materially safer and easier to demonstrate. They do not turn SQLite or an in-process thread pool into a multi-replica production architecture. For Azure productionization:

1. use PostgreSQL/Azure SQL and a formal migration tool such as Alembic;
2. enqueue optimisation requests in Service Bus/Storage Queue;
3. execute them in a dedicated worker or Container Apps Job;
4. use API Management or another shared rate limiter;
5. centralize telemetry and audit export.
