# gui/index_tab.py

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from config import DEFAULT_INDEX_DIR, DEFAULT_REPO_ROOT, DEFAULT_COLLECTION_NAME
from indexing.indexer import index_repo


class IndexTab(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self._current_thread = None
        self._build_ui()

    def _build_ui(self):
        params_frame = ttk.LabelFrame(self, text="Index parameters")
        params_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(params_frame, text="Repo root:").grid(row=0, column=0, sticky="w")
        self.repo_root_var = tk.StringVar(value=DEFAULT_REPO_ROOT)
        repo_entry = ttk.Entry(params_frame, textvariable=self.repo_root_var, width=60)
        repo_entry.grid(row=0, column=1, sticky="we", padx=4)
        browse_repo_btn = ttk.Button(params_frame, text="Browse", command=self.browse_repo_root)
        browse_repo_btn.grid(row=0, column=2, padx=4)

        ttk.Label(params_frame, text="Index directory:").grid(row=1, column=0, sticky="w")
        self.index_dir_var = tk.StringVar(value=DEFAULT_INDEX_DIR)
        index_entry = ttk.Entry(params_frame, textvariable=self.index_dir_var, width=60)
        index_entry.grid(row=1, column=1, sticky="we", padx=4)
        browse_index_btn = ttk.Button(params_frame, text="Browse", command=self.browse_index_dir)
        browse_index_btn.grid(row=1, column=2, padx=4)

        ttk.Label(params_frame, text="Collection name:").grid(row=2, column=0, sticky="w")
        self.collection_var = tk.StringVar(value=DEFAULT_COLLECTION_NAME)
        collection_entry = ttk.Entry(params_frame, textvariable=self.collection_var, width=40)
        collection_entry.grid(row=2, column=1, sticky="w", padx=4)

        params_frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=8, pady=4)

        self.run_btn = ttk.Button(btn_frame, text="Run index", command=self.run_index)
        self.run_btn.pack(side="left")

        self.status_label = ttk.Label(btn_frame, text="")
        self.status_label.pack(side="right")

        log_frame = ttk.LabelFrame(self, text="Index log")
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = ScrolledText(log_frame, wrap="word", height=12)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def browse_repo_root(self):
        path = filedialog.askdirectory(initialdir=self.repo_root_var.get() or os.path.expanduser("~"))
        if path:
            self.repo_root_var.set(path)

    def browse_index_dir(self):
        path = filedialog.askdirectory(initialdir=self.index_dir_var.get() or os.path.expanduser("~"))
        if path:
            self.index_dir_var.set(path)

    def _log(self, msg: str):
        self.after(0, lambda: self._append_log(msg))

    def _append_log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def run_index(self):
        if self._current_thread and self._current_thread.is_alive():
            messagebox.showinfo("Info", "Indexing already running.")
            return

        repo_root = self.repo_root_var.get().strip()
        index_dir = self.index_dir_var.get().strip()
        collection_name = self.collection_var.get().strip()

        if not repo_root:
            messagebox.showerror("Error", "Repo root is required.")
            return
        if not os.path.isdir(repo_root):
            messagebox.showerror("Error", f"Repo root does not exist:\n{repo_root}")
            return

        self.log_text.delete("1.0", "end")
        self.run_btn.config(state="disabled")
        self.status_label.config(text="Indexing...")

        def worker():
            try:
                index_repo(
                    repo_root,
                    index_dir,
                    collection_name,
                    log=self._log,
                )
                self._done(True)
            except Exception as e:
                self._log(f"Error: {e}")
                self._done(False)

        self._current_thread = threading.Thread(target=worker, daemon=True)
        self._current_thread.start()

    def _done(self, success):
        def finish():
            self.run_btn.config(state="normal")
            self.status_label.config(text="Done" if success else "Failed")
        self.after(0, finish)
