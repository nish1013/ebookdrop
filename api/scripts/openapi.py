"""Write the OpenAPI schema that the web client types come from."""

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine

from ebookdrop.app import create_app
from ebookdrop.clock import SystemClock
from ebookdrop.inspection.docker import DockerInspector
from ebookdrop.storage import LocalDiskStorage

app = create_app(
    create_engine("postgresql+psycopg://"),
    SystemClock(),
    LocalDiskStorage(Path()),
    DockerInspector(),
    origin="http://localhost:5173",
)
json.dump(app.openapi(), sys.stdout, indent=2, sort_keys=True)
sys.stdout.write("\n")
