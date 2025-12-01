import os
import sys
import argparse
import requests
import chromadb
from chromadb.config import Settings

# Embedding model name in Ollama
EMBED_MODEL = "nomic-embed-text"

# Default Chroma storage
DEFAULT_CHROMA_DIR = "./chroma_repo"
DEFAULT_COLLECTION_NAME = "repo_chunks"

# What file types to index
INDEX_EXTS = {
    ".java", ".kt",
    ".ts", ".tsx",
    ".js", ".jsx",
    ".html", ".css", ".scss",
    ".md", ".rst", ".adoc", ".txt",
    ".yml", ".yaml", ".json"
}

# Skip huge files
MAX_FILE_BYTES = 500_000

# Chunking
CHARS_PER_CHUNK = 1200
CHUNK_OVERLAP = 200


def should_index_file(path: str) -> bool:
    _, ext = os.path.splitext(path)
    return ext.lower() in INDEX_EXTS


def chunk_text(text: str, max_len: int, overlap: int):
    chunks = []
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
    Ask Ollama for an embedding of a single text chunk.

    If there is any problem, return None so the caller can
    skip this chunk instead of crashing.
    """
    url = "http://localhost:11434/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": text}

    try:
        resp = requests.post(url, json=payload)
    except requests.RequestException as e:
        print(f"[embed_text] Error calling Ollama: {e}")
        return None

    if resp.status_code != 200:
        print(f"[embed_text] Ollama returned {resp.status_code} for embeddings")
        try:
            body_preview = resp.text[:400]
            print(f"[embed_text] Response body (first 400 chars): {body_preview}")
        except Exception:
            pass
        return None

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[embed_text] Could not parse JSON from Ollama: {e}")
        return None

    embedding = data.get("embedding")
    if embedding is None:
        print(f"[embed_text] No 'embedding' field in response: {data}")
        return None

    return embedding


def main():
    parser = argparse.ArgumentParser(
        description="Index a repository into a local Chroma vector store"
    )
    parser.add_argument(
        "repo_root",
        help="Path to the repository to index"
    )
    parser.add_argument(
        "--index-dir",
        dest="index_dir",
        default=DEFAULT_CHROMA_DIR,
        help=f"Path to Chroma index directory (default {DEFAULT_CHROMA_DIR})"
    )
    parser.add_argument(
        "--collection",
        dest="collection",
        default=DEFAULT_COLLECTION_NAME,
        help=f"Chroma collection name (default {DEFAULT_COLLECTION_NAME})"
    )

    args = parser.parse_args()

    repo_root = os.path.abspath(args.repo_root)
    index_dir = args.index_dir
    collection_name = args.collection

    print(f"Indexing repo at {repo_root}")
    print(f"Using Chroma index directory: {index_dir}")
    print(f"Using collection name: {collection_name}")

    client = chromadb.PersistentClient(
        path=index_dir,
        settings=Settings(anonymized_telemetry=False)
    )

    # Reset collection for this index
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"description": "Code and documentation chunks"}
    )

    chunk_count = 0
    file_count = 0

    for root, dirs, files in os.walk(repo_root):

        # Skip unwanted dirs
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", ".idea", "node_modules",
                "build", "dist", "out", "target", ".gradle"
            }
        ]

        for fname in files:
            full = os.path.join(root, fname)

            if not should_index_file(full):
                continue

            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            try:
                with open(full, "r", encoding="utf8", errors="ignore") as f:
                    text = f.read()
            except Exception:
                continue

            if not text.strip():
                continue

            rel = os.path.relpath(full, repo_root)
            chunks = chunk_text(text, CHARS_PER_CHUNK, CHUNK_OVERLAP)

            for idx, chunk in enumerate(chunks):
                embedding = embed_text(chunk)
                if embedding is None:
                    print(f"[index_repo] Skipping {rel} chunk {idx} due to embedding error")
                    continue

                collection.add(
                    ids=[f"{rel}::chunk_{idx}"],
                    documents=[chunk],
                    metadatas=[{"path": rel, "chunk_index": idx}],
                    embeddings=[embedding]
                )

                chunk_count += 1
                if chunk_count % 100 == 0:
                    print(f"Indexed {chunk_count} chunks...")

            file_count += 1
            if file_count % 50 == 0:
                print(f"Processed {file_count} files...")

    print(f"\nDONE.\nFiles processed: {file_count}\nChunks indexed: {chunk_count}")


if __name__ == "__main__":
    main()
