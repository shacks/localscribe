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
from tkinter import messagebox

from . import config, pipeline
from .recorder import Recorder


class App:
    def __init__(self):
        self.cfg = config.load()
        self.recorder = Recorder(self.cfg["sample_rate"])
        self.jobs = queue.Queue()
        self.started_at = None

        self.root = tk.Tk()
        self.root.title("LocalScribe")
        self.root.geometry("420x380")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.button = tk.Button(
            self.root, text="Start Recording", font=("Segoe UI", 18, "bold"),
            bg="#2e7d32", fg="white", height=3, command=self.toggle,
        )
        self.button.pack(fill="x", padx=16, pady=16)

        self.status = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status, font=("Segoe UI", 10)).pack(pady=(0, 8))

        tk.Label(self.root, text="Finished transcripts (double-click to open):",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=16)
        self.listbox = tk.Listbox(self.root, font=("Segoe UI", 9))
        self.listbox.pack(fill="both", expand=True, padx=16, pady=(2, 8))
        self.listbox.bind("<Double-Button-1>", self.open_selected)

        tk.Button(self.root, text="Open transcripts folder",
                  command=lambda: os.startfile(self.cfg["output_dir"])).pack(pady=(0, 12))

        threading.Thread(target=self.worker, daemon=True).start()

    def toggle(self):
        if not self.recorder.recording:
            self.started_at = datetime.now()
            wav = Path(self.cfg["audio_dir"]) / f"{self.started_at.strftime('%Y-%m-%d %H-%M-%S')}.wav"
            try:
                self.recorder.start(str(wav))
            except Exception as e:
                messagebox.showerror("Microphone error", str(e))
                return
            self.button.config(text="Stop Recording", bg="#c62828")
            self.status.set("Recording...")
        else:
            wav = self.recorder.stop()
            self.jobs.put((wav, self.started_at))
            self.button.config(text="Start Recording", bg="#2e7d32")
            self.status.set("Queued for transcription")

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
