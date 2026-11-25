from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.config import settings
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import Appointment, Doctor, Slot
from app.services.phone import mask_phone


def _clinic_now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Please use a date in YYYY-MM-DD format.") from exc


def _format_time(value: datetime) -> str:
    return value.strftime("%I:%M %p").lstrip("0")


def search_availability(
    *,
    doctor_name: str | None = None,
    speciality: str | None = None,
    date_text: str | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    requested_date = _parse_date(date_text)
    now = _clinic_now().replace(second=0, microsecond=0)
    db = SessionLocal()
    try:
        query = (
            select(Slot, Doctor)
            .join(Doctor, Doctor.id == Slot.doctor_id)
            .where(Slot.status == "available", Doctor.is_active.is_(True), Slot.start_at >= now)
        )
        if requested_date:
            start = datetime.combine(requested_date, time.min)
            end = start + timedelta(days=1)
            query = query.where(Slot.start_at >= start, Slot.start_at < end)
        else:
            query = query.where(Slot.start_at < now + timedelta(days=8))
        if doctor_name:
            query = query.where(Doctor.name.ilike(f"%{doctor_name.strip()}%"))
        if speciality:
            query = query.where(Doctor.speciality.ilike(f"%{speciality.strip()}%"))

        rows = db.execute(query.order_by(Slot.start_at, Doctor.name).limit(limit)).all()
        slots = []
        seen_doctors = {}
        for slot, doctor in rows:
            slots.append(
                {
                    "slot_id": slot.id,
                    "doctor_id": doctor.id,
                    "doctor_name": doctor.name,
                    "speciality": doctor.speciality,
                    "date": slot.start_at.date().isoformat(),
                    "time": _format_time(slot.start_at),
                    "start_at": slot.start_at.isoformat(),
                    "consultation_fee": doctor.consultation_fee,
                }
            )
            seen_doctors[doctor.id] = doctor.name
        return {
            "success": True,
            "count": len(slots),
            "doctors_found": list(seen_doctors.values()),
            "available_slots": slots,
            "message": "Available slots retrieved." if slots else "No matching slots are available in the requested period.",
        }
    finally:
        db.close()


def get_slot(slot_id: int) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        row = db.execute(
            select(Slot, Doctor).join(Doctor, Doctor.id == Slot.doctor_id).where(Slot.id == slot_id)
        ).first()
        if not row:
            return None
        slot, doctor = row
        return {
            "slot_id": slot.id,
            "doctor_id": doctor.id,
            "doctor_name": doctor.name,
            "speciality": doctor.speciality,
            "date": slot.start_at.date().isoformat(),
            "time": _format_time(slot.start_at),
            "start_at": slot.start_at.isoformat(),
            "status": slot.status,
            "consultation_fee": doctor.consultation_fee,
        }
    finally:
        db.close()


def book_slot(*, slot_id: int, phone_number: str) -> dict[str, Any]:
    """Atomically reserve an available slot and create its appointment."""
    db = SessionLocal()
    try:
        with db.begin():
            update_result = db.execute(
                update(Slot)
                .where(Slot.id == slot_id, Slot.status == "available", Slot.start_at > _clinic_now())
                .values(status="booked")
            )
            if update_result.rowcount != 1:
                return {"success": False, "message": "That slot is no longer available. Please check availability again."}

            slot = db.scalar(select(Slot).where(Slot.id == slot_id))
            doctor = db.scalar(select(Doctor).where(Doctor.id == slot.doctor_id))
            appointment = Appointment(
                doctor_id=doctor.id,
                slot_id=slot.id,
                phone_number=phone_number,
                status="booked",
                created_at=_clinic_now(),
            )
            db.add(appointment)
            db.flush()
            result = {
                "success": True,
                "appointment_id": appointment.id,
                "reference": f"VC-{appointment.id:04d}",
                "doctor_name": doctor.name,
                "speciality": doctor.speciality,
                "date": slot.start_at.date().isoformat(),
                "time": _format_time(slot.start_at),
                "message": "Appointment booked successfully.",
            }
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_active_appointments_for_phone(phone_number: str) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Appointment, Slot, Doctor)
            .join(Slot, Slot.id == Appointment.slot_id)
            .join(Doctor, Doctor.id == Appointment.doctor_id)
            .where(Appointment.phone_number == phone_number, Appointment.status == "booked")
            .order_by(Slot.start_at)
        ).all()
        return [
            {
                "appointment_id": appointment.id,
                "reference": f"VC-{appointment.id:04d}",
                "doctor_name": doctor.name,
                "speciality": doctor.speciality,
                "date": slot.start_at.date().isoformat(),
                "time": _format_time(slot.start_at),
                "status": appointment.status,
            }
            for appointment, slot, doctor in rows
        ]
    finally:
        db.close()


def cancel_appointment_for_phone(*, appointment_id: int, phone_number: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        with db.begin():
            appointment = db.scalar(
                select(Appointment)
                .where(
                    Appointment.id == appointment_id,
                    Appointment.phone_number == phone_number,
                    Appointment.status == "booked",
                )
            )
            if not appointment:
                return {
                    "success": False,
                    "message": "I could not find an active appointment with that reference for this phone number.",
                }
            slot = db.scalar(select(Slot).where(Slot.id == appointment.slot_id))
            doctor = db.scalar(select(Doctor).where(Doctor.id == appointment.doctor_id))
            appointment.status = "cancelled"
            appointment.cancelled_at = _clinic_now()
            slot.status = "available"
            result = {
                "success": True,
                "appointment_id": appointment.id,
                "reference": f"VC-{appointment.id:04d}",
                "doctor_name": doctor.name,
                "speciality": doctor.speciality,
                "date": slot.start_at.date().isoformat(),
                "time": _format_time(slot.start_at),
                "message": "Appointment cancelled successfully. The slot is available again.",
            }
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_doctors() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        doctors = list(db.scalars(select(Doctor).where(Doctor.is_active.is_(True)).order_by(Doctor.name)))
        now = _clinic_now()
        result = []
        for doctor in doctors:
            next_slot = db.scalar(
                select(Slot.start_at)
                .where(Slot.doctor_id == doctor.id, Slot.status == "available", Slot.start_at > now)
                .order_by(Slot.start_at)
                .limit(1)
            )
            result.append(
                {
                    "id": doctor.id,
                    "name": doctor.name,
                    "speciality": doctor.speciality,
                    "qualification": doctor.qualification,
                    "experience_years": doctor.experience_years,
                    "consultation_fee": doctor.consultation_fee,
                    "bio": doctor.bio,
                    "next_available": next_slot.isoformat() if next_slot else None,
                    "initials": "".join(part[0] for part in doctor.name.replace("Dr. ", "").split()[:2]).upper(),
                }
            )
        return result
    finally:
        db.close()


def get_doctor_slots(doctor_id: int, requested_date: str | None = None) -> list[dict[str, Any]]:
    day = _parse_date(requested_date)
    now = _clinic_now()
    db = SessionLocal()
    try:
        query = (
            select(Slot, Doctor)
            .join(Doctor, Doctor.id == Slot.doctor_id)
            .where(Slot.doctor_id == doctor_id, Slot.status == "available", Slot.start_at > now)
        )
        if day:
            start = datetime.combine(day, time.min)
            query = query.where(Slot.start_at < start + timedelta(days=1))
        rows = db.execute(query.order_by(Slot.start_at).limit(20)).all()
        return [
            {
                "slot_id": slot.id,
                "date": slot.start_at.date().isoformat(),
                "time": _format_time(slot.start_at),
                "start_at": slot.start_at.isoformat(),
                "consultation_fee": doctor.consultation_fee,
            }
            for slot, doctor in rows
        ]
    finally:
        db.close()


def get_appointments(status: str | None = None) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        query = (
            select(Appointment, Slot, Doctor)
            .join(Slot, Slot.id == Appointment.slot_id)
            .join(Doctor, Doctor.id == Appointment.doctor_id)
        )
        if status:
            query = query.where(Appointment.status == status)
        rows = db.execute(query.order_by(Slot.start_at.asc())).all()
        return [
            {
                "id": appointment.id,
                "reference": f"VC-{appointment.id:04d}",
                "doctor_id": doctor.id,
                "doctor_name": doctor.name,
                "speciality": doctor.speciality,
                "date": slot.start_at.date().isoformat(),
                "time": _format_time(slot.start_at),
                "start_at": slot.start_at.isoformat(),
                "status": appointment.status,
                "phone_number": mask_phone(appointment.phone_number),
                "created_at": appointment.created_at.isoformat(),
            }
            for appointment, slot, doctor in rows
        ]
    finally:
        db.close()


def dashboard_summary() -> dict[str, int]:
    db = SessionLocal()
    try:
        today = _clinic_now().date()
        start = datetime.combine(today, time.min)
        end = start + timedelta(days=1)
        booked = list(
            db.scalars(
                select(Appointment).join(Slot).where(Appointment.status == "booked", Slot.start_at >= start, Slot.start_at < end)
            )
        )
        total_doctors = len(list(db.scalars(select(Doctor).where(Doctor.is_active.is_(True)))))
        available_slots = len(
            list(db.scalars(select(Slot.id).where(Slot.status == "available", Slot.start_at >= start)))
        )
        total_booked = len(list(db.scalars(select(Appointment.id).where(Appointment.status == "booked"))))
        return {
            "today_appointments": len(booked),
            "doctors": total_doctors,
            "available_slots": available_slots,
            "active_appointments": total_booked,
        }
    finally:
        db.close()
