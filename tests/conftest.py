import os
import tempfile

data = tempfile.TemporaryDirectory(prefix="culinary-tests-")
os.environ["CULINARY_MODE"] = "demo"
os.environ["CULINARY_DATA_DIR"] = data.name
os.environ["CULINARY_DEMO_DATABASE_URL"] = ""
os.environ["APP_ORIGIN"] = "http://localhost:5173"
os.environ["CHROMA_HOST"] = ""
os.environ["ANONYMIZED_TELEMETRY"] = "FALSE"
