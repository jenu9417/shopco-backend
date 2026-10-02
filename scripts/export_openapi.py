"""Write the OpenAPI spec to docs/openapi.json (hand it to the frontend dev / CI)."""

import json
from pathlib import Path

from app.main import app

out = Path("docs/openapi.json")
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"wrote {out}")
