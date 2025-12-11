import json
import textwrap
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText


DEFAULT_SUMMARIZER_PROMPT = textwrap.dedent("""
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
    - Remove obvious noise.
    - Length target: a few sentences or a short paragraph.
    - Do not invent new information.
""").strip()


DEFAULT_CHAT_PROMPT = textwrap.dedent("""
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

    Answer directly in terms of the bug.
    Separate clearly:
    - Facts that are directly supported by the snippets.
    - Hypotheses or guesses that go beyond the snippets.
""").strip()


class PromptsTab(ttk.Frame):
    """
    Tab for viewing and editing the summarizer and chat prompt templates.

    QueryTab is expected to read from:
        prompts_tab.summarizer_text
        prompts_tab.chat_prompt_text
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._build_prompts_tab()
        self._set_default_prompts()

    def _build_prompts_tab(self):
        ctl_frame = ttk.Frame(self)
        ctl_frame.pack(fill="x", padx=8, pady=4)

        load_prompts_btn = ttk.Button(
            ctl_frame,
            text="Load prompts from file",
            command=self.load_prompts_from_file,
        )
        load_prompts_btn.pack(side="left", padx=4)

        save_prompts_btn = ttk.Button(
            ctl_frame,
            text="Save prompts to file",
            command=self.save_prompts_to_file,
        )
        save_prompts_btn.pack(side="left", padx=4)

        # Summarizer prompt
        sum_frame = ttk.LabelFrame(self, text="Summarizer prompt template")
        sum_frame.pack(fill="both", expand=True, padx=8, pady=4)

        sum_label = ttk.Label(
            sum_frame,
            text="Use <<BUG_TEXT>> where the full bug description should go.",
        )
        sum_label.pack(anchor="w", padx=4, pady=2)

        self.summarizer_text = ScrolledText(sum_frame, wrap="word", height=10)
        self.summarizer_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Chat prompt
        chat_frame = ttk.LabelFrame(self, text="Answer prompt template")
        chat_frame.pack(fill="both", expand=True, padx=8, pady=4)

        chat_label = ttk.Label(
            chat_frame,
            text="Use <<BUG_TEXT>> for bug description and <<SNIPPETS>> for retrieved code snippets.",
        )
        chat_label.pack(anchor="w", padx=4, pady=2)

        self.chat_prompt_text = ScrolledText(chat_frame, wrap="word", height=12)
        self.chat_prompt_text.pack(fill="both", expand=True, padx=4, pady=4)

    def _set_default_prompts(self):
        self.summarizer_text.delete("1.0", "end")
        self.summarizer_text.insert("1.0", DEFAULT_SUMMARIZER_PROMPT)

        self.chat_prompt_text.delete("1.0", "end")
        self.chat_prompt_text.insert("1.0", DEFAULT_CHAT_PROMPT)

    def load_prompts_from_file(self):
        path = filedialog.askopenfilename(
            title="Load prompts",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load prompts:\n{e}")
            return

        summarizer = data.get("summarizer")
        chat = data.get("chat")

        if not isinstance(summarizer, str) or not isinstance(chat, str):
            messagebox.showerror(
                "Error",
                "Prompt file must be JSON with 'summarizer' and 'chat' string fields.",
            )
            return

        self.summarizer_text.delete("1.0", "end")
        self.summarizer_text.insert("1.0", summarizer)

        self.chat_prompt_text.delete("1.0", "end")
        self.chat_prompt_text.insert("1.0", chat)

        messagebox.showinfo("Loaded", f"Prompts loaded from:\n{path}")

    def save_prompts_to_file(self):
        summarizer = self.summarizer_text.get("1.0", "end-1c")
        chat = self.chat_prompt_text.get("1.0", "end-1c")

        data = {
            "summarizer": summarizer,
            "chat": chat,
        }

        path = filedialog.asksaveasfilename(
            title="Save prompts",
            defaultextension=".json",
            initialfile="prompts.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save prompts:\n{e}")
            return

        messagebox.showinfo("Saved", f"Prompts saved to:\n{path}")
