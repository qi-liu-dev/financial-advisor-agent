# Financial Advisor Agent Optimizer

A FastAPI-based prototype for evaluating and improving LLM agents in mock wealth-management workflows. It demonstrates multi-agent patterns, OpenAI API usage, structured outputs, trace logging, evaluation loops, advisor memory, and GEPA-inspired prompt optimisation.
 
The idea is: a financial advisor has client information, meeting notes, portfolio summaries, and investment proposal drafts. The system uses several specialised agents to produce structured, reviewable outputs, and also evaluates the agent outputs, and tries to improve prompts over time.

## Core Features

- Three OpenAI-backed agents: client summaries, meeting notes, and investment proposal review.
- Pydantic structured JSON outputs with fields such as `summary`, `key_points`, `risks`, `next_actions`, `confidence`, and `citations_to_input`.
- SQLite trace logging for every agent run.
- Rule-based and LLM-as-judge evaluation.
- GEPA-inspired prompt optimisation loop with reflection, prompt variants, benchmark re-runs, and Pareto selection.
- Richer benchmark tasks with difficulty levels, scenario tags, expected mentions, forbidden phrases, and required citations.
- Regression thresholds for quality, safety, format correctness, benchmark-specific expectations, latency, and estimated cost.
- Advisor memory for personalisation preferences.
- FastAPI endpoints for running agents, evaluating runs, optimising prompts, listing traces, and updating memory.
- Tests for schemas, evaluator logic, Pareto selection, and API health.
- Docker and docker-compose for local deployment.


## Project Structure

```text
backend/
  agents/          OpenAI-backed advisory agents
  data/            Synthetic benchmark data, mock input data, and regression thresholds
  evaluation/      Rule-based checks, LLM-as-judge evaluation, and regression runner
  memory/          Advisor preference storage
  models/          Pydantic schemas and record types
  optimisation/    GEPA-inspired prompt optimisation loop
  traces/          SQLite trace logging
  main.py          FastAPI app
tests/             Pytest suite
```

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Edit `.env` and set:

```bash
OPENAI_API_KEY=sk-your-key-here
```

The code reads the key from `OPENAI_API_KEY` only. No secrets are hardcoded.

## Run The API

```bash
uvicorn backend.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Run With Docker

```bash
docker compose up --build
```

## Run Tests

```bash
pytest
```

The tests do not call the OpenAI API.

## Run Benchmark Regression Checks

Regression checks run the selected agent over benchmark tasks and fail if aggregate metrics fall below configured thresholds in `backend/data/regression_thresholds.json`.

```bash
python -m backend.evaluation.regression --agent client_summary --benchmark-limit 1
```

You can also run:

```bash
python -m backend.evaluation.regression --agent meeting_notes --benchmark-limit 1
python -m backend.evaluation.regression --agent investment_review --benchmark-limit 1
```

These commands call the OpenAI API, so they require `OPENAI_API_KEY`. For quick local verification without OpenAI calls, use `pytest`.

## Example Workflow

1. Store advisor preferences.
2. Run one of the agents on a synthetic benchmark task.
3. Evaluate the run with rule checks and LLM-as-judge.
4. Optimise the baseline prompt for one agent type.
5. Inspect prompt versions and traces.

### Health

```bash
curl http://127.0.0.1:8000/health
```

### List Benchmark Tasks

```bash
curl http://127.0.0.1:8000/tasks
```

### Save Advisor Memory

```bash
curl -X POST http://127.0.0.1:8000/memory/demo-advisor \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "summary_style": "brief",
      "detail_level": "medium",
      "risk_focus": "high",
      "preferred_language": "en"
    }
  }'
```

### Run An Agent

```bash
curl -X POST http://127.0.0.1:8000/run-agent \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "client_summary",
    "advisor_id": "demo-advisor",
    "task_id": "client-summary-001"
  }'
```

### Evaluate A Run

```bash
curl -X POST http://127.0.0.1:8000/evaluate-run/YOUR_RUN_ID
```

### Run GEPA-Inspired Optimisation

```bash
curl -X POST http://127.0.0.1:8000/optimise/client_summary \
  -H "Content-Type: application/json" \
  -d '{
    "advisor_id": "demo-advisor",
    "max_variants": 1,
    "benchmark_limit": 1
  }'
```

### Inspect Prompt Versions

```bash
curl http://127.0.0.1:8000/prompt-versions/client_summary
```

## Example Optimisation Result

Before optimisation, the baseline prompt may score lower on citation discipline or advisor-useful next actions:

```json
{
  "version": "baseline",
  "metrics": {
    "quality": 3.83,
    "safety": 4.0,
    "latency_ms": 1250.4,
    "estimated_cost": 0.00042
  }
}
```

After the GEPA-inspired loop reflects on weak cases and mutates the prompt, a selected candidate might look like this:

```json
{
  "version": "gepa_inspired_20260518183000_1",
  "metrics": {
    "quality": 4.35,
    "safety": 4.6,
    "latency_ms": 1190.2,
    "estimated_cost": 0.00039
  },
  "selection_reason": "Pareto-improving candidate: better quality and safety with no latency or cost regression."
}
```

The exact numbers depend on the model, benchmark subset, and current prompt variants.

## API Endpoints

- `GET /health`
- `GET /tasks`
- `POST /run-agent`
- `POST /evaluate-run/{run_id}`
- `POST /optimise/{agent_type}`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /prompt-versions/{agent_type}`
- `POST /memory/{advisor_id}`


## Future Improvements

- Add a small frontend dashboard for traces, scores, and prompt comparisons.
- Store OpenAI request ids and richer tracing metadata.
- Add model comparison across different OpenAI models.
