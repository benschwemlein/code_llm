import os
import requests
import chromadb
from chromadb.config import Settings

import config

# Common text-based code and project file types
DEFAULT_INDEX_EXTS: set[str] = {
    # Microsoft / .NET
    ".cs",
    ".csx",
    ".vb",
    ".fs", ".fsi", ".fsx",
    ".xaml",
    ".cshtml",
    ".config",
    ".resx",
    ".sln",
    ".csproj",
    ".vbproj",
    ".fsproj",

    # PHP ecosystem
    ".php",
    ".phtml",
    ".twig",
    ".tpl",

    # Java / JVM
    ".java",
    ".kt", ".kts",
    ".groovy", ".gvy",
    ".scala", ".sc",
    ".gradle",
    ".xml",
    ".properties",

    # JavaScript / Web
    ".js", ".jsx",
    ".ts", ".tsx",
    ".mjs", ".cjs",
    ".vue",
    ".svelte",
    ".astro",
    ".html",
    ".css", ".scss", ".less",
    ".json", ".json5",

    # Python / data science
    ".py",
    ".pyi",
    ".ipynb",
    ".toml",
    ".ini",
    ".cfg",
    ".env",

    # Mobile / UI markup
    ".plist",
    ".storyboard",
    ".xib",

    # C / C++ / embedded
    ".c",
    ".h",
    ".cpp", ".hpp",
    ".cc", ".cxx", ".hh",
    ".ino",
    ".mk",

    # Rust / Go / Ruby / Swift / ObjC
    ".rs",
    ".go",
    ".rb",
    ".swift",
    ".m", ".mm",

    # Cloud / infrastructure as code
    ".tf",
    ".tfvars",
    ".yaml",
    ".yml",
    ".json",  # already listed above, but set() will dedupe

    # SQL / query languages
    ".sql",
    ".psql",
    ".hql",
    ".cql",

    # Shell / scripts
    ".sh", ".bash",
    ".zsh",
    ".ksh",
    ".fish",
    ".bat", ".cmd",
    ".ps1", ".psm1",

    # Documentation
    ".md",
    ".rst",
    ".adoc",
    ".txt",
    ".csv",
}

MAX_FILE_BYTES = 500_000
CHARS_PER_CHUNK = 1200
CHUNK_OVERLAP = 200


def should_index_file(path: str, index_exts: set[str]) -> bool:
    """
    Return True if the file at 'path' should be indexed based on its extension.
    """
    _, ext = os.path.splitext(path)
    return ext.lower() in index_exts


def chunk_text(text: str, max_len: int, overlap: int) -> list[str]:
    """
    Split text into overlapping chunks of approximately max_len characters.
    """
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + max_len)
        chunks.append(text[start:end])
        if end == n:
            break
        start = end - overlap
    return chunks


def embed_text(text: str):
    """
    Call the local Ollama embedding endpoint for a single piece of text.
    Returns the embedding vector or None on error.
    """
    url = f"{config.OLLAMA_URL.rstrip('/')}/api/embeddings"
    payload = {"model": config.EMBED_MODEL, "prompt": text}

    try:
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("embedding")
    except Exception:
        return None


def index_repo(
    repo_root: str,
    index_dir: str | None = None,
    collection_name: str | None = None,
    index_exts: set[str] | None = None,
    max_file_bytes: int = MAX_FILE_BYTES,
    chars_per_chunk: int = CHARS_PER_CHUNK,
    chunk_overlap: int = CHUNK_OVERLAP,
    log=print,
):
    """
    Walk a repo, chunk supported files, embed each chunk, and write them into a Chroma collection.

    Parameters are usually set from the GUI, but sensible defaults exist for headless use.
    """
    repo_root = os.path.abspath(repo_root)
    index_dir = index_dir or config.DEFAULT_INDEX_DIR
    collection_name = collection_name or config.DEFAULT_COLLECTION_NAME
    index_exts = index_exts or DEFAULT_INDEX_EXTS

    log(f"Indexing repo at {repo_root}")
    log(f"Using Chroma index directory: {index_dir}")
    log(f"Using collection name: {collection_name}")
    log(f"Using Ollama URL: {config.OLLAMA_URL}")
    log(f"Using embed model: {config.EMBED_MODEL}")
    log(f"Max file size (bytes): {max_file_bytes}")
    log(f"Chars per chunk: {chars_per_chunk}")
    log(f"Chunk overlap: {chunk_overlap}")
    log(f"File types: {', '.join(sorted(index_exts))}")

    client = chromadb.PersistentClient(
        path=index_dir,
        settings=Settings(anonymized_telemetry=False),
    )

    # Drop the existing collection with this name and recreate it
    try:
        client.delete_collection(collection_name)
    except Exception:
        # ok if it doesn't exist yet
        pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "Code and documentation chunks"},
    )

    chunk_count = 0
    file_count = 0

    for root, dirs, files in os.walk(repo_root):
        # Skip typical build / IDE / dependency directories
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".idea", ".vscode",
                "node_modules",
                "build", "dist", "out", "target", ".gradle",
                ".venv", "venv", "__pycache__",
            }
        ]

        for fname in files:
            full = os.path.join(root, fname)

            if not should_index_file(full, index_exts):
                continue

            try:
                if os.path.getsize(full) > max_file_bytes:
                    continue
            except OSError:
                # If we cannot stat it, skip
                continue

            try:
                with open(full, "r", encoding="utf8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                # unreadable file, skip
                continue

            if not text.strip():
                continue

            rel = os.path.relpath(full, repo_root)
            chunks = chunk_text(text, chars_per_chunk, chunk_overlap)

            for idx, chunk in enumerate(chunks):
                embedding = embed_text(chunk)
                if embedding is None:
                    log(f"[index_repo] Skipping {rel} chunk {idx} due to embedding error")
                    continue

                collection.add(
                    ids=[f"{rel}::chunk_{idx}"],
                    documents=[chunk],
                    metadatas=[{"path": rel, "chunk_index": idx}],
                    embeddings=[embedding],
                )

                chunk_count += 1
                if chunk_count % 100 == 0:
                    log(f"Indexed {chunk_count} chunks...")

            file_count += 1
            if file_count % 50 == 0:
                log(f"Processed {file_count} files...")

    log("")
    log("DONE.")
    log(f"Files processed: {file_count}")
    log(f"Chunks indexed: {chunk_count}")
