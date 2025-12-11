import os
from pathlib import Path

# Name of your application (optional, used for future packaging)
APP_NAME = "local_code_query"

# Base directory of the project (folder containing this file)
BASE_DIR = Path(__file__).resolve().parent


# Helper to read environment variables with defaults
def env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# OLLAMA CONFIGURATION
# ---------------------------------------------------------------------------

# Base URL for Ollama API
# Can be overridden:
#   export LCQ_OLLAMA_URL="http://remotehost:11434"
OLLAMA_URL = env("LCQ_OLLAMA_URL", "http://localhost:11434")

# Embedding model
EMBED_MODEL = env("LCQ_EMBED_MODEL", "nomic-embed-text")

# Chat model for summarizing and answering
CHAT_MODEL = env("LCQ_CHAT_MODEL", "llama3.1")


# ---------------------------------------------------------------------------
# INDEX STORAGE CONFIGURATION
# ---------------------------------------------------------------------------

# Default directory where Chroma index will be stored.
# By default, keeps it inside your project folder:
#
#   local_code_query/chroma_repo/
#
DEFAULT_INDEX_DIR = env(
    "LCQ_INDEX_DIR",
    str(BASE_DIR / "chroma_repo")
)

# Default name of the Chroma collection
DEFAULT_COLLECTION_NAME = env(
    "LCQ_COLLECTION_NAME",
    "repo_chunks"
)


# ---------------------------------------------------------------------------
# QUERY BEHAVIOR DEFAULTS
# ---------------------------------------------------------------------------

DEFAULT_TOP_K = int(env("LCQ_TOP_K", "16"))

DEFAULT_MAX_DIRECT_EMBED_CHARS = int(
    env("LCQ_MAX_DIRECT_EMBED_CHARS", "4000")
)


# ---------------------------------------------------------------------------
# OPTIONAL: DEFAULT REPO PATH
# ---------------------------------------------------------------------------

# You can override with:
#   export LCQ_REPO_ROOT=/path/to/repo
DEFAULT_REPO_ROOT = env("LCQ_REPO_ROOT", "")
