from __future__ import annotations

import asyncio
import os
import queue
import shutil
import threading
import time
from pathlib import Path

from celine.config import CELINE_HOME, VoiceConfig
from celine.voice.tts import AUDIO_DIR, TTSEngine


class VoiceManager:
    def __init__(self, config: VoiceConfig) -> None:
        self.config = config
        self.enabled = config.enabled
        self.engine = TTSEngine(
            voice=config.voice,
            rate=config.rate,
            pitch=config.pitch,
            volume=config.volume,
        )
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._running = False
        self._thread: threading.Thread | None = None
        self._check_environment()
        self._start_worker()

    def _check_environment(self) -> bool:
        return shutil.which("mpv") is not None

    def _start_worker(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _worker_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                text = self._queue.get(timeout=0.5)
                if text is None:
                    break

                if not self.enabled:
                    self._queue.task_done()
                    continue

                output_file = AUDIO_DIR / f"celine_{int(time.time() * 1000)}.mp3"
                try:
                    success = loop.run_until_complete(self.engine.synthesize(text, output_file))
                    if success:
                        self.engine.play_audio(output_file)
                        # Keep latest audio symlink/copy
                        latest = AUDIO_DIR / "celine-latest.mp3"
                        if output_file.exists():
                            output_file.replace(latest)
                except Exception:
                    pass
                finally:
                    self._queue.task_done()

            except queue.Empty:
                continue

    def speak(self, text: str) -> None:
        if not self.enabled:
            return
        if not self._check_environment():
            return
        if text and text.strip():
            self._queue.put(text)

    def toggle(self, enabled: bool | None = None) -> bool:
        if enabled is None:
            self.enabled = not self.enabled
        else:
            self.enabled = enabled
        self.config.enabled = self.enabled
        return self.enabled

    def set_voice(self, voice_name: str) -> None:
        self.config.voice = voice_name
        self.engine.voice = voice_name

    def set_rate(self, rate: str) -> None:
        self.config.rate = rate
        self.engine.rate = rate

    def shutdown(self) -> None:
        self._running = False
        self._queue.put(None)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
