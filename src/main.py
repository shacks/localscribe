"""LocalScribe GUI: one button, background processing queue, quiet flat styling.

Recording is instant; transcription + redaction happen in a worker thread so
the next consult can be recorded while the previous one processes.
"""
import os
import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

from . import __version__, config, pipeline
from .recorder import Recorder

BG = "#fafafa"
TEXT = "#212121"
MUTED = "#8a8a8a"
GREEN = "#2e7d32"
GREEN_DARK = "#1b5e20"
RED = "#b71c1c"
RED_TINT = "#fdecea"
METER_BG = "#ececec"
FONT = "Segoe UI"


def flat(btn: tk.Button, **kw):
    btn.config(relief="flat", bd=0, cursor="hand2", **kw)
    return btn


class App:
    def __init__(self):
        self.cfg = config.load()
        self.recorder = Recorder(self.cfg["sample_rate"])
        self.jobs = queue.Queue()
        self.started_at = None
        self.settings_open = False

        self.root = tk.Tk()
        self.root.title("LocalScribe")
        self.root.geometry("400x520")
        self.root.minsize(360, 440)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 10))
        tk.Label(header, text="LocalScribe", font=(FONT, 13, "bold"),
                 bg=BG, fg=TEXT).pack(side="left")
        tk.Label(header, text=f"v{__version__}", font=(FONT, 9),
                 bg=BG, fg=MUTED).pack(side="right")

        # main control
        self.button = flat(
            tk.Button(self.root, command=self.toggle),
            text="●  Start recording", font=(FONT, 13, "bold"),
            bg=GREEN, fg="white", activebackground=GREEN_DARK,
            activeforeground="white", pady=14,
        )
        self.button.pack(fill="x", padx=20)

        # recording row (hidden unless recording): blinking timer + level meter
        self.rec_row = tk.Frame(self.root, bg=BG)
        self.rec_var = tk.StringVar(value="")
        tk.Label(self.rec_row, textvariable=self.rec_var, font=("Consolas", 11, "bold"),
                 bg=BG, fg=RED, width=9, anchor="w").pack(side="left")
        self.meter = tk.Canvas(self.rec_row, height=8, bg=METER_BG, highlightthickness=0)
        self.meter.pack(side="left", fill="x", expand=True, pady=2)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, font=(FONT, 9),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=20, pady=(8, 12))

        # transcript list
        tk.Label(self.root, text="RECENT TRANSCRIPTS", font=(FONT, 8, "bold"),
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", padx=20)
        self.listbox = tk.Listbox(
            self.root, font=(FONT, 9), bd=0, highlightthickness=0,
            bg="white", fg=TEXT, selectbackground="#e3f2fd",
            selectforeground=TEXT, activestyle="none",
        )
        self.listbox.pack(fill="both", expand=True, padx=20, pady=(4, 10))
        self.listbox.bind("<Double-Button-1>", self.open_selected)

        # footer buttons
        self.btn_row = tk.Frame(self.root, bg=BG)
        self.btn_row.pack(fill="x", padx=20, pady=(0, 14))
        flat(tk.Button(self.btn_row, text="Open folder", font=(FONT, 9),
                       bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
                       command=lambda: os.startfile(self.cfg["output_dir"]))
             ).pack(side="left")
        flat(tk.Button(self.btn_row, text="Settings", font=(FONT, 9),
                       bg=BG, fg=MUTED, activebackground=BG, activeforeground=TEXT,
                       command=self.toggle_settings)).pack(side="right")

        # settings panel (hidden by default)
        self.settings = tk.Frame(self.root, bg="white")
        self.delete_audio_var = tk.BooleanVar(value=self.cfg["delete_audio_after_success"])
        tk.Checkbutton(
            self.settings, text="Delete audio after successful transcript",
            variable=self.delete_audio_var, font=(FONT, 9), bg="white", fg=TEXT,
            activebackground="white", command=self.save_settings,
        ).pack(anchor="w", padx=10, pady=(8, 2))
        row = tk.Frame(self.settings, bg="white")
        row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Label(row, text="Save to:", font=(FONT, 9), bg="white", fg=TEXT).pack(side="left")
        self.outdir_var = tk.StringVar(value=self.cfg["output_dir"])
        tk.Label(row, textvariable=self.outdir_var, font=(FONT, 8), bg="white",
                 fg=MUTED, anchor="w").pack(side="left", fill="x", expand=True, padx=6)
        flat(tk.Button(row, text="Change", font=(FONT, 9), bg="#eeeeee", fg=TEXT,
                       activebackground="#e0e0e0", padx=8,
                       command=self.choose_output_dir)).pack(side="right")

        threading.Thread(target=self.worker, daemon=True).start()

    # -- settings --------------------------------------------------------
    def toggle_settings(self):
        if self.settings_open:
            self.settings.pack_forget()
        else:
            self.settings.pack(fill="x", padx=20, pady=(0, 14), after=self.btn_row)
        self.settings_open = not self.settings_open

    def save_settings(self):
        self.cfg["delete_audio_after_success"] = self.delete_audio_var.get()
        config.save(self.cfg)

    def choose_output_dir(self):
        chosen = filedialog.askdirectory(
            initialdir=self.cfg["output_dir"], title="Choose transcripts folder"
        )
        if not chosen:
            return
        self.cfg["output_dir"] = chosen
        Path(chosen).mkdir(parents=True, exist_ok=True)
        self.outdir_var.set(chosen)
        config.save(self.cfg)

    # -- recording -------------------------------------------------------
    def toggle(self):
        if not self.recorder.recording:
            self.started_at = datetime.now()
            wav = Path(self.cfg["audio_dir"]) / f"{self.started_at.strftime('%Y-%m-%d %H-%M-%S')}.wav"
            try:
                self.recorder.start(str(wav))
            except Exception as e:
                messagebox.showerror("Microphone error", str(e))
                return
            # discreet while recording: small neutral stop, meter carries the signal
            self.button.config(text="Stop recording", font=(FONT, 10),
                               bg=RED_TINT, fg=RED, activebackground="#f7d9d5",
                               activeforeground=RED, pady=6)
            self.rec_row.pack(fill="x", padx=20, pady=(8, 0), after=self.button)
            self.status.set("Recording")
            self._tick_n = 0
            self._blink = False
            self._disp_level = 0.0
            self._meter_tick()
        else:
            wav = self.recorder.stop()
            self.jobs.put((wav, self.started_at))
            self.button.config(text="●  Start recording", font=(FONT, 13, "bold"),
                               bg=GREEN, fg="white", activebackground=GREEN_DARK,
                               activeforeground="white", pady=14)
            self.rec_row.pack_forget()
            self.status.set("Queued for transcription")

    def _meter_tick(self):
        if not self.recorder.recording:
            return
        # peak with decay so the bar falls smoothly; sqrt scaling for visibility
        self._disp_level = max(self.recorder.level, self._disp_level * 0.75)
        width = max(self.meter.winfo_width(), 1)
        frac = min(1.0, self._disp_level ** 0.5)
        color = GREEN if self._disp_level < 0.6 else (
            "#f9a825" if self._disp_level < 0.9 else RED)
        self.meter.delete("all")
        self.meter.create_rectangle(0, 0, int(width * frac), 8, fill=color, width=0)

        self._tick_n += 1
        if self._tick_n % 6 == 0:  # blink REC dot about twice a second
            self._blink = not self._blink
        elapsed = int((datetime.now() - self.started_at).total_seconds())
        mins, secs = divmod(elapsed, 60)
        self.rec_var.set(f"{'●' if self._blink else ' '} {mins:02d}:{secs:02d}")
        self.root.after(80, self._meter_tick)

    # -- pipeline --------------------------------------------------------
    def worker(self):
        while True:
            wav, started_at = self.jobs.get()
            try:
                out = pipeline.process(wav, started_at, self.cfg, self.set_status)
                self.root.after(0, self.done, out)
            except Exception as e:
                stamp = started_at.strftime("%H:%M")
                self.root.after(0, self.set_status,
                                f"FAILED ({stamp}): {e} - audio kept at {wav}")

    def set_status(self, msg: str):
        self.root.after(0, self.status.set, msg)

    def done(self, out_path: str):
        self.status.set("Ready")
        self.listbox.insert(0, Path(out_path).name)
        if self.cfg["open_for_review"]:
            subprocess.Popen(["notepad.exe", out_path])

    def open_selected(self, _event):
        sel = self.listbox.curselection()
        if sel:
            subprocess.Popen(
                ["notepad.exe", str(Path(self.cfg["output_dir"]) / self.listbox.get(sel[0]))]
            )

    def on_close(self):
        if self.recorder.recording:
            if not messagebox.askyesno("Recording in progress",
                                       "Still recording. Stop and discard this recording?"):
                return
            self.recorder.stop()
        if not self.jobs.empty():
            if not messagebox.askyesno("Processing in progress",
                                       "Transcripts are still processing and will be lost. Quit anyway?"):
                return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
