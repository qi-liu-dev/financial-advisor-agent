# Unified LLM Client Refactor

This repository centralises every provider call in `backend/llm/client.py`.
The agent, evaluator, reflection, and prompt-mutation modules no longer create
OpenAI SDK clients or implement their own provider checks.

## Responsibilities

`LLMClient` owns:

- public OpenAI versus Azure OpenAI selection;
- API-key versus Azure `DefaultAzureCredential` authentication;
- HTTP connect/read/write/pool timeouts;
- SDK retry configuration;
- provider and client request IDs;
- metadata-only logging;
- JSON Schema request construction and Pydantic response validation;
- provider-neutral exceptions.

Prompts, financial payloads, and model outputs are deliberately not written to
application logs.

## Repository changes

```text
backend/
  llm/
    __init__.py
    client.py
  config.py
  agents/base.py
  evaluation/llm_judge.py
  optimisation/reflection.py
  optimisation/prompt_mutation.py
  database.py
  traces/trace_logger.py
  main.py
.env.example
.dockerignore
```

The two request IDs from agent calls are persisted in `agent_runs` and returned
from `POST /run-agent`:

- `client_request_id`: generated before the call and kept stable across SDK
  retries;
- `provider_request_id`: returned by OpenAI or Azure when available.

`init_db()` includes an idempotent SQLite migration for existing databases.

## Configuration

Copy the template and activate the required section:

```bash
cp .env.example .env
```

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
```

For a user-assigned identity, also set:

```dotenv
AZURE_CLIENT_ID=00000000-0000-0000-0000-000000000000
```

Grant that identity access to the Azure OpenAI resource, for example with the
`Cognitive Services OpenAI User` role. During local development,
`DefaultAzureCredential` can use the developer's Azure CLI login:

```bash
az login
```

## Local commands

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload --env-file .env
```

Tests do not need a real provider credential:

```bash
pytest -q
```

## Adding another structured LLM operation

Define a Pydantic response model and call the gateway:

```python
from pydantic import BaseModel

from backend.config import get_settings
from backend.llm import get_llm_client


class MyResult(BaseModel):
    answer: str


settings = get_settings()
result = get_llm_client().structured_chat(
    model=settings.openai_model,
    system_prompt="Return a grounded answer.",
    user_message="Synthetic input only.",
    response_model=MyResult,
    temperature=0.0,
    operation="feature.my_operation",
    log_context={"feature": "example"},
)

print(result.output.answer)
print(result.client_request_id)
print(result.provider_request_id)
```

Do not instantiate `OpenAI()` anywhere outside `backend/llm/client.py`.

## Error handling

The gateway maps SDK failures to provider-neutral exceptions:

- `LLMConfigurationError` — missing or contradictory environment settings;
- `LLMRequestError` — timeout, connection error, authentication error, rate
  limit, or upstream status failure;
- `LLMResponseError` — refusal, empty content, or invalid Pydantic output.

The FastAPI layer converts these into safe `503` or `502` responses and returns
correlation IDs without exposing prompts, financial payloads, credentials, or
raw provider error bodies.
