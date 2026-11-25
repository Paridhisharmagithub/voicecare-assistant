from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)


class Settings:
    elevenlabs_api_key: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    elevenlabs_tts_model: str = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5").strip()
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "").strip()
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/voicecare.db").strip()
    clinic_name: str = os.getenv("CLINIC_NAME", "VoiceCare Clinic").strip()
    timezone: str = os.getenv("APP_TIMEZONE", "Asia/Kolkata").strip()

    @property
    def voice_ready(self) -> bool:
        return all(
            [self.elevenlabs_api_key, self.elevenlabs_voice_id, self.google_api_key]
        )


settings = Settings()
