"""Run a small isolated database smoke test without touching the demo database."""
from __future__ import annotations

import os
import uuid
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

smoke_name = f"smoke_{uuid.uuid4().hex[:8]}.sqlite"
os.environ["DATABASE_URL"] = f"sqlite:///./data/{smoke_name}"

from app.seed import init_database  # noqa: E402
from app.services.appointments import (  # noqa: E402
    book_slot,
    cancel_appointment_for_phone,
    get_active_appointments_for_phone,
    get_doctors,
    search_availability,
)
from app.services.phone import normalize_indian_phone  # noqa: E402


def main() -> None:
    database_path = BACKEND_DIR / "data" / smoke_name
    try:
        init_database()
        assert len(get_doctors()) == 4, "Expected four seeded doctors"
        assert normalize_indian_phone("nine eight seven six five four three two one zero") == "+919876543210"

        availability = search_availability(speciality="Dermatology")
        assert availability["count"] > 0, "Expected mock dermatology slots"
        slot_id = availability["available_slots"][0]["slot_id"]

        booked = book_slot(slot_id=slot_id, phone_number="+919123456789")
        assert booked["success"], booked
        owned = get_active_appointments_for_phone("+919123456789")
        assert any(item["appointment_id"] == booked["appointment_id"] for item in owned)

        cancelled = cancel_appointment_for_phone(
            appointment_id=booked["appointment_id"],
            phone_number="+919123456789",
        )
        assert cancelled["success"], cancelled

        rebooked = book_slot(slot_id=slot_id, phone_number="+919123456789")
        assert rebooked["success"], "A cancelled slot should become available again"
        print("PASS: seed, phone normalization, availability, booking, cancellation and rebooking")
    finally:
        if database_path.exists():
            database_path.unlink()


if __name__ == "__main__":
    main()
