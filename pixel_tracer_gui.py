#!/usr/bin/env python3
"""Tracer desktop workbench: retro Macintosh UI with Morrowind colors."""

from __future__ import annotations

import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageTk

from pixel_tracer import iter_line_strokes, trace


BG = "#202522"
PANEL = "#303a32"
PANEL_2 = "#3f4a3d"
BONE = "#d8c7a0"
BONE_DARK = "#b8a681"
RUST = "#a8442a"
GOLD = "#c49b54"
INK = "#171a18"
WHITE = "#f0e7cf"
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}


class PhotoBrowser(tk.Toplevel):
    """Small image-only browser; hidden files and folders are never listed."""
    def __init__(self, parent, initial=""):
        super().__init__(parent)
        self.title("tracer — choose a photograph")
        self.configure(bg=BG)
        self.geometry("620x470")
        self.transient(parent)
        self.grab_set()
        self.result = None
        start = Path(initial).expanduser() if initial else Path.cwd()
        self.directory = tk.StringVar(value=str(start if start.is_dir() else start.parent))
        tk.Label(self, text="PHOTO BROWSER", bg=RUST, fg=WHITE, font=("DejaVu Sans Mono", 14, "bold"), anchor="w").pack(fill="x", ipady=8, padx=0)
        bar = tk.Frame(self, bg=PANEL)
        bar.pack(fill="x", padx=12, pady=12)
        tk.Entry(bar, textvariable=self.directory, bg=INK, fg=WHITE, insertbackground=GOLD, relief="flat").pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Button(bar, text="FOLDER", command=self.pick_folder, bg=PANEL_2, fg=WHITE, relief="flat").pack(side="left")
        tk.Button(bar, text="REFRESH", command=self.refresh, bg=PANEL_2, fg=WHITE, relief="flat").pack(side="left", padx=(6, 0))
        listing = tk.Frame(self, bg=BG)
        listing.pack(fill="both", expand=True, padx=12)
        self.listbox = tk.Listbox(listing, bg=INK, fg=BONE, selectbackground=RUST, selectforeground=WHITE,
                                  relief="flat", highlightthickness=0, font=("DejaVu Sans Mono", 10))
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(listing, command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<Double-Button-1>", lambda _event: self.choose())
        bottom = tk.Frame(self, bg=PANEL)
        bottom.pack(fill="x", padx=12, pady=12)
        tk.Label(bottom, text="Only image files are shown; hidden dotfiles are excluded.", bg=PANEL, fg=BONE_DARK).pack(side="left")
        tk.Button(bottom, text="CANCEL", command=self.destroy, bg=PANEL_2, fg=WHITE, relief="flat").pack(side="right", padx=(8, 0))
        tk.Button(bottom, text="CHOOSE", command=self.choose, bg=GOLD, fg=INK, relief="flat").pack(side="right")
        self.refresh()

    def pick_folder(self):
        folder = filedialog.askdirectory(parent=self, title="Choose photo folder", initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)
            self.refresh()

    def refresh(self):
        self.listbox.delete(0, tk.END)
        folder = Path(self.directory.get()).expanduser()
        try:
            files = sorted((p for p in folder.iterdir() if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in IMAGE_EXTENSIONS), key=lambda p: p.name.lower())
        except (OSError, FileNotFoundError):
            files = []
        for path in files:
            self.listbox.insert(tk.END, path.name)
        self.files = files

    def choose(self):
        selected = self.listbox.curselection()
        if selected:
            self.result = str(self.files[selected[0]])
            self.destroy()


class Tracer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("tracer — pixel print atelier")
        self.geometry("1100x760")
        self.minsize(900, 620)
        self.configure(bg=BG)
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar(value="pixel-trace.png")
        self.style = tk.StringVar(value="poster")
        self.width = tk.IntVar(value=300)
        self.colors = tk.IntVar(value=24)
        self.threshold = tk.DoubleVar(value=0.11)
        self.jitter = tk.DoubleVar(value=0.15)
        self.seed = tk.IntVar(value=7)
        self.chroma = tk.IntVar(value=0)
        self.grain = tk.DoubleVar(value=0.03)
        self.paper = tk.StringVar(value="ivory")
        self.ink = tk.StringVar(value="charcoal")
        self.underlay = tk.BooleanVar(value=False)
        self.caption = tk.StringVar()
        self.open_gimp = tk.BooleanVar(value=True)
        self.live_draw = tk.BooleanVar(value=True)
        self.draw_speed = tk.DoubleVar(value=1.0)
        self.preview_photo = None
        self.animation_job = None
        self._build()

    def _label(self, parent, text, row, column=0, **kwargs):
        tk.Label(parent, text=text, bg=parent["bg"], fg=BONE, anchor="w", **kwargs).grid(
            row=row, column=column, sticky="w", padx=8, pady=4)

    def _entry(self, parent, variable, row, column=1, width=18):
        entry = tk.Entry(parent, textvariable=variable, bg=INK, fg=WHITE, insertbackground=GOLD,
                         relief="flat", highlightthickness=1, highlightbackground=PANEL_2,
                         highlightcolor=GOLD, width=width)
        entry.grid(row=row, column=column, sticky="ew", padx=8, pady=4)
        return entry

    def _scale(self, parent, variable, row, start, end, resolution, width=150):
        scale = tk.Scale(parent, variable=variable, from_=start, to=end, resolution=resolution,
                         orient="horizontal", showvalue=True, length=width, bg=parent["bg"],
                         fg=BONE, troughcolor=INK, activebackground=GOLD, highlightthickness=0,
                         bd=0, sliderlength=18)
        scale.grid(row=row, column=1, sticky="ew", padx=8, pady=0)
        return scale

    def _option(self, parent, variable, values, row):
        menu = tk.OptionMenu(parent, variable, *values)
        menu.config(bg=INK, fg=WHITE, activebackground=GOLD, activeforeground=INK, relief="flat", highlightthickness=0)
        menu["menu"].config(bg=INK, fg=WHITE, activebackground=GOLD, activeforeground=INK)
        menu.grid(row=row, column=1, sticky="ew", padx=8, pady=4)

    def _section(self, parent, title, row):
        tk.Label(parent, text=f"  {title}  ", bg=BG, fg=GOLD, anchor="w",
                 font=("DejaVu Sans Mono", 9, "bold")).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 3))

    def _build(self):
        top = tk.Frame(self, bg=RUST, height=52)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="TRACER", bg=RUST, fg=WHITE, font=("DejaVu Sans Mono", 19, "bold")).pack(side="left", padx=18)
        tk.Label(top, text="pixel print atelier  /  morrowind palette", bg=RUST, fg="#f0c99a",
                 font=("DejaVu Sans Mono", 10)).pack(side="left", padx=8)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=14)
        controls = tk.Frame(body, bg=PANEL, width=360)
        controls.pack(side="left", fill="y", padx=(0, 12))
        controls.pack_propagate(False)
        preview = tk.Frame(body, bg=INK)
        preview.pack(side="right", fill="both", expand=True)
        self.preview = tk.Canvas(preview, bg=INK, highlightthickness=0)
        self.preview.pack(fill="both", expand=True, padx=16, pady=16)
        self.preview.create_text(340, 300, text="NO IMAGE LOADED\n\nChoose a source and render a study.", fill=BONE_DARK,
                                font=("DejaVu Sans Mono", 12), justify="center", tags="placeholder")

        self._section(controls, "SOURCE / OUTPUT", 0)
        self._label(controls, "Image", 1)
        self._entry(controls, self.input_path, 1)
        tk.Button(controls, text="BROWSE", command=self.pick_input, bg=PANEL_2, fg=WHITE, activebackground=GOLD,
                  activeforeground=INK, relief="flat", padx=7).grid(row=1, column=2, padx=5)
        self._label(controls, "Output", 2)
        self._entry(controls, self.output_path, 2)
        tk.Button(controls, text="SAVE AS", command=self.pick_output, bg=PANEL_2, fg=WHITE, activebackground=GOLD,
                  activeforeground=INK, relief="flat", padx=7).grid(row=2, column=2, padx=5)

        self._section(controls, "RENDER ENGINE", 3)
        self._label(controls, "Style", 4)
        self._option(controls, self.style, ("poster", "trace"), 4)
        self._label(controls, "Pixel width", 5)
        self._entry(controls, self.width, 5)
        self._label(controls, "Palette colors", 6)
        self._entry(controls, self.colors, 6)
        self._label(controls, "Edge threshold", 7)
        self._scale(controls, self.threshold, 7, 0.03, 0.60, 0.01)
        self._label(controls, "Hand wobble", 8)
        self._scale(controls, self.jitter, 8, 0.0, 1.5, 0.01)
        self._label(controls, "Seed", 9)
        self._entry(controls, self.seed, 9)

        self._section(controls, "PRINT CHARACTER", 10)
        self._label(controls, "RGB offset", 11)
        self._entry(controls, self.chroma, 11)
        self._label(controls, "Grain", 12)
        self._scale(controls, self.grain, 12, 0.0, 0.30, 0.01)
        self._label(controls, "Paper", 13)
        self._option(controls, self.paper, ("ivory", "white", "gray"), 13)
        self._label(controls, "Ink", 14)
        self._option(controls, self.ink, ("charcoal", "navy", "green"), 14)
        tk.Checkbutton(controls, text="Faint source underlay", variable=self.underlay, bg=PANEL, fg=BONE,
                       selectcolor=INK, activebackground=PANEL, activeforeground=WHITE).grid(row=15, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        self._label(controls, "Caption", 16)
        self._entry(controls, self.caption, 16)
        tk.Checkbutton(controls, text="Open result in GIMP", variable=self.open_gimp, bg=PANEL, fg=BONE,
                       selectcolor=INK, activebackground=PANEL, activeforeground=WHITE).grid(row=17, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        tk.Checkbutton(controls, text="Live human stroke playback", variable=self.live_draw, bg=PANEL, fg=BONE,
                       selectcolor=INK, activebackground=PANEL, activeforeground=WHITE).grid(row=18, column=0, columnspan=3, sticky="w", padx=8, pady=4)
        self._label(controls, "Draw speed", 19)
        self._scale(controls, self.draw_speed, 19, 0.25, 3.0, 0.05)
        tk.Button(controls, text="  RENDER STUDY  ", command=self.render, bg=GOLD, fg=INK,
                  activebackground=WHITE, activeforeground=INK, relief="flat",
                  font=("DejaVu Sans Mono", 11, "bold"), pady=7).grid(row=20, column=0, columnspan=3, sticky="ew", padx=12, pady=(14, 4))
        self.status = tk.Label(controls, text="Ready.", bg=PANEL, fg=BONE_DARK, anchor="w", wraplength=330)
        self.status.grid(row=21, column=0, columnspan=3, sticky="ew", padx=12, pady=5)
        controls.columnconfigure(1, weight=1)

    def pick_input(self):
        browser = PhotoBrowser(self, self.input_path.get())
        self.wait_window(browser)
        if browser.result:
            source = Path(browser.result)
            self.input_path.set(str(source))
            self.output_path.set(str(source.with_name(source.stem + "-tracer.png")))
            self.status.config(text=f"Loaded {source.name}")

    def pick_output(self):
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")], initialfile=Path(self.output_path.get()).name)
        if path:
            self.output_path.set(path)

    def render(self):
        if not self.input_path.get():
            messagebox.showwarning("No source", "Choose an image first.")
            return
        if self.animation_job is not None:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        if self.live_draw.get():
            self.animate_lines()
        else:
            self._render_final()

    def animate_lines(self):
        try:
            strokes = list(iter_line_strokes(Path(self.input_path.get()), self.width.get(), self.colors.get(),
                                              self.threshold.get(), self.jitter.get(), self.seed.get()))
        except Exception as exc:
            messagebox.showerror("Animation failed", str(exc))
            return
        self.preview.delete("all")
        self.preview.update_idletasks()
        canvas_w = max(100, self.preview.winfo_width())
        canvas_h = max(100, self.preview.winfo_height())
        source = Image.open(self.input_path.get())
        source_h = max(16, round(self.width.get() * source.height / source.width))
        scale = min((canvas_w - 30) / self.width.get(), (canvas_h - 30) / source_h)
        ox = (canvas_w - self.width.get() * scale) / 2
        oy = (canvas_h - source_h * scale) / 2
        self.preview.create_rectangle(0, 0, canvas_w, canvas_h, fill=INK, outline="", tags="animation")
        self.status.config(text=f"Drawing {len(strokes)} human-like strokes…")
        state = {"index": 0}

        def step():
            index = state["index"]
            if index >= len(strokes):
                self.animation_job = None
                self._render_final()
                return
            points = strokes[index]
            coords = []
            for x, y in points:
                coords.extend((ox + x * scale, oy + y * scale))
            self.preview.create_line(*coords, fill=BONE, width=max(1, round(scale * 0.65)),
                                     capstyle=tk.ROUND, joinstyle=tk.ROUND, tags="animation")
            state["index"] += 1
            distance = max(1, len(points))
            delay = max(8, int((18 + distance * 7) / self.draw_speed.get()))
            self.animation_job = self.after(delay, step)

        step()

    def _render_final(self):
        try:
            trace(Path(self.input_path.get()), Path(self.output_path.get()), self.width.get(), self.colors.get(),
                  self.threshold.get(), self.jitter.get(), self.seed.get(), self.underlay.get(),
                  style=self.style.get(), caption=self.caption.get(), chroma=self.chroma.get(),
                  grain=self.grain.get(), paper=self.paper.get(), ink=self.ink.get())
            self._show_preview(Path(self.output_path.get()))
            self.status.config(text=f"Rendered {Path(self.output_path.get()).name}")
            if self.open_gimp.get():
                subprocess.Popen(["gimp", self.output_path.get()])
        except Exception as exc:
            self.status.config(text=f"Render failed: {exc}")
            messagebox.showerror("Render failed", str(exc))

    def _show_preview(self, path: Path):
        image = Image.open(path)
        image.thumbnail((max(100, self.preview.winfo_width() - 20), max(100, self.preview.winfo_height() - 20)), Image.Resampling.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview.delete("all")
        self.preview.create_image(self.preview.winfo_width() // 2, self.preview.winfo_height() // 2,
                                 image=self.preview_photo, anchor="center")


if __name__ == "__main__":
    Tracer().mainloop()
