import sys
import requests
import chromadb
from chromadb.config import Settings

EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.1"

CHROMA_DIR = "./chroma_repo"
COLLECTION_NAME = "repo_chunks"
TOP_K = 8


def embed_text(text: str):
    url = "http://localhost:11434/api/embeddings"
    payload = {"model": EMBED_MODEL, "prompt": text}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()["embedding"]


def chat_with_context(question, docs, metas):
    context = ""

    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        context += (
            f"\n[Snippet {i} from {meta['path']} chunk {meta['chunk_index']}]\n{doc}\n"
        )

    full_prompt = f"""
You are a senior engineer analyzing a large proprietary codebase.
You must answer ONLY using the provided snippets.
If the answer is not in the snippets, say you do not know.

Context:
{context}

Question:
{question}

Answer concisely.
"""

    url = "http://localhost:11434/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": full_prompt}],
        "stream": False,
    }

    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python query_repo.py \"your question\"")
        sys.exit(1)

    question = " ".join(sys.argv[1:])

    client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )

    collection = client.get_collection(COLLECTION_NAME)

    q_embedding = embed_text(question)

    res = collection.query(
        query_embeddings=[q_embedding],
        n_results=TOP_K,
        include=["documents", "metadatas"],
    )

    docs = res["documents"][0]
    metas = res["metadatas"][0]

    print("Using snippets from:")
    for meta in metas:
        print(f"  {meta['path']} (chunk {meta['chunk_index']})")

    print()
    answer = chat_with_context(question, docs, metas)
    print(answer)


if __name__ == "__main__":
    main()
