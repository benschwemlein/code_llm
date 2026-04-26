#!/usr/bin/env python3
"""
CLI for querying a local RAG index.

Usage:
    python cli/rag_query.py --index /path/to/index "your question here"
    python cli/rag_query.py --index /path/to/index --top-k 20 "your question"

Reads model settings (embed_model, chat_model, ollama_url) from
~/.local-rag-llm/config.json — the same settings file the GUI uses.
"""

import argparse
import json
import sys
import os
from pathlib import Path

# Allow running from repo root or cli/ directory
_HERE = Path(__file__).parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO))


def _load_settings() -> dict:
    p = Path.home() / ".local-rag-llm" / "config.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def main():
    settings = _load_settings()
    qt = settings.get("query_tab") or {}
    st = settings.get("settings_tab") or {}

    parser = argparse.ArgumentParser(
        description="Query a local RAG index and return ranked code snippets."
    )
    parser.add_argument("query", nargs="+", help="Query text")
    parser.add_argument(
        "--index", "-i",
        default=qt.get("index_dir", ""),
        help="Path to ChromaDB index directory (default: from GUI settings)",
    )
    parser.add_argument(
        "--top-k", "-k",
        type=int,
        default=qt.get("top_k", 12),
        help="Number of results to return (default: %(default)s)",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=qt.get("max_chars", 4000),
        help="Summarize query if longer than this many chars (default: %(default)s)",
    )
    parser.add_argument(
        "--no-snippets",
        action="store_true",
        help="Print only file paths and scores, not snippet content",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON",
    )

    args = parser.parse_args()
    query_text = " ".join(args.query)

    if not args.index:
        print("ERROR: --index is required (or set index_dir in GUI settings)", file=sys.stderr)
        sys.exit(1)

    # Apply settings to config module
    import config
    if st.get("ollama_url"):
        config.OLLAMA_URL = st["ollama_url"]
    if st.get("embed_model"):
        config.EMBED_MODEL = st["embed_model"]
    if st.get("chat_model"):
        config.CHAT_MODEL = st["chat_model"]

    # Load prompts for summarizer (only needed if query > max_chars)
    summarizer_template = settings.get("prompts_tab", {}).get("summarizer_prompt", "")

    from querying.query_engine import _embed_text, _summarize_query, _compute_relative_scores
    import chromadb
    from chromadb.config import Settings

    def log(msg):
        print(msg, file=sys.stderr)

    # Summarize if needed
    query_for_embed = query_text
    if len(query_text) > args.max_chars and summarizer_template:
        log(f"[rag_query] Query is {len(query_text)} chars, summarizing...")
        query_for_embed = _summarize_query(query_text, summarizer_template, log)

    log(f"[rag_query] Embedding query...")
    embedding = _embed_text(query_for_embed, log)
    if embedding is None:
        print("ERROR: Failed to get embedding from Ollama", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(
        path=args.index,
        settings=Settings(anonymized_telemetry=False),
    )
    collections = client.list_collections()
    if not collections:
        print(f"ERROR: No collections found in {args.index}", file=sys.stderr)
        sys.exit(1)

    collection = client.get_collection(collections[0].name)
    log(f"[rag_query] Querying collection '{collections[0].name}' for top {args.top_k} results...")

    res = collection.query(
        query_embeddings=[embedding],
        n_results=args.top_k * 3,
        include=["documents", "metadatas", "distances"],
    )

    docs_list  = res.get("documents", [[]])[0]
    metas_list = res.get("metadatas", [[]])[0]
    dist_list  = res.get("distances",  [[]])[0]

    # Deduplicate by source file
    seen: set[str] = set()
    deduped = []
    for doc, meta, dist in zip(docs_list, metas_list, dist_list):
        source = meta.get("source", "")
        if source not in seen:
            seen.add(source)
            deduped.append((doc, meta, dist))
        if len(deduped) == args.top_k:
            break

    scores = _compute_relative_scores([d[2] for d in deduped])

    if args.json_output:
        output = []
        for (doc, meta, dist), score in zip(deduped, scores):
            entry = {"source": meta.get("source", ""), "score": round(score, 1), "distance": dist}
            if not args.no_snippets:
                entry["snippet"] = doc
            output.append(entry)
        print(json.dumps(output, indent=2))
        return

    # Human-readable output
    print(f"\n=== RAG Results: {len(deduped)} files ===\n")
    for i, ((doc, meta, dist), score) in enumerate(zip(deduped, scores), 1):
        source = meta.get("source", "<unknown>")
        chunk  = meta.get("chunk_index", "?")
        print(f"[{i:02d}] {score:5.1f}%  {source}  (chunk {chunk})")
        if not args.no_snippets:
            print("-" * 60)
            print(doc[:600] + ("..." if len(doc) > 600 else ""))
            print()


if __name__ == "__main__":
    main()
