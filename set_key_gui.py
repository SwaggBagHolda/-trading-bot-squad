#!/usr/bin/env python3
"""set_key_gui.py — GUI popup to safely add ANTHROPIC_API_KEY to .env"""
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

ENV = Path.home() / "trading-bot-squad" / ".env"

def save_key():
    key = entry.get().strip()
    if not key:
        messagebox.showerror("Error", "Key cannot be empty.")
        return
    if not key.startswith("sk-ant-"):
        if not messagebox.askyesno("Warning", "Key doesn't look like an Anthropic key (should start with sk-ant-). Save anyway?"):
            return

    existing = ENV.read_text() if ENV.exists() else ""
    lines = [l for l in existing.splitlines() if not l.startswith("ANTHROPIC_API_KEY=")]
    lines.append(f"ANTHROPIC_API_KEY={key}")
    ENV.write_text("\n".join(lines) + "\n")

    messagebox.showinfo("Saved", f"ANTHROPIC_API_KEY saved.\nFirst 12: {key[:12]}...\nLength: {len(key)}")
    root.destroy()

root = tk.Tk()
root.title("Set Anthropic API Key")
root.resizable(False, False)
root.eval("tk::PlaceWindow . center")

tk.Label(root, text="ANTHROPIC_API_KEY", font=("Helvetica", 13, "bold"), pady=10).pack()
tk.Label(root, text="Paste your key below (input is masked):", font=("Helvetica", 11)).pack()

entry = tk.Entry(root, show="*", width=55, font=("Helvetica", 11))
entry.pack(padx=20, pady=8)
entry.focus()

tk.Button(root, text="Save to .env", command=save_key,
          bg="#2ecc71", fg="white", font=("Helvetica", 12, "bold"),
          padx=10, pady=6).pack(pady=(0, 15))

root.bind("<Return>", lambda e: save_key())
root.mainloop()
