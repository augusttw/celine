from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path

import edge_tts

from celine.config import CELINE_HOME

AUDIO_DIR = CELINE_HOME / "audio"


def clean_text_for_speech(text: str) -> str:
    """Removes code blocks, links, tables and technical syntax for natural speech."""
    # Remove code blocks ```...```
    cleaned = re.sub(r"```.*?```", " bloco de código omitido na fala. ", text, flags=re.DOTALL)
    # Remove inline code `...`
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # Convert markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # Remove raw URLs
    cleaned = re.sub(r"https?://\S+", " link ", cleaned)
    # Remove markdown headers and emphasis
    cleaned = re.sub(r"[#*_~>]+", " ", cleaned)
    # Remove markdown tables
    cleaned = re.sub(r"\|.*\|", " ", cleaned)
    # Clean emojis or strange characters if needed, keep punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


class TTSEngine:
    def __init__(
        self,
        voice: str = "pt-BR-FranciscaNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        volume: str = "+0%",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    async def synthesize(self, text: str, output_path: Path) -> bool:
        clean = clean_text_for_speech(text)
        if not clean:
            return False

        communicate = edge_tts.Communicate(
            text=clean,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
            volume=self.volume,
        )
        await communicate.save(str(output_path))
        return output_path.exists() and output_path.stat().st_size > 0

    def play_audio(self, audio_path: Path) -> None:
        if not shutil.which("mpv"):
            return
        subprocess.run(
            ["mpv", "--no-video", "--really-quiet", str(audio_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
