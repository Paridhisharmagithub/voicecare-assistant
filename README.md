# VoiceCare — Voice AI Doctor Appointment Assistant

A browser-based clinic receptionist that can check doctor availability, book an appointment, and cancel an existing appointment through a natural voice conversation.

**Stack:** Pipecat · ElevenLabs Realtime STT · Google Gemini · ElevenLabs TTS · FastAPI · SQLAlchemy · SQLite · React · Vite · SmallWebRTC


> **Demo scope:** This project uses mock clinic data and is intended for an internship assignment/demo. It is not connected to a real hospital, does not provide medical advice, and must not be used with real patient data.

## Features

- Browser-based microphone calling using Pipecat + SmallWebRTC.
- Realtime speech recognition through ElevenLabs, conversation and function calling through Gemini, and speech synthesis through ElevenLabs.
- Required voice tools: `check_doctor_availability`, `book_appointment`, `cancel_appointment`.
- Additional call-scoped tools capture and confirm the caller's spoken Indian mobile number, list their appointments, prepare an action, and record a separate explicit yes/no confirmation before each database mutation.
- Caller identity is held in the individual call's server-side state. There is no login, OTP or caller-ID flow.
- SQLAlchemy + SQLite persistence with seeded mock doctors, slots and a demo appointment.
- Atomic slot claiming prevents two sessions from booking the same available slot at the same time.
- The browser dashboard shows doctors, their available times, upcoming appointments and a live transcript. It refreshes the shared database view automatically during a call.
- Responsive, restrained ivory/plum design with minimal motion and reduced-motion support.

## Requirements

- Python 3.11–3.13 (Python 3.12 is a good choice).
- `uv` package manager. If it is not installed on Windows, run `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"` and reopen the terminal.
- Node.js 20 or newer and npm.
- An ElevenLabs API key and voice ID.
- A Google AI Studio API key with access to the selected Gemini model.
- A browser with microphone access (localhost is treated as a secure context by modern browsers).

No Twilio, paid telephony number, external database, Redis, Docker, or Pipecat Cloud account is required for local development.

## 1. Configure secrets

Copy the backend example file and fill in your own provider values. On Windows, the first run of `start-backend.bat` creates `backend/.env` automatically if it does not exist, then pauses so you can add the keys.

**Windows PowerShell:**

```powershell
Copy-Item backend/.env.example backend/.env
```

**macOS/Linux:**

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```dotenv
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_VOICE_ID=your_elevenlabs_voice_id
GOOGLE_API_KEY=your_google_ai_studio_api_key

GEMINI_MODEL=gemini-3.5-flash-lite
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5

DATABASE_URL=sqlite:///./data/voicecare.db
CLINIC_NAME=VoiceCare Clinic
APP_TIMEZONE=Asia/Kolkata
```

The frontend only needs the backend URL. Copy its example file:

```powershell
Copy-Item frontend/.env.example frontend/.env
```

You can leave the frontend values as they are for local development:

```dotenv
VITE_API_BASE_URL=http://localhost:7860
VITE_PIPECAT_URL=http://localhost:7860
```

**Never put provider API keys in `frontend/.env` or any variable beginning with `VITE_`.** Vite exposes those values to the browser bundle.

## 2. Install and start the backend

Open a terminal in the repository root:

```powershell
cd backend
uv sync
uv run bot.py
```

The Pipecat development runner starts the backend at `http://localhost:7860`. It hosts the voice session endpoint (`/start`) and the dashboard REST endpoints on the same server.

Useful checks:

- `http://localhost:7860/api/health` — backend and voice-key configuration.
- `http://localhost:7860/api/doctors` — seeded doctor list.
- `http://localhost:7860/api/appointments` — appointment records.
- `http://localhost:7860/docs` — FastAPI API documentation, if enabled by the runner.

The SQLite database is created automatically at `backend/data/voicecare.db` and seeded on the first backend startup. The seeded demo appointment belongs to `+919876543210`; use that number when demonstrating cancellation. New bookings made during a call use the phone number the caller says and confirms.

## 3. Install and start the frontend

Open a **second terminal** in the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in Chrome or Edge. Allow microphone access when asked, then select **Start a call**. On Windows, `start-frontend.bat` installs the npm dependencies automatically on its first run.

For convenience, `start-all.bat` opens separate backend and frontend terminal windows after you have configured `backend/.env`.

## 4. Try the booking flow

A suggested demo conversation:

1. “I would like to book an appointment with a dermatologist tomorrow.”
2. Give a 10-digit Indian mobile number, speaking each digit clearly.
3. Confirm the number after the assistant reads it back.
4. Select Dr. Ananya Sharma and one of the available slots.
5. Confirm the doctor, date and time when the assistant repeats the details.
6. Check the upcoming appointment list on the dashboard. It refreshes from SQLite automatically.

For cancellation, use the seeded demo number `+91 98765 43210`, ask to cancel the existing appointment, select the appointment if prompted, and confirm the doctor/date/time before cancellation.

## 5. API overview

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Backend readiness and missing voice configuration keys |
| GET | `/api/doctors` | List active doctors and next available time |
| GET | `/api/doctors/{doctor_id}/slots` | List a doctor's available slots |
| GET | `/api/appointments` | List appointment records |
| GET | `/api/dashboard/summary` | Small summary endpoint for the clinic |

Appointment creation and cancellation are performed by the Pipecat function tools, not by separate unauthenticated dashboard buttons.

## 6. Voice pipeline

```text
Browser microphone
      │
      ▼
SmallWebRTC / Pipecat transport
      │
      ▼
ElevenLabs Realtime STT
      │
      ▼
Gemini LLM + tool calling
      │
      ├── capture_phone_number / confirm_phone_number
      ├── check_doctor_availability
      ├── list_my_appointments
      ├── prepare_appointment → confirm_booking → book_appointment
      └── prepare_cancellation → confirm_cancellation → cancel_appointment
      │
      ▼
ElevenLabs TTS
      │
      ▼
Browser audio playback
```

The caller's verified phone number and any pending booking/cancellation confirmation are stored in a `CallState` object created for that voice session. Tool handlers require explicit confirmation before changing appointment records. The database re-checks slot availability inside the booking transaction and checks appointment ownership during cancellation.

## 7. Important implementation notes

- Phone numbers are normalized as Indian `+91` mobile numbers. This is a mock clinic rule and can be changed in `app/services/phone.py`.
- Database date/time values are stored as naive clinic-local timestamps using `APP_TIMEZONE` (default `Asia/Kolkata`).
- The voice pipeline uses ElevenLabs VAD for realtime transcript segmentation; a separate local VAD service is not required. While a doctor is expanded in the dashboard, the slot list refreshes periodically so booked times disappear from the available list.
- Dashboard appointment records are refreshed periodically from the API. The live call transcript comes from Pipecat client events.
- This demo does not send SMS, email, calendar invites, or reminders.
- For production, replace mock doctors and slots, add staff/admin authentication, define data retention and consent, and obtain a proper privacy/security review before handling patient information.

## 8. Troubleshooting

**Backend says voice services are not configured**

Check that `backend/.env` exists and contains `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and `GOOGLE_API_KEY`. Restart the backend after changing `.env`.

**Frontend says backend offline**

Make sure `uv run bot.py` is still running at port `7860`. Visit `/api/health` directly to check it.

**Microphone permission fails**

Use `http://localhost:5173`, allow microphone permission in the browser, and check that another application is not exclusively using the microphone.

**WebRTC does not connect**

Try Chrome/Edge, disable VPN temporarily, and ensure local firewall rules allow the browser and Python process to communicate. SmallWebRTC needs working peer-to-peer connectivity.

**Gemini or ElevenLabs rejects a request**

Check that the selected model/voice is enabled for your account, the keys are valid, and the account has quota/credits. You can change the model IDs in `backend/.env` without changing the pipeline code.

## 9. Project structure

```text
voicecare-assistant/
├── backend/
│   ├── app/
│   │   ├── api.py                 # Dashboard REST endpoints
│   │   ├── config.py              # Environment settings
│   │   ├── database.py            # SQLite engine and sessions
│   │   ├── models.py              # Doctor, Slot, Appointment tables
│   │   ├── seed.py                # Mock data initializer
│   │   ├── voice_prompt.py        # Voice-agent instructions
│   │   ├── voice_tools.py         # Pipecat function tools and call state
│   │   └── services/
│   │       ├── appointments.py    # Appointment business logic
│   │       └── phone.py           # Indian phone normalization
│   ├── bot.py                     # Pipecat pipeline and runner
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx                # Dashboard and browser call controls
│   │   ├── api.js                 # REST API client
│   │   ├── main.jsx
│   │   └── styles.css             # Responsive minimalist design
│   ├── package.json
│   └── .env.example
└── README.md
```

## Pipeline description for the assignment form

The browser captures microphone audio and sends it to a Pipecat backend over SmallWebRTC. Pipecat streams the audio through ElevenLabs Realtime STT, passes the transcript to Gemini for conversation and tool selection, and sends the response to ElevenLabs TTS for playback. When the caller requests an appointment action, Gemini invokes Python tools that validate the caller's spoken and confirmed phone number, check or update the SQLite database, and return the result to the conversation. The dashboard reads the same database and displays appointment changes alongside the live transcript.

## 10. Run the local smoke test

From the backend directory:

```powershell
uv run python scripts/smoke_test.py
```

This creates a disposable SQLite file, checks phone normalization, seeds the mock clinic, books and cancels an appointment, verifies that the slot can be booked again, and removes the temporary database. It does not modify your normal demo database.

You can also run the phone unit tests:

```powershell
uv run python -m unittest discover -s tests
```
