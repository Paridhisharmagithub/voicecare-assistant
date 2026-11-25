from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    speciality: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    qualification: Mapped[str] = mapped_column(String(120), nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consultation_fee: Mapped[int] = mapped_column(Integer, nullable=False, default=500)
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    slots: Mapped[list["Slot"]] = relationship(back_populates="doctor")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="doctor")


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True)

    doctor: Mapped[Doctor] = relationship(back_populates="slots")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="slot")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("doctors.id"), nullable=False, index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="booked", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    doctor: Mapped[Doctor] = relationship(back_populates="appointments")
    slot: Mapped[Slot] = relationship(back_populates="appointments")
