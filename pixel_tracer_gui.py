#!/usr/bin/env python3
"""Tiny desktop front-end for pixel_tracer.py (Tkinter, no extra dependency)."""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from pixel_tracer import trace


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Pixel Tracer — GIMP / MS Paint mode")
        self.geometry("520x300")
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar(value="pixel-trace.png")
        self.width = tk.IntVar(value=160)
        self.threshold = tk.DoubleVar(value=0.19)
        self.jitter = tk.DoubleVar(value=0.55)
        self.underlay = tk.BooleanVar(value=False)
        self.style = tk.StringVar(value="poster")
        self.caption = tk.StringVar()
        self._build()

    def _build(self):
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="PIXEL TRACER", font=("TkDefaultFont", 16, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="Low-res, distressed character posters for GIMP").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 16))
        ttk.Label(frame, text="Image").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.input_path, width=45).grid(row=2, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.pick_input).grid(row=2, column=2, padx=(8, 0))
        ttk.Label(frame, text="Pixel width").grid(row=3, column=0, sticky="w", pady=(12, 0))
        ttk.Spinbox(frame, from_=48, to=640, textvariable=self.width, width=8).grid(row=3, column=1, sticky="w", pady=(12, 0))
        ttk.Label(frame, text="Wobble").grid(row=4, column=0, sticky="w")
        ttk.Scale(frame, from_=0, to=1.5, variable=self.jitter, orient="horizontal").grid(row=4, column=1, sticky="ew")
        ttk.Label(frame, text="Edge threshold").grid(row=5, column=0, sticky="w")
        ttk.Scale(frame, from_=0.05, to=0.6, variable=self.threshold, orient="horizontal").grid(row=5, column=1, sticky="ew")
        ttk.Checkbutton(frame, text="Keep a faint image underlay", variable=self.underlay).grid(row=6, column=1, sticky="w", pady=8)
        ttk.Label(frame, text="Style").grid(row=7, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=self.style, values=("poster", "trace"), state="readonly", width=12).grid(row=7, column=1, sticky="w")
        ttk.Label(frame, text="Caption").grid(row=8, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.caption).grid(row=8, column=1, sticky="ew")
        ttk.Button(frame, text="Trace and save PNG", command=self.run).grid(row=9, column=1, sticky="e", pady=(10, 0))
        frame.columnconfigure(1, weight=1)

    def pick_input(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")])
        if path:
            self.input_path.set(path)
            self.output_path.set(str(Path(path).with_name(Path(path).stem + "-pixel-trace.png")))

    def run(self):
        if not self.input_path.get():
            messagebox.showwarning("Choose an image", "Pick an image to trace first.")
            return
        try:
            trace(Path(self.input_path.get()), Path(self.output_path.get()), self.width.get(), 12,
                  self.threshold.get(), self.jitter.get(), 7, self.underlay.get(),
                  style=self.style.get(), caption=self.caption.get())
            messagebox.showinfo("Done", f"Saved {self.output_path.get()}\nOpen it in GIMP to continue editing.")
        except Exception as exc:
            messagebox.showerror("Trace failed", str(exc))


if __name__ == "__main__":
    App().mainloop()
