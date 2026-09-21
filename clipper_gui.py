#!/usr/bin/env python3
"""
Simple desktop GUI for clip.py.

Pick a video file (or paste a YouTube URL), choose "just subtitles" or "cut a
clip", and press one button. Output lands in the clips folder. Launch it by
double-clicking "Clipper GUI.bat" (or: pythonw clipper_gui.py).
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

ROOT = Path(__file__).resolve().parent
CLIP_PY = ROOT / "clip.py"
CLIPS_DIR = ROOT / "clips"
PYTHON = sys.executable  # the venv python that launched this GUI
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

MODELS = ["tiny.en", "base.en", "small.en", "medium.en", "large-v3", "small"]


class ClipperGUI:
    def __init__(self, root):
        self.root = root
        root.title("Clipper")
        root.geometry("820x660")
        root.minsize(700, 560)
        self.q = queue.Queue()
        self._build()
        self._toggle_mode()
        self.root.after(100, self._drain)

    def _build(self):
        pad = {"padx": 6, "pady": 4}
        main = ttk.Frame(self.root, padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=0)

        # --- Source ---
        ttk.Label(main, text="1.  Video file  or  YouTube URL",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        self.source = tk.StringVar()
        ttk.Entry(main, textvariable=self.source).grid(row=1, column=0, columnspan=2, sticky="we", **pad)
        ttk.Button(main, text="Browse…", command=self._browse).grid(row=1, column=2, sticky="we", **pad)

        # --- Mode ---
        ttk.Label(main, text="2.  What to do",
                  font=("Segoe UI", 10, "bold")).grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        self.mode = tk.StringVar(value="subtitle")
        ttk.Radiobutton(main, text="Just add subtitles (keep the video as-is)",
                        variable=self.mode, value="subtitle",
                        command=self._toggle_mode).grid(row=3, column=0, columnspan=3, sticky="w", **pad)
        ttk.Radiobutton(main, text="Cut a clip + make it vertical 9:16",
                        variable=self.mode, value="clip",
                        command=self._toggle_mode).grid(row=4, column=0, columnspan=3, sticky="w", **pad)

        self.ts_frame = ttk.Frame(main)
        self.ts_frame.grid(row=5, column=0, columnspan=3, sticky="we", padx=24)
        ttk.Label(self.ts_frame, text="Start").grid(row=0, column=0, **pad)
        self.start = tk.StringVar()
        ttk.Entry(self.ts_frame, textvariable=self.start, width=10).grid(row=0, column=1, **pad)
        ttk.Label(self.ts_frame, text="End").grid(row=0, column=2, **pad)
        self.end = tk.StringVar()
        ttk.Entry(self.ts_frame, textvariable=self.end, width=10).grid(row=0, column=3, **pad)
        ttk.Label(self.ts_frame, text="(mm:ss)").grid(row=0, column=4, **pad)
        ttk.Label(self.ts_frame, text="Reframe").grid(row=0, column=5, **pad)
        self.reframe = tk.StringVar(value="blur")
        ttk.Combobox(self.ts_frame, textvariable=self.reframe, values=["blur", "crop", "none"],
                     width=7, state="readonly").grid(row=0, column=6, **pad)

        # --- Options ---
        opt = ttk.LabelFrame(main, text="3.  Options", padding=10)
        opt.grid(row=6, column=0, columnspan=3, sticky="we", pady=12)
        ttk.Label(opt, text="Caption quality").grid(row=0, column=0, **pad)
        self.model = tk.StringVar(value="small.en")
        ttk.Combobox(opt, textvariable=self.model, values=MODELS, width=11,
                     state="readonly").grid(row=0, column=1, **pad)
        ttk.Label(opt, text="Font").grid(row=0, column=2, **pad)
        self.font = tk.StringVar(value="Arial Black")
        ttk.Entry(opt, textvariable=self.font, width=15).grid(row=0, column=3, **pad)
        ttk.Label(opt, text="Size").grid(row=0, column=4, **pad)
        self.fontsize = tk.StringVar(value="96")
        ttk.Entry(opt, textvariable=self.fontsize, width=5).grid(row=0, column=5, **pad)
        ttk.Label(opt, text=".en = English  ·  use 'small' or 'large-v3' for other languages",
                  foreground="#888").grid(row=1, column=0, columnspan=6, sticky="w", padx=6)

        # --- Run row ---
        self.run_btn = ttk.Button(main, text="▶   Make it", command=self._run)
        self.run_btn.grid(row=7, column=0, sticky="we", **pad)
        ttk.Button(main, text="Open clips folder",
                   command=self._open_clips).grid(row=7, column=2, sticky="we", **pad)
        self.status = tk.StringVar(value="Ready.")
        ttk.Label(main, textvariable=self.status, foreground="#0a7").grid(
            row=8, column=0, columnspan=3, sticky="w", padx=6)

        # --- Log ---
        self.log = tk.Text(main, height=14, wrap="word", state="disabled",
                           bg="#15171c", fg="#cfd2d6", relief="flat", padx=8, pady=6)
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        main.rowconfigure(9, weight=1)

    def _toggle_mode(self):
        state = "normal" if self.mode.get() == "clip" else "disabled"
        for child in self.ts_frame.winfo_children():
            try:
                child.configure(state=state)
            except tk.TclError:
                pass

    def _browse(self):
        f = filedialog.askopenfilename(
            title="Choose a video",
            filetypes=[("Video files", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v"),
                       ("All files", "*.*")])
        if f:
            self.source.set(f)

    def _open_clips(self):
        CLIPS_DIR.mkdir(exist_ok=True)
        try:
            os.startfile(CLIPS_DIR)  # Windows
        except AttributeError:
            subprocess.run(["xdg-open", str(CLIPS_DIR)])

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _run(self):
        src = self.source.get().strip().strip('"')
        if not src:
            self.status.set("Pick a video or paste a URL first.")
            return
        cmd = [PYTHON, str(CLIP_PY), src]
        if self.mode.get() == "clip":
            if not self.start.get().strip() or not self.end.get().strip():
                self.status.set("Enter a start and end time.")
                return
            cmd += [self.start.get().strip(), self.end.get().strip(),
                    "--reframe", self.reframe.get()]
        size = self.fontsize.get().strip()
        cmd += ["--model", self.model.get(), "--font", self.font.get().strip() or "Arial Black"]
        if size.isdigit():
            cmd += ["--fontsize", size]

        self.run_btn.configure(state="disabled")
        self.status.set("Working…  (first run of a new model downloads it once)")
        self._log("\n$ " + " ".join(cmd) + "\n")
        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def _worker(self, cmd):
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, cwd=str(ROOT),
                                    creationflags=CREATE_NO_WINDOW)
            for line in proc.stdout:
                self.q.put(("log", line))
            self.q.put(("done", proc.wait()))
        except Exception as e:  # noqa: BLE001
            self.q.put(("log", f"ERROR: {e}\n"))
            self.q.put(("done", 1))

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "done":
                    self.run_btn.configure(state="normal")
                    self.status.set("Done — saved in the clips folder."
                                    if payload == 0 else f"Finished with errors (exit {payload}).")
        except queue.Empty:
            pass
        self.root.after(100, self._drain)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")  # nicer on Windows; falls back if unavailable
    except tk.TclError:
        pass
    ClipperGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
