"""LocalScribe GUI: one big Start/Stop button, background processing queue.

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


class App:
    def __init__(self):
        self.cfg = config.load()
        self.recorder = Recorder(self.cfg["sample_rate"])
        self.jobs = queue.Queue()
        self.started_at = None

        self.root = tk.Tk()
        self.root.title(f"LocalScribe v{__version__}")
        self.root.geometry("460x530")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.button = tk.Button(
            self.root, text="Start Recording", font=("Segoe UI", 18, "bold"),
            bg="#2e7d32", fg="white", height=3, command=self.toggle,
        )
        self.button.pack(fill="x", padx=16, pady=(16, 8))

        # live recording indicator: blinking REC + elapsed time + mic level meter
        meter_row = tk.Frame(self.root)
        meter_row.pack(fill="x", padx=16, pady=(0, 8))
        self.rec_var = tk.StringVar(value="")
        tk.Label(meter_row, textvariable=self.rec_var, font=("Consolas", 12, "bold"),
                 fg="#c62828", width=9, anchor="w").pack(side="left")
        self.meter = tk.Canvas(meter_row, height=16, bg="#e0e0e0", highlightthickness=0)
        self.meter.pack(side="left", fill="x", expand=True)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, font=("Segoe UI", 10)).pack(pady=(0, 8))

        tk.Label(self.root, text="Finished transcripts (double-click to open):",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        self.listbox = tk.Listbox(self.root, font=("Segoe UI", 9))
        self.listbox.pack(fill="both", expand=True, padx=16, pady=(2, 8))
        self.listbox.bind("<Double-Button-1>", self.open_selected)

        tk.Button(self.root, text="Open transcripts folder",
                  command=lambda: os.startfile(self.cfg["output_dir"])).pack(pady=(0, 8))

        settings = tk.LabelFrame(self.root, text="Settings", font=("Segoe UI", 9))
        settings.pack(fill="x", padx=16, pady=(0, 12))

        self.delete_audio_var = tk.BooleanVar(value=self.cfg["delete_audio_after_success"])
        tk.Checkbutton(
            settings, text="Delete audio after successful transcript",
            variable=self.delete_audio_var, font=("Segoe UI", 9),
            command=self.save_settings,
        ).pack(anchor="w", padx=8, pady=(4, 0))

        row = tk.Frame(settings)
        row.pack(fill="x", padx=8, pady=(2, 8))
        tk.Label(row, text="Save transcripts to:", font=("Segoe UI", 9)).pack(side="left")
        self.outdir_var = tk.StringVar(value=self.cfg["output_dir"])
        tk.Label(row, textvariable=self.outdir_var, font=("Segoe UI", 8),
                 fg="#555", anchor="w").pack(side="left", fill="x", expand=True, padx=6)
        tk.Button(row, text="Change...", command=self.choose_output_dir).pack(side="right")

        threading.Thread(target=self.worker, daemon=True).start()

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

    def toggle(self):
        if not self.recorder.recording:
            self.started_at = datetime.now()
            wav = Path(self.cfg["audio_dir"]) / f"{self.started_at.strftime('%Y-%m-%d %H-%M-%S')}.wav"
            try:
                self.recorder.start(str(wav))
            except Exception as e:
                messagebox.showerror("Microphone error", str(e))
                return
            # while recording the button goes small and discreet; the meter is the focus
            self.button.config(text="Stop recording", font=("Segoe UI", 10),
                               height=1, bg="#f2f2f2", fg="#c62828",
                               activebackground="#e0e0e0", activeforeground="#c62828")
            self.status.set("Recording")
            self._tick_n = 0
            self._blink = False
            self._disp_level = 0.0
            self._meter_tick()
        else:
            wav = self.recorder.stop()
            self.jobs.put((wav, self.started_at))
            self.button.config(text="Start Recording", font=("Segoe UI", 18, "bold"),
                               height=3, bg="#2e7d32", fg="white",
                               activebackground="#1b5e20", activeforeground="white")
            self.rec_var.set("")
            self.meter.delete("all")
            self.status.set("Queued for transcription")

    def _meter_tick(self):
        if not self.recorder.recording:
            return
        # peak with decay so the bar falls smoothly; sqrt scaling for visibility
        self._disp_level = max(self.recorder.level, self._disp_level * 0.75)
        width = max(self.meter.winfo_width(), 1)
        frac = min(1.0, self._disp_level ** 0.5)
        color = "#2e7d32" if self._disp_level < 0.6 else (
            "#f9a825" if self._disp_level < 0.9 else "#c62828")
        self.meter.delete("all")
        self.meter.create_rectangle(0, 0, int(width * frac), 16, fill=color, width=0)

        self._tick_n += 1
        if self._tick_n % 6 == 0:  # blink REC dot about twice a second
            self._blink = not self._blink
        elapsed = int((datetime.now() - self.started_at).total_seconds())
        mins, secs = divmod(elapsed, 60)
        self.rec_var.set(f"{'●' if self._blink else ' '} {mins:02d}:{secs:02d}")
        self.root.after(80, self._meter_tick)

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
