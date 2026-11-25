from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Appointment, Doctor, Slot

DOCTORS = [
    {
        "name": "Dr. Ananya Sharma",
        "speciality": "Dermatology",
        "qualification": "MBBS, MD (Dermatology)",
        "experience_years": 8,
        "consultation_fee": 600,
        "bio": "Focused on skin health, acne care and routine dermatology consultations.",
    },
    {
        "name": "Dr. Rohan Mehta",
        "speciality": "Cardiology",
        "qualification": "MBBS, MD, DM (Cardiology)",
        "experience_years": 11,
        "consultation_fee": 900,
        "bio": "Provides preventive heart-health consultations and cardiac follow-ups.",
    },
    {
        "name": "Dr. Priya Nair",
        "speciality": "General Medicine",
        "qualification": "MBBS, MD (Internal Medicine)",
        "experience_years": 7,
        "consultation_fee": 500,
        "bio": "General physician for routine consultations and ongoing care.",
    },
    {
        "name": "Dr. Kabir Shah",
        "speciality": "Gastroenterology",
        "qualification": "MBBS, MD, DM (Gastroenterology)",
        "experience_years": 9,
        "consultation_fee": 800,
        "bio": "Specialises in digestive health consultations and follow-ups.",
    },
]

SLOT_TIMES = [(10, 0), (11, 0), (12, 0), (14, 0), (15, 0), (16, 0)]


def init_database() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.scalar(select(Doctor.id).limit(1))
        if existing:
            return

        for doctor_data in DOCTORS:
            db.add(Doctor(**doctor_data, is_active=True))
        db.flush()

        local_now = datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None, second=0, microsecond=0)
        today = local_now.date()
        doctors = list(db.scalars(select(Doctor).order_by(Doctor.id)))

        for doctor in doctors:
            for day_offset in range(0, 8):
                day = today + timedelta(days=day_offset)
                for hour, minute in SLOT_TIMES:
                    start_at = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
                    if start_at <= local_now:
                        continue
                    slot = Slot(
                        doctor_id=doctor.id,
                        start_at=start_at,
                        end_at=start_at + timedelta(minutes=30),
                        status="available",
                    )
                    db.add(slot)
        db.flush()

        # One clearly labelled demo appointment makes the cancellation flow testable.
        demo_doctor = doctors[1]
        demo_slot = db.scalar(
            select(Slot)
            .where(Slot.doctor_id == demo_doctor.id, Slot.status == "available")
            .order_by(Slot.start_at)
        )
        if demo_slot:
            demo_slot.status = "booked"
            db.add(
                Appointment(
                    doctor_id=demo_doctor.id,
                    slot_id=demo_slot.id,
                    phone_number="+919876543210",
                    status="booked",
                    created_at=local_now,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
