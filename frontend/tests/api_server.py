"""Run the unchanged API with a disposable database for browser tests."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import main

with TemporaryDirectory(prefix="tracker-browser-test-") as directory:
    main.DATABASE_PATH = str(Path(directory) / "test.db")
    uvicorn.run(main.app, host="127.0.0.1", port=8011)
