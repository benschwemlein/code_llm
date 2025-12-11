import json
import requests
import tkinter as tk
from tkinter import ttk, messagebox

import config


# Simple curated metadata for common models.
# We match by base name before the ":" tag (e.g. "llama3.1:8b" -> "llama3.1").
MODEL_INFO = {
    "nomic-embed-text": (
        "Nomic AI",
        "Text embedding model designed for high quality semantic search and retrieval.",
    ),
    "all-minilm": (
        "Microsoft / Hugging Face",
        "Small and fast general purpose embedding model based on MiniLM.",
    ),
    "llama3.1": (
        "Meta",
        "Llama 3.1 generation model, good general purpose chat and coding assistant.",
    ),
    "llama3": (
        "Meta",
        "Llama 3 series model for general chat and coding tasks.",
    ),
    "llama2": (
        "Meta",
        "Earlier Llama 2 series open model for chat and reasoning.",
    ),
    "qwen2.5": (
        "Alibaba Cloud",
        "Qwen 2.5 family model, strong at multilingual tasks and reasoning.",
    ),
    "qwen2": (
        "Alibaba Cloud",
        "Qwen 2 series general chat and coding model.",
    ),
    "mistral": (
        "Mistral AI",
        "Mistral family model, efficient general purpose LLM.",
    ),
    "mixtral": (
        "Mistral AI",
        "Mixture of experts model that trades size for higher quality.",
    ),
    "phi3": (
        "Microsoft",
        "Phi 3 series small model tuned for strong reasoning at small sizes.",
    ),
    "phi-3": (
        "Microsoft",
        "Phi 3 series small model tuned for strong reasoning at small sizes.",
    ),
}

# Suggested models to show in the download dropdown
SUGGESTED_PULL_MODELS = [
    "nomic-embed-text",
    "all-minilm",
    "llama3.1:8b",
    "llama3.1:70b",
    "llama3:8b",
    "qwen2.5:7b",
    "mistral:7b",
    "mixtral:8x7b",
    "phi3:3.8b",
]


def describe_model(name: str):
    """
    Return (company, description) for a given Ollama model name.

    We strip any tag after ":" and match by prefix in MODEL_INFO.
    """
    base = name.split(":", 1)[0].lower()

    # Exact key match first
    if base in MODEL_INFO:
        return MODEL_INFO[base]

    # Prefix match as fallback
    for key, info in MODEL_INFO.items():
        if base.startswith(key):
            return info

    return (
        "Unknown or community model",
        "No specific metadata is available. It may be a community or custom model.",
    )


class SettingsTab(ttk.Frame):
    """
    Tab for configuring runtime settings such as Ollama URL and model names.

    Changes update the config module globals, which are read by the indexer
    and query engine on each call.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.available_models: list[str] = []
        self.embed_combo = None
        self.chat_combo = None

        self.ollama_online = False
        self.status_var: tk.StringVar | None = None
        self.status_label: ttk.Label | None = None

        self._load_models_from_ollama()
        self._build_ui()
        self._update_status_indicator()

    def _load_models_from_ollama(self):
        """
        Query Ollama for the list of installed models.

        Populates self.available_models and updates self.ollama_online.
        Fails gracefully if Ollama is not reachable.
        """
        url = f"{config.OLLAMA_URL.rstrip('/')}/api/tags"
        self.ollama_online = False
        try:
            resp = requests.get(url, timeout=5)
        except Exception:
            self.available_models = []
            self._update_status_indicator()
            return

        if not resp.ok:
            self.available_models = []
            self._update_status_indicator()
            return

        try:
            data = resp.json()
        except Exception:
            self.available_models = []
            self._update_status_indicator()
            return

        models = []
        for m in data.get("models", []):
            name = m.get("name") or m.get("model")
            if name:
                models.append(name)

        # De duplicate and sort for nicer UX
        seen = set()
        unique_models = []
        for m in models:
            if m not in seen:
                seen.add(m)
                unique_models.append(m)

        self.available_models = sorted(unique_models)
        self.ollama_online = True
        self._update_status_indicator()

    def _build_ui(self):
        main_frame = ttk.LabelFrame(self, text="Ollama and model settings")
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Ollama URL
        ttk.Label(main_frame, text="Ollama URL:").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )
        self.ollama_url_var = tk.StringVar(value=config.OLLAMA_URL)
        ollama_entry = ttk.Entry(main_frame, textvariable=self.ollama_url_var, width=50)
        ollama_entry.grid(row=0, column=1, sticky="we", padx=4, pady=4)

        ollama_help_btn = ttk.Button(
            main_frame,
            text="?",
            width=2,
            command=self._show_ollama_help,
        )
        ollama_help_btn.grid(row=0, column=2, sticky="e", padx=4, pady=4)

        # Status indicator (green/red icon)
        self.status_var = tk.StringVar(value="● status unknown")
        self.status_label = ttk.Label(main_frame, textvariable=self.status_var)
        self.status_label.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Embedding model dropdown
        ttk.Label(main_frame, text="Embedding model:").grid(
            row=1, column=0, sticky="w", padx=4, pady=4
        )
        self.embed_model_var = tk.StringVar(value=config.EMBED_MODEL)

        self.embed_combo = ttk.Combobox(
            main_frame,
            textvariable=self.embed_model_var,
            values=self.available_models,
            width=40,
            state="normal",  # allow typing custom model names
        )
        self.embed_combo.grid(row=1, column=1, sticky="we", padx=4, pady=4)

        embed_help_btn = ttk.Button(
            main_frame,
            text="?",
            width=2,
            command=self._show_embed_model_help,
        )
        embed_help_btn.grid(row=1, column=2, sticky="e", padx=4, pady=4)

        # Chat model dropdown
        ttk.Label(main_frame, text="Chat model:").grid(
            row=2, column=0, sticky="w", padx=4, pady=4
        )
        self.chat_model_var = tk.StringVar(value=config.CHAT_MODEL)

        self.chat_combo = ttk.Combobox(
            main_frame,
            textvariable=self.chat_model_var,
            values=self.available_models,
            width=40,
            state="normal",  # allow typing custom model names
        )
        self.chat_combo.grid(row=2, column=1, sticky="we", padx=4, pady=4)

        chat_help_btn = ttk.Button(
            main_frame,
            text="?",
            width=2,
            command=self._show_chat_model_help,
        )
        chat_help_btn.grid(row=2, column=2, sticky="e", padx=4, pady=4)

        # Refresh models button
        refresh_btn = ttk.Button(
            main_frame,
            text="Refresh models from Ollama",
            command=self._refresh_models,
        )
        refresh_btn.grid(row=3, column=1, sticky="w", padx=4, pady=(4, 8))

        # Download model button (opens dropdown dialog)
        download_btn = ttk.Button(
            main_frame,
            text="Download model…",
            command=self._download_model,
        )
        download_btn.grid(row=3, column=2, sticky="w", padx=4, pady=(4, 8))

        main_frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        apply_btn = ttk.Button(btn_frame, text="Apply settings", command=self.apply_settings)
        apply_btn.pack(side="left")

        info_label = ttk.Label(
            btn_frame,
            text="These settings affect new queries and indexing runs.",
        )
        info_label.pack(side="right")

    # Status indicator

    def _update_status_indicator(self):
        """
        Update the green/red status icon and text based on self.ollama_online.
        """
        if self.status_var is None or self.status_label is None:
            return

        if self.ollama_online:
            self.status_var.set("● Ollama running")
            self.status_label.configure(foreground="green")
        else:
            self.status_var.set("● Ollama not reachable")
            self.status_label.configure(foreground="red")

    # Help popups

    def _show_ollama_help(self):
        messagebox.showinfo(
            "Ollama URL",
            (
                "The base URL where Ollama is running on your machine.\n\n"
                "Examples:\n"
                "  http://localhost:11434   (default on your own laptop)\n\n"
                "The app calls:\n"
                "  {URL}/api/embeddings  for embeddings\n"
                "  {URL}/api/chat        for chat completions\n\n"
                "If you do not have Ollama installed, download it from:\n"
                "  https://ollama.com/download\n\n"
                "After installing and starting Ollama, leave the URL as\n"
                "  http://localhost:11434\n"
                "unless you have configured Ollama to listen elsewhere.\n\n"
                "If you change the URL, click Refresh models to reload the\n"
                "model list from that instance."
            ),
        )

    def _show_embed_model_help(self):
        if self.available_models:
            lines = [
                "Embedding models discovered on this Ollama instance:\n"
            ]
            for name in self.available_models:
                company, desc = describe_model(name)
                lines.append(f"{name}")
                lines.append(f"  Company: {company}")
                lines.append(f"  Description: {desc}\n")

            lines.append(
                "Note: The same embedding model must be used for indexing and querying.\n"
                "If you change this, you should re index your repository."
            )
            text = "\n".join(lines)
        else:
            text = (
                "Name of the Ollama model used for embeddings.\n\n"
                "This model turns code and text into vectors for ChromaDB.\n"
                "All indexing and query similarity search depends on this.\n\n"
                "Examples:\n"
                "  nomic-embed-text\n"
                "  all-minilm\n\n"
                "The same embedding model must be used for both indexing and querying.\n"
                "You can see installed models in the Ollama app or by running:\n"
                "  ollama list"
            )

        messagebox.showinfo("Embedding model", text)

    def _show_chat_model_help(self):
        if self.available_models:
            lines = [
                "Chat models discovered on this Ollama instance:\n"
            ]
            for name in self.available_models:
                company, desc = describe_model(name)
                lines.append(f"{name}")
                lines.append(f"  Company: {company}")
                lines.append(f"  Description: {desc}\n")

            lines.append(
                "Note: You can change the chat model without re indexing, since it only\n"
                "affects how the answer is generated from the retrieved snippets."
            )
            text = "\n".join(lines)
        else:
            text = (
                "Name of the Ollama chat model used to answer questions.\n\n"
                "This model reads your bug description plus the retrieved code\n"
                "snippets and generates the final explanation or fix suggestion.\n\n"
                "Examples:\n"
                "  llama3.1\n"
                "  llama3\n"
                "  qwen2.5\n\n"
                "You can switch this without re indexing, because embeddings do not\n"
                "depend on the chat model.\n"
                "You can see installed models by running:\n"
                "  ollama list"
            )

        messagebox.showinfo("Chat model", text)

    # Download model (dropdown dialog)

    def _download_model(self):
        """
        Open a small dialog with a dropdown of suggested models and an optional
        editable field so the user can pick (or type) a model to pull.
        """
        base_url = self.ollama_url_var.get().strip() or config.OLLAMA_URL
        if not base_url:
            messagebox.showerror("Download model", "Ollama URL is empty.")
            return

        # Small modal dialog
        dialog = tk.Toplevel(self)
        dialog.title("Download model")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ttk.Label(
            dialog,
            text="Choose a model to download (or type a custom name):",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

        model_var = tk.StringVar(value=SUGGESTED_PULL_MODELS[0] if SUGGESTED_PULL_MODELS else "")
        combo = ttk.Combobox(
            dialog,
            textvariable=model_var,
            values=SUGGESTED_PULL_MODELS,
            width=40,
            state="normal",  # allow typing custom
        )
        combo.grid(row=1, column=0, columnspan=2, sticky="we", padx=8, pady=4)
        combo.focus_set()

        result = {"name": None}

        def on_ok():
            name = model_var.get().strip()
            if not name:
                messagebox.showerror("Download model", "Please choose or type a model name.")
                return
            result["name"] = name
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        ok_btn = ttk.Button(dialog, text="Download", command=on_ok)
        ok_btn.grid(row=2, column=0, sticky="e", padx=8, pady=8)

        cancel_btn = ttk.Button(dialog, text="Cancel", command=on_cancel)
        cancel_btn.grid(row=2, column=1, sticky="w", padx=8, pady=8)

        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)

        self.wait_window(dialog)

        model_name = result["name"]
        if not model_name:
            return

        url = f"{base_url.rstrip('/')}/api/pull"
        try:
            resp = requests.post(url, json={"name": model_name}, stream=True)
        except Exception as e:
            messagebox.showerror(
                "Download model",
                f"Could not contact Ollama at {base_url}.\n\nError: {e}",
            )
            self.ollama_online = False
            self._update_status_indicator()
            return

        if not resp.ok:
            text = resp.text[:400] if resp.text else f"Status {resp.status_code}"
            messagebox.showerror(
                "Download model",
                f"Ollama returned an error while pulling model:\n\n{text}",
            )
            self.ollama_online = False
            self._update_status_indicator()
            return

        # Consume the streaming progress, watch for error or success status
        error_msg = None
        success = False

        try:
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line.decode("utf8"))
                except Exception:
                    continue

                if "error" in obj:
                    error_msg = obj["error"]
                    break
                status = obj.get("status") or obj.get("message")
                if isinstance(status, str) and "success" in status.lower():
                    success = True
        except Exception:
            # If streaming fails partway through, just fall back to "check Ollama"
            pass

        if error_msg:
            messagebox.showerror(
                "Download model",
                f"Model download failed:\n\n{error_msg}",
            )
        elif success:
            messagebox.showinfo(
                "Download model",
                f"Model '{model_name}' downloaded successfully (or is ready to use).",
            )
        else:
            messagebox.showinfo(
                "Download model",
                f"Model '{model_name}' pull ended.\n"
                "If something looks off, check the Ollama UI or logs.",
            )

        # After downloading, refresh model list and status
        self._refresh_models()

    def _refresh_models(self):
        """
        Reload models from Ollama and update the dropdown lists.
        """
        # Use current URL from the field
        new_url = self.ollama_url_var.get().strip()
        if new_url:
            config.OLLAMA_URL = new_url

        self._load_models_from_ollama()

        if self.embed_combo is not None:
            self.embed_combo["values"] = self.available_models
        if self.chat_combo is not None:
            self.chat_combo["values"] = self.available_models

        if self.available_models:
            messagebox.showinfo(
                "Models refreshed",
                f"Loaded {len(self.available_models)} models from Ollama.",
            )
        else:
            messagebox.showwarning(
                "Models not found",
                "Could not load any models from Ollama. "
                "Check the URL and that Ollama is running.",
            )

    # Apply

    def apply_settings(self):
        # Update config globals from fields
        new_url = self.ollama_url_var.get().strip()
        if new_url:
            config.OLLAMA_URL = new_url

        new_embed = self.embed_model_var.get().strip()
        if new_embed:
            config.EMBED_MODEL = new_embed

        new_chat = self.chat_model_var.get().strip()
        if new_chat:
            config.CHAT_MODEL = new_chat

        # Refresh models / status in case URL changed
        self._refresh_models()

        messagebox.showinfo(
            "Settings applied",
            f"Ollama URL set to: {config.OLLAMA_URL}\n"
            f"Embedding model: {config.EMBED_MODEL}\n"
            f"Chat model: {config.CHAT_MODEL}",
        )
