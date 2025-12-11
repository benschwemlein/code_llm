import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from config import DEFAULT_INDEX_DIR, DEFAULT_REPO_ROOT, DEFAULT_COLLECTION_NAME
from indexing.indexer import (
    index_repo,
    CHARS_PER_CHUNK,
    CHUNK_OVERLAP,
    MAX_FILE_BYTES,
)

COMMON_FILETYPE_GROUPS = {
    "Microsoft / .NET": [
        ".cs", ".csx", ".vb",
        ".fs", ".fsi", ".fsx",
        ".xaml",
        ".cshtml",
        ".config",
        ".resx",
        ".sln",
        ".csproj", ".vbproj", ".fsproj",
    ],
    "PHP ecosystem": [
        ".php", ".phtml", ".twig", ".tpl",
    ],
    "Java / JVM": [
        ".java",
        ".kt", ".kts",
        ".groovy", ".gvy",
        ".scala", ".sc",
        ".gradle",
        ".xml",
        ".properties",
    ],
    "JavaScript / Web": [
        ".js", ".jsx",
        ".ts", ".tsx",
        ".mjs", ".cjs",
        ".vue", ".svelte",
        ".astro",
        ".html",
        ".css", ".scss", ".less",
        ".json", ".json5",
    ],
    "Python / Data": [
        ".py", ".pyi",
        ".ipynb",
        ".toml",
        ".ini",
        ".cfg",
        ".env",
    ],
    "Mobile / UI": [
        ".xml",
        ".plist",
        ".storyboard",
        ".xib",
    ],
    "C / C++ / Embedded": [
        ".c", ".h",
        ".cpp", ".hpp",
        ".cc", ".cxx", ".hh",
        ".ino",
        ".mk",
    ],
    "Rust / Go / Ruby / Swift / ObjC": [
        ".rs",
        ".go",
        ".rb",
        ".swift",
        ".m", ".mm",
    ],
    "Cloud / IaC": [
        ".tf",
        ".tfvars",
        ".yaml",
        ".yml",
        ".json",
    ],
    "SQL / Query": [
        ".sql",
        ".psql",
        ".hql",
        ".cql",
    ],
    "Shell / Scripts": [
        ".sh", ".bash", ".zsh",
        ".ksh",
        ".fish",
        ".bat", ".cmd",
        ".ps1", ".psm1",
    ],
    "Documentation": [
        ".md", ".rst", ".adoc",
        ".txt",
        ".csv",
    ],
}


class CollapsibleFrame(ttk.Frame):
    def __init__(self, parent, text="", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self._shown = tk.BooleanVar(value=True)

        header = ttk.Frame(self)
        header.pack(fill="x")

        self._btn = ttk.Checkbutton(
            header,
            text=text,
            variable=self._shown,
            command=self._toggle,
            style="Toolbutton",
        )
        self._btn.pack(side="left", padx=2, pady=2)

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)

    def _toggle(self):
        if self._shown.get():
            self.body.pack(fill="both", expand=True)
        else:
            self.body.forget()


class IndexTab(ttk.Frame):

    def __init__(self, parent):
        super().__init__(parent)
        self._current_thread = None
        self._ext_vars: dict[str, tk.BooleanVar] = {}
        self._build_ui()

    def _build_ui(self):
        params_frame = ttk.LabelFrame(self, text="Index parameters")
        params_frame.pack(fill="x", padx=8, pady=8)

        # Repo root
        ttk.Label(params_frame, text="Repo root:").grid(row=0, column=0, sticky="w")
        self.repo_root_var = tk.StringVar(value=DEFAULT_REPO_ROOT)
        ttk.Entry(params_frame, textvariable=self.repo_root_var, width=60).grid(
            row=0, column=1, sticky="we", padx=4
        )
        ttk.Button(params_frame, text="Browse", command=self.browse_repo_root).grid(row=0, column=2, padx=4)
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Repo root",
                (
                    "Top folder of the source tree you want to index.\n\n"
                    "The indexer walks this directory and all child folders and reads files "
                    "that match the selected file types."
                ),
            ),
        ).grid(row=0, column=3)

        # Index directory
        ttk.Label(params_frame, text="Index directory:").grid(row=1, column=0, sticky="w")
        self.index_dir_var = tk.StringVar(value=DEFAULT_INDEX_DIR)
        ttk.Entry(params_frame, textvariable=self.index_dir_var, width=60).grid(
            row=1, column=1, sticky="we", padx=4
        )
        ttk.Button(params_frame, text="Browse", command=self.browse_index_dir).grid(row=1, column=2, padx=4)
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Index directory",
                (
                    "Base folder where index data is stored.\n\n"
                    "A subfolder named with the collection name will be created here for this index."
                ),
            ),
        ).grid(row=1, column=3)

        # Collection name
        ttk.Label(params_frame, text="Collection name:").grid(row=2, column=0, sticky="w")
        self.collection_var = tk.StringVar(value=DEFAULT_COLLECTION_NAME)
        ttk.Entry(params_frame, textvariable=self.collection_var, width=40).grid(
            row=2, column=1, sticky="w", padx=4
        )
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Collection name",
                (
                    "Logical name for this index.\n\n"
                    "Used as the Chroma collection name and as the subfolder name under the index directory."
                ),
            ),
        ).grid(row=2, column=3)

        # Chars per chunk
        ttk.Label(params_frame, text="Chars per chunk:").grid(row=3, column=0, sticky="w")
        self.chars_per_chunk_var = tk.StringVar(value=str(CHARS_PER_CHUNK))
        ttk.Entry(params_frame, textvariable=self.chars_per_chunk_var, width=10).grid(
            row=3, column=1, sticky="w", padx=4
        )
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Chars per chunk",
                (
                    "Target maximum characters in each text chunk sent to the embedding model.\n\n"
                    "Larger values capture more context in one chunk. Smaller values give tighter snippets "
                    "but may lose surrounding context. Typical range is about 800 to 2000."
                ),
            ),
        ).grid(row=3, column=3)

        # Chunk overlap
        ttk.Label(params_frame, text="Chunk overlap:").grid(row=4, column=0, sticky="w")
        self.chunk_overlap_var = tk.StringVar(value=str(CHUNK_OVERLAP))
        ttk.Entry(params_frame, textvariable=self.chunk_overlap_var, width=10).grid(
            row=4, column=1, sticky="w", padx=4
        )
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Chunk overlap",
                (
                    "Number of characters shared between neighboring chunks.\n\n"
                    "Overlap helps keep related lines together when they cross an artificial chunk boundary. "
                    "Moderate overlap improves recall with a small cost in index size."
                ),
            ),
        ).grid(row=4, column=3)

        # Max file size
        ttk.Label(params_frame, text="Max file size (bytes):").grid(row=5, column=0, sticky="w")
        self.max_file_bytes_var = tk.StringVar(value=str(MAX_FILE_BYTES))
        ttk.Entry(params_frame, textvariable=self.max_file_bytes_var, width=12).grid(
            row=5, column=1, sticky="w", padx=4
        )
        ttk.Button(
            params_frame,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "Max file size",
                (
                    "Files larger than this many bytes are skipped.\n\n"
                    "Useful to avoid huge bundles, logs or generated output bloating the index."
                ),
            ),
        ).grid(row=5, column=3)

        params_frame.columnconfigure(1, weight=1)

        # Collapsible file types section
        filetypes_collapsible = CollapsibleFrame(self, text="File types to index")
        filetypes_collapsible.pack(fill="x", padx=8, pady=4)

        filetypes_frame = filetypes_collapsible.body

        toolbar = ttk.Frame(filetypes_frame)
        toolbar.pack(fill="x", padx=4, pady=4)

        ttk.Button(toolbar, text="Select all", command=self._select_all_filetypes).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Clear all", command=self._clear_all_filetypes).pack(side="left", padx=4)
        ttk.Button(
            toolbar,
            text="?",
            width=2,
            command=lambda: self._show_help(
                "File types",
                (
                    "Choose which file extensions should be indexed.\n\n"
                    "Only files with these extensions are read and chunked. This keeps the index focused on "
                    "actual source, configuration and documentation files."
                ),
            ),
        ).pack(side="left", padx=4)

        groups_holder = ttk.Frame(filetypes_frame)
        groups_holder.pack(fill="x", padx=4, pady=(2, 4))

        seen: set[str] = set()
        group_names = list(COMMON_FILETYPE_GROUPS.keys())
        cols_of_groups = 3

        for i, group in enumerate(group_names):
            exts = COMMON_FILETYPE_GROUPS[group]
            row = i // cols_of_groups
            col = i % cols_of_groups

            group_frame = ttk.LabelFrame(groups_holder, text=group)
            group_frame.grid(row=row, column=col, sticky="nwe", padx=4, pady=2)

            groups_holder.columnconfigure(col, weight=1)

            inner_cols = 4
            idx = 0
            for ext in sorted(exts):
                if ext in seen:
                    continue
                seen.add(ext)

                r = idx // inner_cols
                c = idx % inner_cols
                idx += 1

                var = tk.BooleanVar(value=True)
                self._ext_vars[ext] = var
                chk = ttk.Checkbutton(group_frame, text=ext, variable=var)
                chk.grid(row=r, column=c, sticky="w", padx=2, pady=1)

        bottom_frame = ttk.Frame(self)
        bottom_frame.pack(fill="x", padx=8, pady=8)

        self.run_btn = ttk.Button(bottom_frame, text="Index", command=self.run_index)
        self.run_btn.pack(side="left")

        self.status_label = ttk.Label(bottom_frame, text="")
        self.status_label.pack(side="right")

        log_frame = ttk.LabelFrame(self, text="Index log")
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self.log_text = ScrolledText(log_frame, wrap="word", height=12)
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _show_help(self, title: str, text: str):
        messagebox.showinfo(title, text)

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

    def _select_all_filetypes(self):
        for v in self._ext_vars.values():
            v.set(True)

    def _clear_all_filetypes(self):
        for v in self._ext_vars.values():
            v.set(False)

    def run_index(self):
        if self._current_thread and self._current_thread.is_alive():
            messagebox.showinfo("Info", "Indexing already running.")
            return

        repo_root = self.repo_root_var.get().strip()
        index_base = self.index_dir_var.get().strip()
        collection_name = self.collection_var.get().strip()

        if not repo_root:
            messagebox.showerror("Error", "Repo root is required.")
            return
        if not os.path.isdir(repo_root):
            messagebox.showerror("Error", f"Repo root does not exist:\n{repo_root}")
            return
        if not index_base:
            messagebox.showerror("Error", "Index directory is required.")
            return

        index_dir = os.path.join(index_base, collection_name)

        try:
            chars = int(self.chars_per_chunk_var.get())
            overlap = int(self.chunk_overlap_var.get())
            max_bytes = int(self.max_file_bytes_var.get())
        except ValueError:
            messagebox.showerror("Error", "Numeric fields must contain integers.")
            return

        if chars <= 0:
            messagebox.showerror("Error", "Chars per chunk must be greater than zero.")
            return
        if overlap < 0:
            messagebox.showerror("Error", "Chunk overlap cannot be negative.")
            return
        if max_bytes <= 0:
            messagebox.showerror("Error", "Max file size must be greater than zero.")
            return

        selected_exts = {ext for ext, var in self._ext_vars.items() if var.get()}
        if not selected_exts:
            messagebox.showerror("Error", "Choose at least one file type.")
            return

        self.log_text.delete("1.0", "end")
        self.run_btn.config(state="disabled")
        self.status_label.config(text="Indexing...")

        def worker():
            try:
                index_repo(
                    repo_root=repo_root,
                    index_dir=index_dir,
                    collection_name=collection_name,
                    index_exts=selected_exts,
                    max_file_bytes=max_bytes,
                    chars_per_chunk=chars,
                    chunk_overlap=overlap,
                    log=self._log,
                )
                self._done(True)
            except Exception as e:
                self._log(f"Error: {e}")
                self._done(False)

        self._current_thread = threading.Thread(target=worker, daemon=True)
        self._current_thread.start()

    def _done(self, ok: bool):
        def finish():
            self.run_btn.config(state="normal")
            self.status_label.config(text="Done" if ok else "Failed")
        self.after(0, finish)
