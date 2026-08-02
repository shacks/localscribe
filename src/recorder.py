"""Microphone recording to WAV (16 kHz mono), start/stop from the GUI thread."""
import queue
import threading

import numpy as np
import sounddevice as sd
import soundfile as sf


class Recorder:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self._stream = None
        self._writer = None
        self._q = None
        self._stop_flag = None
        self.path = None
        self.level = 0.0  # latest mic peak (0.0-1.0), polled by the GUI meter

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self, path: str):
        if self._stream is not None:
            raise RuntimeError("already recording")
        self.path = path
        self._q = queue.Queue()
        self._stop_flag = threading.Event()

        def callback(indata, frames, time_info, status):
            self.level = float(np.abs(indata).max()) / 32768.0
            self._q.put(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="int16", callback=callback
        )
        self._writer = threading.Thread(target=self._write_loop, daemon=True)
        self._stream.start()
        self._writer.start()

    def _write_loop(self):
        with sf.SoundFile(
            self.path, mode="w", samplerate=self.sample_rate, channels=1, subtype="PCM_16"
        ) as f:
            while not (self._stop_flag.is_set() and self._q.empty()):
                try:
                    f.write(self._q.get(timeout=0.2))
                except queue.Empty:
                    continue

    def stop(self) -> str:
        if self._stream is None:
            raise RuntimeError("not recording")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        self._stop_flag.set()
        self._writer.join(timeout=10)
        self._writer = None
        self.level = 0.0
        return self.path
