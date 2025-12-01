#!/usr/bin/env python3
import os
import sys
import textwrap
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import requests
import chromadb
from chromadb.config import Settings

# Models
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3.1"

# Defaults
DEFAULT_INDEX_DIR = os.path.expanduser("~/dev/indexes/commerce_customer_aeo")
DEFAULT_COLLECTION = "repo_chunks_commerce_customer_aeo"
DEFAULT_TOP_K = 16
DEFAULT_MAX_DIRECT_EMBED_CHARS = 4000


def embed_text(text: str):
    """
    Ask Ollama for an embedding of a single text chunk or query.

    Returns the embedding list or None on error.
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


def summarize_query(long_text: str, template: str):
    """
    Use the chat LLM to rewrite a long bug or log into a compact semantic query.

    The template can contain the placeholder <<BUG_TEXT>> which will be replaced
    with the full bug text.

    If there is an error, we fall back to the original long_text.
    """
    if "<<BUG_TEXT>>" in template:
        user_content = template.replace("<<BUG_TEXT>>", long_text)
    else:
        # Safe fallback if the placeholder was removed
        user_content = template + "\n\nBug text:\n" + long_text

    url = "http://localhost:11434/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "user", "content": user_content},
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
        return long_text

    if not resp.ok:
        print(f"[summarize_query] Ollama returned {resp.status_code}", file=sys.stderr)
        print(f"[summarize_query] Body (first 400 chars): {resp.text[:400]!r}", file=sys.stderr)
        return long_text

    try:
        data = resp.json()
    except ValueError as e:
        print(f"[summarize_query] Could not parse JSON: {e}", file=sys.stderr)
        return long_text

    summary = data["message"]["content"].strip()
    print(f"[gui_query] Summarized question to {len(summary)} chars for embedding.", file=sys.stderr)
    return summary


def chat_with_context(question: str, docs, metas, template: str):
    """
    Call the chat model with the bug description and retrieved snippets.

    The template can contain the placeholders:
        <<BUG_TEXT>>   replaced with the original question / bug text
        <<SNIPPETS>>   replaced with the formatted snippets
    """
    context_parts = []
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        path = meta.get("path", "<unknown>")
        chunk_idx = meta.get("chunk_index", "?")
        header = f"[Snippet {i} from {path} chunk {chunk_idx}]"
        context_parts.append(header + "\n" + doc)

    snippets_text = "\n\n".join(context_parts)

    prompt = template
    if "<<BUG_TEXT>>" in prompt:
        prompt = prompt.replace("<<BUG_TEXT>>", question)
    else:
        prompt = prompt + "\n\nBug description:\n" + question

    if "<<SNIPPETS>>" in prompt:
        prompt = prompt.replace("<<SNIPPETS>>", snippets_text)
    else:
        prompt = prompt + "\n\nRelevant snippets:\n" + snippets_text

    url = "http://localhost:11434/api/chat"
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "user", "content": prompt},
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


class CodeSearchGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Local Code Query")

        # Main notebook with two tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.tab_query = ttk.Frame(notebook)
        self.tab_prompts = ttk.Frame(notebook)

        notebook.add(self.tab_query, text="Query")
        notebook.add(self.tab_prompts, text="Prompts")

        self._build_query_tab()
        self._build_prompts_tab()

        # Prefill prompt texts
        self._set_default_prompts()

    def _build_query_tab(self):
        # Top frame for parameters
        params_frame = ttk.LabelFrame(self.tab_query, text="Parameters")
        params_frame.pack(fill="x", padx=8, pady=8)

        # Index dir
        ttk.Label(params_frame, text="Index directory:").grid(row=0, column=0, sticky="w")
        self.index_dir_var = tk.StringVar(value=DEFAULT_INDEX_DIR)
        self.index_dir_entry = ttk.Entry(params_frame, textvariable=self.index_dir_var, width=60)
        self.index_dir_entry.grid(row=0, column=1, sticky="we", padx=4)
        browse_btn = ttk.Button(params_frame, text="Browse", command=self.browse_index_dir)
        browse_btn.grid(row=0, column=2, padx=4)

        # Collection
        ttk.Label(params_frame, text="Collection:").grid(row=1, column=0, sticky="w")
        self.collection_var = tk.StringVar(value=DEFAULT_COLLECTION)
        self.collection_entry = ttk.Entry(params_frame, textvariable=self.collection_var, width=40)
        self.collection_entry.grid(row=1, column=1, sticky="w", padx=4)

        # Top K
        ttk.Label(params_frame, text="Top K:").grid(row=2, column=0, sticky="w")
        self.top_k_var = tk.StringVar(value=str(DEFAULT_TOP_K))
        self.top_k_entry = ttk.Entry(params_frame, textvariable=self.top_k_var, width=10)
        self.top_k_entry.grid(row=2, column=1, sticky="w", padx=4)

        # Max chars before summarizing
        ttk.Label(params_frame, text="Max chars before summarize:").grid(row=3, column=0, sticky="w")
        self.max_chars_var = tk.StringVar(value=str(DEFAULT_MAX_DIRECT_EMBED_CHARS))
        self.max_chars_entry = ttk.Entry(params_frame, textvariable=self.max_chars_var, width=10)
        self.max_chars_entry.grid(row=3, column=1, sticky="w", padx=4)

        # Let the second column stretch
        params_frame.columnconfigure(1, weight=1)

        # Bug text frame
        bug_frame = ttk.LabelFrame(self.tab_query, text="Bug / Question")
        bug_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.bug_text = ScrolledText(bug_frame, wrap="word", height=12)
        self.bug_text.pack(fill="both", expand=True, padx=4, pady=4)

        btn_frame = ttk.Frame(bug_frame)
        btn_frame.pack(fill="x", padx=4, pady=4)

        load_btn = ttk.Button(btn_frame, text="Load from file…", command=self.load_bug_from_file)
        load_btn.pack(side="left")

        run_btn = ttk.Button(btn_frame, text="Run query", command=self.run_query)
        run_btn.pack(side="right")

        # Output frame
        output_frame = ttk.LabelFrame(self.tab_query, text="Output")
        output_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.output_text = ScrolledText(output_frame, wrap="word", height=12, state="normal")
        self.output_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_prompts_tab(self):
        # Summarizer prompt
        sum_frame = ttk.LabelFrame(self.tab_prompts, text="Summarizer prompt template")
        sum_frame.pack(fill="both", expand=True, padx=8, pady=8)

        sum_label = ttk.Label(
            sum_frame,
            text="Use <<BUG_TEXT>> where the full bug description should go."
        )
        sum_label.pack(anchor="w", padx=4, pady=2)

        self.summarizer_text = ScrolledText(sum_frame, wrap="word", height=10)
        self.summarizer_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Answer prompt
        chat_frame = ttk.LabelFrame(self.tab_prompts, text="Answer prompt template")
        chat_frame.pack(fill="both", expand=True, padx=8, pady=8)

        chat_label = ttk.Label(
            chat_frame,
            text="Use <<BUG_TEXT>> for bug description and <<SNIPPETS>> for retrieved code snippets."
        )
        chat_label.pack(anchor="w", padx=4, pady=2)

        self.chat_prompt_text = ScrolledText(chat_frame, wrap="word", height=12)
        self.chat_prompt_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _set_default_prompts(self):
        summarizer_default = textwrap.dedent("""
        You are a senior engineer helping with code search.

        You will be given a long bug description, Jira ticket text, logs, and sometimes SQL queries.
        Your job is to rewrite it as a shorter query that preserves all important technical details
        needed to search the codebase.

        Long bug text:

        <<BUG_TEXT>>

        Task:
        - Rewrite this as a concise search query for a codebase.
        - Keep all important technical details: class names, endpoints, error messages,
          stack trace fragments, config keys, error codes, i18n string keys, table and column names,
          and SQL fragments.
        - Never remove or alter i18n keys, table or column names, or any text that looks like SQL.
        - Remove obvious noise (timestamps, repeated identical lines, huge uninformative blobs).
        - Length target: a few sentences or a short paragraph.
        - Do not invent new information.
        """).strip()

        chat_default = textwrap.dedent("""
        You are a senior engineer working on a large Java and Angular based retail point of sale system.

        You will be given:
        - A bug description, which may include SQL, database results, UI behavior, and business context.
        - A set of code snippets retrieved as relevant to that bug.

        Your job:
        - Explain the likely root cause of the bug using the snippets as evidence.
        - Point to specific files, classes, and methods involved.
        - Explain what needs to be changed and where in order to fix the bug.
        - When possible, explain how to make the fix data driven so that future changes only require updating
          database or configuration entries rather than code.

        Bug description:
        <<BUG_TEXT>>

        Relevant code and documentation snippets:
        <<SNIPPETS>>

        Answer directly in terms of the bug, not as separate numbered questions.
        Separate clearly:
        - Facts that are directly supported by the snippets.
        - Hypotheses or guesses that go beyond the snippets.
        """).strip()

        self.summarizer_text.insert("1.0", summarizer_default)
        self.chat_prompt_text.insert("1.0", chat_default)

    def browse_index_dir(self):
        path = filedialog.askdirectory(initialdir=self.index_dir_var.get() or os.path.expanduser("~"))
        if path:
            self.index_dir_var.set(path)

    def load_bug_from_file(self):
        path = filedialog.askopenfilename(
            title="Select bug text file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return

        self.bug_text.delete("1.0", "end")
        self.bug_text.insert("1.0", content)

    def append_output(self, text: str):
        self.output_text.insert("end", text + "\n")
        self.output_text.see("end")
        self.update_idletasks()

    def run_query(self):
        self.output_text.delete("1.0", "end")

        index_dir = self.index_dir_var.get().strip()
        collection_name = self.collection_var.get().strip()
        bug = self.bug_text.get("1.0", "end-1c").strip()

        if not index_dir:
            messagebox.showerror("Error", "Index directory is required.")
            return
        if not collection_name:
            messagebox.showerror("Error", "Collection name is required.")
            return
        if not bug:
            messagebox.showerror("Error", "Bug or question text is required.")
            return

        try:
            top_k = int(self.top_k_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Top K must be an integer.")
            return

        try:
            max_chars = int(self.max_chars_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Max chars must be an integer.")
            return

        if not os.path.isdir(index_dir):
            messagebox.showerror("Error", f"Index directory does not exist:\n{index_dir}")
            return

        # Connect to Chroma
        try:
            client = chromadb.PersistentClient(
                path=index_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            collection = client.get_collection(collection_name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open collection '{collection_name}':\n{e}")
            return

        self.append_output(f"[gui_query] Using index directory: {index_dir}")
        self.append_output(f"[gui_query] Using collection: {collection_name}")

        # Summarize if needed
        query_for_embedding = bug
        if len(bug) > max_chars:
            self.append_output(f"[gui_query] Bug text is {len(bug)} chars, summarizing before embedding...")
            sum_template = self.summarizer_text.get("1.0", "end-1c")
            query_for_embedding = summarize_query(bug, sum_template)

        self.append_output("[gui_query] Embedding query text...")
        q_embedding = embed_text(query_for_embedding)
        if q_embedding is None:
            messagebox.showerror("Error", "Failed to obtain embedding from Ollama.")
            return

        self.append_output(f"[gui_query] Querying index for top {top_k} snippets...")

        res = collection.query(
            query_embeddings=[q_embedding],
            n_results=top_k,
            include=["documents", "metadatas"],
        )

        docs_list = res.get("documents", [[]])
        metas_list = res.get("metadatas", [[]])
        if not docs_list or not docs_list[0]:
            self.append_output("[gui_query] No relevant snippets found in the index.")
            return

        docs = docs_list[0]
        metas = metas_list[0]

        self.append_output("Using snippets from:")
        for meta in metas:
            path = meta.get("path", "<unknown>")
            chunk_idx = meta.get("chunk_index", "?")
            self.append_output(f"  {path} (chunk {chunk_idx})")

        self.append_output("")
        self.append_output("[gui_query] Asking LLM with retrieved context...")

        chat_template = self.chat_prompt_text.get("1.0", "end-1c")
        try:
            answer = chat_with_context(bug, docs, metas, chat_template)
        except Exception as e:
            messagebox.showerror("Error", f"Error calling chat model:\n{e}")
            return

        self.append_output("\n=== ANSWER ===\n")
        self.append_output(answer)


def main():
    app = CodeSearchGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
