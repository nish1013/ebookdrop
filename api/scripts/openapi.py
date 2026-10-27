"""Write the OpenAPI schema that the web client types come from."""

import json
import sys

from sqlalchemy import create_engine

from ebookdrop.app import create_app
from ebookdrop.clock import SystemClock

app = create_app(create_engine("postgresql+psycopg://"), SystemClock())
json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
