import tkinter as tk
from tkinter import ttk, messagebox

import config


class SettingsTab(ttk.Frame):
    """
    Tab for configuring runtime settings such as Ollama URL and model names.

    Changes update the config module globals, which are read by the indexer
    and query engine on each call.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.LabelFrame(self, text="Ollama and model settings")
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Ollama URL
        ttk.Label(main_frame, text="Ollama URL:").grid(row=0, column=0, sticky="w", padx=4, pady=4)
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

        # Embedding model
        ttk.Label(main_frame, text="Embedding model:").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.embed_model_var = tk.StringVar(value=config.EMBED_MODEL)
        embed_entry = ttk.Entry(main_frame, textvariable=self.embed_model_var, width=40)
        embed_entry.grid(row=1, column=1, sticky="we", padx=4, pady=4)

        embed_help_btn = ttk.Button(
            main_frame,
            text="?",
            width=2,
            command=self._show_embed_model_help,
        )
        embed_help_btn.grid(row=1, column=2, sticky="e", padx=4, pady=4)

        # Chat model
        ttk.Label(main_frame, text="Chat model:").grid(row=2, column=0, sticky="w", padx=4, pady=4)
        self.chat_model_var = tk.StringVar(value=config.CHAT_MODEL)
        chat_entry = ttk.Entry(main_frame, textvariable=self.chat_model_var, width=40)
        chat_entry.grid(row=2, column=1, sticky="we", padx=4, pady=4)

        chat_help_btn = ttk.Button(
            main_frame,
            text="?",
            width=2,
            command=self._show_chat_model_help,
        )
        chat_help_btn.grid(row=2, column=2, sticky="e", padx=4, pady=4)

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
                "Change this if Ollama is listening on a different host or port."
            ),
        )

    def _show_embed_model_help(self):
        messagebox.showinfo(
            "Embedding model",
            (
                "Name of the Ollama model used for embeddings.\n\n"
                "This model turns code and text into vectors for ChromaDB.\n"
                "All indexing and query similarity search depends on this.\n\n"
                "Examples:\n"
                "  nomic-embed-text\n"
                "  all-minilm\n\n"
                "IMPORTANT:\n"
                "  • The same embedding model must be used for indexing and querying.\n"
                "    If you change this, you should re-index the repo."
            ),
        )

    def _show_chat_model_help(self):
        messagebox.showinfo(
            "Chat model",
            (
                "Name of the Ollama chat model used to answer questions.\n\n"
                "This model reads your bug description plus the retrieved code\n"
                "snippets and generates the final explanation / fix suggestion.\n\n"
                "Examples:\n"
                "  llama3.1\n"
                "  llama3\n"
                "  qwen2.5\n\n"
                "You can switch this without re-indexing, since it only affects\n"
                "the reasoning and wording of the answer, not the embeddings."
            ),
        )

    # Apply

    def apply_settings(self):
        config.OLLAMA_URL = self.ollama_url_var.get().strip() or config.OLLAMA_URL
        config.EMBED_MODEL = self.embed_model_var.get().strip() or config.EMBED_MODEL
        config.CHAT_MODEL = self.chat_model_var.get().strip() or config.CHAT_MODEL

        messagebox.showinfo(
            "Settings applied",
            f"Ollama URL set to: {config.OLLAMA_URL}\n"
            f"Embedding model: {config.EMBED_MODEL}\n"
            f"Chat model: {config.CHAT_MODEL}",
        )
