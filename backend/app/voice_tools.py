from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import EndWorkerFrame
from pipecat.services.llm_service import FunctionCallParams

from app.services.appointments import (
    book_slot,
    cancel_appointment_for_phone,
    get_active_appointments_for_phone,
    get_slot,
    search_availability,
)
from app.services.phone import format_phone_for_speech, normalize_indian_phone


@dataclass
class CallState:
    """Mutable state scoped to one Pipecat call; never shared between callers."""

    pending_phone_number: str | None = None
    verified_phone_number: str | None = None
    pending_slot_id: int | None = None
    pending_cancellation_id: int | None = None
    booking_confirmed: bool = False
    cancellation_confirmed: bool = False


def build_voice_tools(state: CallState) -> list[FunctionSchema]:
    async def capture_phone_number(params: FunctionCallParams) -> None:
        """Capture the caller's Indian mobile number from the digits they speak.

        Args:
            phone_number: The complete number as spoken or transcribed, for example
                'nine eight seven six five four three two one zero'.
        """
        raw_number = str(params.arguments.get("phone_number", ""))
        try:
            normalized = normalize_indian_phone(raw_number)
        except ValueError as exc:
            state.pending_phone_number = None
            state.verified_phone_number = None
            await params.result_callback({"success": False, "message": str(exc)})
            return

        state.pending_phone_number = normalized
        state.verified_phone_number = None
        state.pending_slot_id = None
        state.pending_cancellation_id = None
        state.booking_confirmed = False
        state.cancellation_confirmed = False
        await params.result_callback(
            {
                "success": True,
                "number_to_read_back": format_phone_for_speech(normalized),
                "instruction": "Read this number back digit by digit and ask whether it is correct. Then call confirm_phone_number only after the caller answers.",
            }
        )

    async def confirm_phone_number(params: FunctionCallParams) -> None:
        """Record whether the caller confirmed the phone number read back to them.

        Args:
            confirmed: True only when the caller explicitly says the number is correct.
        """
        confirmed = params.arguments.get("confirmed") is True
        if not state.pending_phone_number:
            await params.result_callback({"success": False, "message": "No phone number is awaiting confirmation. Ask the caller to say it again."})
            return
        if not confirmed:
            state.pending_phone_number = None
            state.verified_phone_number = None
            await params.result_callback({"success": False, "message": "The caller did not confirm. Ask them to repeat the phone number."})
            return

        state.verified_phone_number = state.pending_phone_number
        state.pending_phone_number = None
        await params.result_callback(
            {
                "success": True,
                "verified": True,
                "message": "Phone number confirmed for this call. Use this verified identity for all appointment operations.",
            }
        )

    async def check_doctor_availability(params: FunctionCallParams) -> None:
        """Find doctors and available appointment slots by doctor, speciality or date.

        Args:
            doctor_name: Optional doctor's full or partial name.
            speciality: Optional medical speciality such as Dermatology or Cardiology.
            date: Optional requested date in YYYY-MM-DD format. Convert relative dates
                using the clinic date supplied in the system instructions.
        """
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "First ask for the caller's phone number, read it back and confirm it."})
            return
        args = params.arguments or {}
        doctor_name = args.get("doctor_name")
        speciality = args.get("speciality")
        requested_date = args.get("date")
        try:
            result = search_availability(
                doctor_name=doctor_name,
                speciality=speciality,
                date_text=requested_date,
            )

            # First-stage discovery: return only the doctors/specialities that
            # have availability. The model should ask the caller to choose one,
            # then call this tool again with doctor_name/speciality to fetch slots.
            if not doctor_name and not speciality:
                doctors_by_key: dict[tuple[str, str], dict[str, str]] = {}
                for slot in result.get("available_slots", []):
                    key = (slot["doctor_name"], slot["speciality"])
                    doctors_by_key.setdefault(
                        key,
                        {"doctor_name": key[0], "speciality": key[1]},
                    )

                await params.result_callback(
                    {
                        "success": result.get("success", False),
                        "date": requested_date,
                        "available_doctors": list(doctors_by_key.values()),
                        "available_doctor_count": len(doctors_by_key),
                        "message": result.get("message", "Availability retrieved."),
                        "next_step": (
                            "Tell the caller which doctors/specialities are available and ask "
                            "which one they prefer. Once they choose, call this tool again "
                            "with that doctor_name or speciality and the same date to retrieve slots."
                        ),
                    }
                )
                return

            # Second-stage lookup: retain only the fields needed to offer a slot
            # and pass its slot_id to prepare_appointment.
            compact_slots = [
                {
                    "slot_id": slot["slot_id"],
                    "doctor_name": slot["doctor_name"],
                    "speciality": slot["speciality"],
                    "date": slot["date"],
                    "time": slot["time"],
                    "consultation_fee": slot.get("consultation_fee"),
                }
                for slot in result.get("available_slots", [])
            ]
            await params.result_callback(
                {
                    "success": result.get("success", False),
                    "count": len(compact_slots),
                    "available_slots": compact_slots,
                    "message": result.get("message", "Availability retrieved."),
                }
            )
        except ValueError as exc:
            await params.result_callback({"success": False, "message": str(exc)})

    async def list_my_appointments(params: FunctionCallParams) -> None:
        """List the caller's active appointments using the confirmed phone number."""
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "The caller's phone number has not been confirmed yet."})
            return
        rows = get_active_appointments_for_phone(state.verified_phone_number)
        await params.result_callback({"success": True, "count": len(rows), "appointments": rows})

    async def prepare_appointment(params: FunctionCallParams) -> None:
        """Select an available slot and retrieve its exact details before confirmation.

        Args:
            slot_id: The slot_id returned by check_doctor_availability that the caller selected.
        """
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "The caller's phone number has not been confirmed yet."})
            return
        try:
            slot_id = int(params.arguments.get("slot_id"))
        except (TypeError, ValueError):
            await params.result_callback({"success": False, "message": "Please select one of the slot IDs returned by the availability tool."})
            return
        slot = get_slot(slot_id)
        if not slot or slot.get("status") != "available":
            await params.result_callback({"success": False, "message": "That slot is no longer available. Check availability again."})
            return
        state.pending_slot_id = slot_id
        state.pending_cancellation_id = None
        state.booking_confirmed = False
        state.cancellation_confirmed = False
        await params.result_callback(
            {
                "success": True,
                "selected_appointment": {
                    "doctor_name": slot["doctor_name"],
                    "speciality": slot["speciality"],
                    "date": slot["date"],
                    "time": slot["time"],
                    "consultation_fee": slot["consultation_fee"],
                },
                "instruction": "Read back doctor, date and time, then ask for explicit confirmation. If the caller clearly says yes, first call confirm_booking(confirmed=true), then call book_appointment.",
            }
        )

    async def confirm_booking(params: FunctionCallParams) -> None:
        """Record the caller's explicit yes/no response to the appointment read-back.

        Args:
            confirmed: True only when the caller clearly agrees to book the selected slot.
        """
        if state.pending_slot_id is None:
            await params.result_callback({"success": False, "message": "There is no prepared booking to confirm."})
            return
        confirmed = params.arguments.get("confirmed") is True
        state.booking_confirmed = confirmed
        if not confirmed:
            state.pending_slot_id = None
        await params.result_callback({"success": confirmed, "confirmed": confirmed, "message": "Booking confirmation recorded." if confirmed else "Booking declined. No appointment was created."})

    async def book_appointment(params: FunctionCallParams) -> None:
        """Book the previously selected slot only after confirm_booking records a clear yes."""
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "The caller's phone number is not verified. No appointment was booked."})
            return
        if state.pending_slot_id is None or not state.booking_confirmed:
            await params.result_callback({"success": False, "message": "The caller has not explicitly confirmed the prepared appointment. Ask for confirmation first."})
            return
        slot_id = state.pending_slot_id
        state.pending_slot_id = None
        state.booking_confirmed = False
        result = book_slot(slot_id=slot_id, phone_number=state.verified_phone_number)
        await params.result_callback(result)

    async def prepare_cancellation(params: FunctionCallParams) -> None:
        """Select one of the caller's active appointments for cancellation confirmation.

        Args:
            appointment_id: Appointment ID from list_my_appointments.
        """
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "The caller's phone number has not been confirmed yet."})
            return
        try:
            appointment_id = int(params.arguments.get("appointment_id"))
        except (TypeError, ValueError):
            await params.result_callback({"success": False, "message": "Please select an appointment ID from the caller's active appointments."})
            return
        appointments = get_active_appointments_for_phone(state.verified_phone_number)
        chosen = next((a for a in appointments if a["appointment_id"] == appointment_id), None)
        if not chosen:
            await params.result_callback({"success": False, "message": "That appointment does not belong to this caller or is no longer active."})
            return
        state.pending_cancellation_id = appointment_id
        state.pending_slot_id = None
        state.booking_confirmed = False
        state.cancellation_confirmed = False
        await params.result_callback(
            {
                "success": True,
                "appointment_to_cancel": chosen,
                "instruction": "Read the appointment details back and ask for explicit cancellation confirmation. If the caller clearly says yes, first call confirm_cancellation(confirmed=true), then call cancel_appointment.",
            }
        )

    async def confirm_cancellation(params: FunctionCallParams) -> None:
        """Record the caller's explicit yes/no response to the cancellation read-back.

        Args:
            confirmed: True only when the caller clearly agrees to cancel the selected appointment.
        """
        if state.pending_cancellation_id is None:
            await params.result_callback({"success": False, "message": "There is no prepared cancellation to confirm."})
            return
        confirmed = params.arguments.get("confirmed") is True
        state.cancellation_confirmed = confirmed
        if not confirmed:
            state.pending_cancellation_id = None
        await params.result_callback({"success": confirmed, "confirmed": confirmed, "message": "Cancellation confirmation recorded." if confirmed else "Cancellation declined. The appointment remains active."})

    async def cancel_appointment(params: FunctionCallParams) -> None:
        """Cancel the previously selected appointment only after confirm_cancellation records a clear yes."""
        if not state.verified_phone_number:
            await params.result_callback({"success": False, "message": "The caller's phone number is not verified. No appointment was cancelled."})
            return
        if state.pending_cancellation_id is None or not state.cancellation_confirmed:
            await params.result_callback({"success": False, "message": "The caller has not explicitly confirmed cancellation. Ask for confirmation first."})
            return
        appointment_id = state.pending_cancellation_id
        state.pending_cancellation_id = None
        state.cancellation_confirmed = False
        result = cancel_appointment_for_phone(
            appointment_id=appointment_id,
            phone_number=state.verified_phone_number,
        )
        await params.result_callback(result)

    async def end_call(params: FunctionCallParams) -> None:
        """Gracefully end the browser call after the caller says goodbye or asks to hang up."""
        await params.result_callback(
            {"success": True, "message": "The caller requested to end the call. Say a brief goodbye, then end the session."}
        )
        # EndWorkerFrame is queued downstream so the current assistant turn can
        # finish flushing before Pipecat closes the worker and WebRTC transport.
        await params.llm.push_frame(EndWorkerFrame(reason="Caller requested to end the call"))

    return [
        FunctionSchema(
            name="capture_phone_number",
            description="Capture and normalize the phone number the caller says aloud. Always read it back before proceeding.",
            properties={"phone_number": {"type": "string", "description": "The phone number as spoken by the caller."}},
            required=["phone_number"],
            handler=capture_phone_number,
        ),
        FunctionSchema(
            name="confirm_phone_number",
            description="Confirm whether the caller explicitly said that the repeated phone number is correct.",
            properties={"confirmed": {"type": "boolean", "description": "True only if the caller explicitly confirmed the read-back number."}},
            required=["confirmed"],
            handler=confirm_phone_number,
        ),
        FunctionSchema(
            name="check_doctor_availability",
            description="Return real available slots from the clinic database. Use after caller phone number verification.",
            properties={
                "doctor_name": {"type": "string", "description": "Doctor name or partial name; omit if searching by speciality."},
                "speciality": {"type": "string", "description": "Speciality such as Dermatology or Cardiology; omit if a doctor is specified."},
                "date": {"type": "string", "description": "Optional date in YYYY-MM-DD format."},
            },
            required=[],
            handler=check_doctor_availability,
        ),
        FunctionSchema(
            name="list_my_appointments",
            description="Find active appointments belonging only to the caller's verified phone number.",
            properties={},
            required=[],
            handler=list_my_appointments,
        ),
        FunctionSchema(
            name="prepare_appointment",
            description="Select an available slot and get details to read back. This does not book it.",
            properties={"slot_id": {"type": "integer", "description": "The slot_id returned by check_doctor_availability."}},
            required=["slot_id"],
            handler=prepare_appointment,
        ),
        FunctionSchema(
            name="confirm_booking",
            description="Record the caller's explicit yes/no confirmation after reading back the proposed doctor, date and time.",
            properties={"confirmed": {"type": "boolean", "description": "True only if the caller clearly said yes to booking the read-back appointment."}},
            required=["confirmed"],
            handler=confirm_booking,
        ),
        FunctionSchema(
            name="book_appointment",
            description="Book the pending slot only after the caller explicitly confirms the doctor, date and time.",
            properties={},
            required=[],
            handler=book_appointment,
        ),
        FunctionSchema(
            name="prepare_cancellation",
            description="Select a caller-owned active appointment and get its details for read-back confirmation. Does not cancel it.",
            properties={"appointment_id": {"type": "integer", "description": "An appointment_id from list_my_appointments."}},
            required=["appointment_id"],
            handler=prepare_cancellation,
        ),
        FunctionSchema(
            name="confirm_cancellation",
            description="Record the caller's explicit yes/no confirmation after reading back the appointment to be cancelled.",
            properties={"confirmed": {"type": "boolean", "description": "True only if the caller clearly said yes to cancelling the read-back appointment."}},
            required=["confirmed"],
            handler=confirm_cancellation,
        ),
        FunctionSchema(
            name="cancel_appointment",
            description="Cancel the pending appointment only after the caller explicitly confirms the details.",
            properties={},
            required=[],
            handler=cancel_appointment,
        ),
        FunctionSchema(
            name="end_call",
            description="Gracefully end the voice call when the caller clearly says goodbye, asks to hang up, or says the conversation is finished. Use only after giving a brief farewell; do not continue the conversation after this tool.",
            properties={},
            required=[],
            handler=end_call,
        ),
    ]
