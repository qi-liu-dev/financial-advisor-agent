from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.main import app  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the FastAPI OpenAPI document for Angular/client generation."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/openapi.json"),
        help="Destination path (default: docs/openapi.json).",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
