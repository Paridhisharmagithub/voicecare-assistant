from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.appointments import (
    dashboard_summary,
    get_appointments,
    get_doctor_slots,
    get_doctors,
)


def register_api_routes(app: FastAPI) -> None:
    """Add dashboard REST endpoints to Pipecat's development-runner FastAPI app."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "status": "ok",
            "service": "VoiceCare Clinic Assistant",
            "voice_configured": settings.voice_ready,
            "missing_voice_keys": [
                key
                for key, value in [
                    ("ELEVENLABS_API_KEY", settings.elevenlabs_api_key),
                    ("ELEVENLABS_VOICE_ID", settings.elevenlabs_voice_id),
                    ("GOOGLE_API_KEY", settings.google_api_key),
                ]
                if not value
            ],
            "database": "sqlite",
        }

    @app.get("/api/doctors")
    async def doctors() -> dict:
        return {"doctors": get_doctors()}

    @app.get("/api/doctors/{doctor_id}/slots")
    async def doctor_slots(
        doctor_id: int,
        date: str | None = Query(default=None, description="Optional date in YYYY-MM-DD format"),
    ) -> dict:
        try:
            slots = get_doctor_slots(doctor_id, date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"doctor_id": doctor_id, "slots": slots}

    @app.get("/api/appointments")
    async def appointments(status: str | None = Query(default=None, pattern="^(booked|cancelled)$")) -> dict:
        return {"appointments": get_appointments(status)}

    @app.get("/api/dashboard/summary")
    async def summary() -> dict:
        return dashboard_summary()
