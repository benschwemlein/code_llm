#!/usr/bin/env python3
import sys
import os
import argparse
import textwrap
import requests
import chromadb
from chromadb.config import Settings

EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.1"

CHROMA_DIR = "./chroma_repo"
COLLECTION_NAME = "repo_chunks"
DEFAULT_TOP_K = 8

# If the question is longer than this many characters,
# we first ask llama3.1 to summarize it into a shorter query text.
MAX_DIRECT_EMBED_CHARS = 4000


def embed_text(text: str):
    """
    Ask Ollama for an embedding of a single text chunk or query.

    Returns the embedding list or None on error, so caller can
    handle the failure instead of crashing.
    """
    url = "http://localhost:11434/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": text}

    try:
        resp = requests.post(url, json=payload)
    except requests.RequestException as e:
        print(f"[embed_text] Error calling Ollama: {e}", file=sys.stderr)
        return None

    if not resp.ok:
        print(f"[embed_text] Ollama returned {resp.status_code}", file=sys.stderr)
        try:
            print(f"[embed_text] Body (first 400 chars): {resp.text[:400]!r}", file=sys.stderr)
        except Exception:
            pass
        return None

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[embed_text] Could not parse JSON from Ollama: {e}", file=sys.stderr)
        return None

    embedding = data.get("embedding")
    if embedding is None:
        print(f"[embed_text] No 'embedding' field in response: {data}", file=sys.stderr)
        return None

    return embedding


def summarize_query(long_text: str) -> str:
    """
    Use the chat LLM to rewrite a long bug or log into a compact semantic query.
    If there is an error, fall back to the original long_text.
    """
    system_prompt = (
        "You are a senior engineer helping with code search.\n"
        "You will be given a long bug description, Jira ticket text, and or logs.\n"
        "Rewrite it as a shorter query that preserves all important technical details\n"
        "needed to search the codebase."
    )

    user_prompt = textwrap.dedent(f"""
    Long bug text:

    {long_text}

    Task:
    - Rewrite this as a concise search query for a codebase.
    - Keep all important technical details: class names, endpoints, error messages,
      stack trace fragments, config keys, error codes, etc.
    - Remove obvious noise (timestamps, repeated identical lines, huge uninformative blobs).
    - Length target: a few sentences or a short paragraph.
    - Do not invent new information.
    """)

    url = "http://localhost:11434/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }

    try:
        resp = requests.post(url, json=payload)
    except requests.RequestException as e:
        print(f"[summarize_query] Error calling Ollama: {e}", file=sys.stderr)
        print("[summarize_query] Falling back to full text for embedding.", file=sys.stderr)
        return long_text

    if not resp.ok:
        print(f"[summarize_query] Ollama returned {resp.status_code}", file=sys.stderr)
        print(f"[summarize_query] Body (first 400 chars): {resp.text[:400]!r}", file=sys.stderr)
        print("[summarize_query] Falling back to full text for embedding.", file=sys.stderr)
        return long_text

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[summarize_query] Could not parse JSON: {e}", file=sys.stderr)
        print("[summarize_query] Falling back to full text for embedding.", file=sys.stderr)
        return long_text

    summary = data["message"]["content"].strip()
    print(f"[query_repo] Summarized long question to {len(summary)} chars for embedding.", file=sys.stderr)
    print(f"[query_repo] Summarized long question text: '{summary}' for embedding.", file=sys.stderr)
    return summary


def chat_with_context(question, docs, metas):
    context_parts = []

    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        path = meta.get("path", "<unknown>")
        chunk_idx = meta.get("chunk_index", "?")
        header = f"[Snippet {i} from {path} chunk {chunk_idx}]"
        context_parts.append(header + "\n" + doc)

    context = "\n\n".join(context_parts)

    full_prompt = textwrap.dedent(f"""
    You are a senior engineer analyzing a large proprietary Java and Angular codebase.
    You must answer only using the provided snippets.
    If the answer is not in the snippets, say you do not know.

    Original user question (possibly long Jira bug or logs):
    {question}

    Relevant code and documentation snippets:
    {context}

    Answer concisely and, when possible, point to specific file paths, classes, and methods.
    """)

    url = "http://localhost:11434/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "user", "content": full_prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }

    resp = requests.post(url, json=payload)
    if not resp.ok:
        print(f"[chat_with_context] Ollama returned {resp.status_code}", file=sys.stderr)
        print(f"[chat_with_context] Body (first 400 chars): {resp.text[:400]!r}", file=sys.stderr)
        resp.raise_for_status()
    return resp.json()["message"]["content"]


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"[query_repo] File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except UnicodeDecodeError:
        print(f"[query_repo] Could not decode file as UTF 8: {path}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Query the local code index with a question or a text file for Jira bugs, logs, etc."
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="The question to ask about the codebase"
    )
    parser.add_argument(
        "-f", "--file",
        dest="file",
        help="Path to a text file whose contents will be used as the question"
    )
    parser.add_argument(
        "-k", "--top-k",
        dest="top_k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Number of top snippets to retrieve from the index (default {DEFAULT_TOP_K})"
    )
    parser.add_argument(
        "--index-dir",
        dest="index_dir",
        default=CHROMA_DIR,
        help=f"Path to Chroma index directory (default {CHROMA_DIR})"
    )
    parser.add_argument(
        "--collection",
        dest="collection",
        default=COLLECTION_NAME,
        help=f"Chroma collection name (default {COLLECTION_NAME})"
    )

    args = parser.parse_args()

    if args.file and args.question:
        print("[query_repo] Provide either a question or -f file, not both.", file=sys.stderr)
        sys.exit(1)

    if args.file:
        question = read_file(args.file)
        print(f"[query_repo] Using contents of file as question: {args.file}", file=sys.stderr)
    else:
        if not args.question:
            parser.print_help()
            sys.exit(1)
        question = args.question

    print(f"[query_repo] Using index directory: {args.index_dir}", file=sys.stderr)
    print(f"[query_repo] Using collection: {args.collection}", file=sys.stderr)

    if not os.path.isdir(args.index_dir):
        print(f"[query_repo] Index directory does not exist: {args.index_dir}", file=sys.stderr)
        sys.exit(1)

    client = chromadb.PersistentClient(
        path=args.index_dir,
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        collection = client.get_collection(args.collection)
    except Exception as e:
        print(f"[query_repo] Could not open collection '{args.collection}': {e}", file=sys.stderr)
        sys.exit(1)

    if len(question) > MAX_DIRECT_EMBED_CHARS:
        print(
            f"[query_repo] Question is {len(question)} chars, summarizing before embedding...",
            file=sys.stderr,
        )
        query_for_embedding = summarize_query(question)
    else:
        query_for_embedding = question

    print("[query_repo] Embedding query text...", file=sys.stderr)
    q_embedding = embed_text(query_for_embedding)
    if q_embedding is None:
        print("[query_repo] Failed to obtain embedding for query text.", file=sys.stderr)
        sys.exit(1)

    print(f"[query_repo] Querying index for top {args.top_k} snippets...", file=sys.stderr)
    res = collection.query(
        query_embeddings=[q_embedding],
        n_results=args.top_k,
        include=["documents", "metadatas"],
    )

    docs_list = res.get("documents", [[]])
    metas_list = res.get("metadatas", [[]])
    if not docs_list or not docs_list[0]:
        print("[query_repo] No relevant snippets found in the index.", file=sys.stderr)
        sys.exit(0)

    docs = docs_list[0]
    metas = metas_list[0]

    print("Using snippets from:")
    for meta in metas:
        path = meta.get("path", "<unknown>")
        chunk_idx = meta.get("chunk_index", "?")
        print(f"  {path} (chunk {chunk_idx})")

    print()
    answer = chat_with_context(question, docs, metas)
    print(answer)


if __name__ == "__main__":
    main()
