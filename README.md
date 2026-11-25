# VoiceCare — Voice AI Doctor Appointment Assistant

VoiceCare is a browser-based clinic receptionist that lets a caller check doctor availability, book an appointment, and cancel an existing appointment through a natural voice conversation.

> **Demo scope:** This project uses mock clinic data for an internship assignment. It is not connected to a real hospital, does not provide medical advice, and must not be used with real patient data.

## Technology stack

- **Voice orchestration:** Pipecat + SmallWebRTC
- **Speech-to-text:** ElevenLabs Realtime STT
- **Language model and tool calling:** Google Gemini
- **Text-to-speech:** ElevenLabs TTS
- **Backend/API:** Python, FastAPI, SQLAlchemy
- **Database:** SQLite with seeded mock doctors, slots, and appointments
- **Frontend:** React, Vite, JavaScript, CSS

## Features

- Browser microphone calling over WebRTC, with start/end call controls.
- Live caller and assistant transcript in the dashboard.
- Realtime speech recognition through ElevenLabs, Gemini conversation and function calling, and ElevenLabs speech synthesis.
- Voice tools for checking doctor availability, booking appointments, and cancelling appointments.
- Call-scoped phone-number capture and read-back confirmation. The caller is identified by the phone number spoken during the call; there is no login, OTP, or caller-ID flow.
- Separate explicit confirmation before booking or cancellation changes are committed.
- SQLite persistence with seeded doctors, appointment slots, and a demo appointment.
- Slot availability is rechecked as part of the booking transaction to prevent a slot from being booked twice.
- Dashboard pages for the voice assistant, doctors, appointments, and availability.
- Appointment and availability data is fetched when relevant views load and refreshed after relevant call/session actions; the dashboard does not continuously poll the API.
- Responsive ivory/plum interface with reduced-motion support.

## Requirements

- Python **3.11–3.13** (Python 3.12 recommended).
- [`uv`](https://docs.astral.sh/uv/) Python package manager.
- Node.js **20 or newer** and npm.
- An ElevenLabs API key and a voice ID supported by the API for your account.
- A Google AI Studio API key with access to the configured Gemini model.
- A modern browser with microphone access (Chrome or Edge recommended).

No Twilio number, external database, Redis, Docker, or Pipecat Cloud account is required for local development.

## Quick start (Windows)

The repository includes three Windows convenience scripts:

- `start-backend.bat` — creates `backend/.env` from the example on first run, installs/synchronizes backend dependencies with `uv`, and starts the Pipecat backend.
- `start-frontend.bat` — installs frontend dependencies on first run and starts the Vite development server.
- `start-all.bat` — opens separate terminal windows for the backend and frontend after `backend/.env` has been configured.

### 1. Configure the backend environment

From the repository root, run:

```powershell
Copy-Item backend/.env.example backend/.env
```

Open `backend/.env` and provide your own credentials:

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

Keep these credentials private. Never commit `backend/.env`, and never put provider keys in frontend environment variables beginning with `VITE_` because Vite exposes those values to the browser bundle.

### 2. Configure the frontend environment

```powershell
Copy-Item frontend/.env.example frontend/.env
```

The example values are already suitable for local development:

```dotenv
VITE_API_BASE_URL=http://localhost:7860
VITE_PIPECAT_URL=http://localhost:7860
```

### 3. Start the application

After filling in `backend/.env`, run this from the repository root:

```powershell
.\start-all.bat
```

This opens separate backend and frontend terminal windows. Keep both terminals running while using the app. On the very first run, if `backend/.env` does not exist, the backend launcher creates it from the example and exits; add your credentials, then run `start-all.bat` again.

You can also start them separately with `start-backend.bat` and `start-frontend.bat`.

### Manual start (Windows, macOS, or Linux)

**Backend — terminal 1:**

```bash
cd backend
uv sync
uv run bot.py
```

The Pipecat development runner starts the backend at `http://localhost:7860`. The voice session endpoint (`/start`) and dashboard REST endpoints are served by this backend.

**Frontend — terminal 2:**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in Chrome or Edge and allow microphone access when prompted. Select **Start a call** to talk to the assistant.

## Demo data and suggested flows

The SQLite database is initialized and seeded when the backend starts for the first time. The seeded demo appointment belongs to `+91 98765 43210`; use this number when demonstrating cancellation. New bookings use the number the caller speaks and confirms during the call.

### Booking

1. Start a browser call and ask to book an appointment.
2. Speak a 10-digit Indian mobile number clearly.
3. Confirm the number after the assistant reads it back.
4. Choose a doctor and an available slot.
5. Confirm the doctor, date, and time when the assistant repeats the details.
6. Verify the booking reference and the updated appointment in the dashboard.

### Cancellation

1. Start a call using the seeded demo number `+91 98765 43210`.
2. Ask to cancel the existing appointment.
3. Select the appointment if the assistant asks you to disambiguate.
4. Confirm the doctor/date/time before cancellation.
5. Verify that the appointment is shown as cancelled in the dashboard.

## API overview

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/health` | Backend readiness and voice configuration status |
| `GET` | `/api/doctors` | List active doctors and their next available time |
| `GET` | `/api/doctors/{doctor_id}/slots` | List a doctor's available slots |
| `GET` | `/api/appointments` | List appointment records |
| `GET` | `/api/dashboard/summary` | Dashboard summary data |

Appointment creation and cancellation are performed through the Pipecat function tools, not through unauthenticated dashboard mutation buttons.

## Voice pipeline

```text
Browser microphone
       |
       v
SmallWebRTC / Pipecat transport
       |
       v
ElevenLabs Realtime STT
       |
       v
Gemini LLM + function calling
       |
       +--> capture_phone_number / confirm_phone_number
       +--> check_doctor_availability
       +--> list_my_appointments
       +--> prepare_appointment -> confirm_booking -> book_appointment
       +--> prepare_cancellation -> confirm_cancellation -> cancel_appointment
       |
       v
ElevenLabs TTS
       |
       v
Browser audio playback
```

Each voice session gets its own `CallState`, which holds the caller's verified phone number and any pending booking/cancellation confirmation. Tool handlers require explicit confirmation before changing appointment records. Booking rechecks slot availability inside the database transaction, and cancellation checks that the appointment belongs to the caller's verified phone number.

## Important implementation notes

- Phone numbers are normalized as Indian `+91` mobile numbers. This is a demo rule and can be changed in `backend/app/services/phone.py`.
- Database date/time values use clinic-local timestamps configured by `APP_TIMEZONE` (default: `Asia/Kolkata`). The backend includes `tzdata` so IANA timezone names also work on Windows.
- ElevenLabs Realtime STT uses its VAD-based commit strategy for speech-turn segmentation; a separate local VAD service is not required by this implementation.
- The live transcript is driven by Pipecat client events. Dashboard data is fetched on view entry and refreshed after relevant call/session actions rather than by continuous polling.
- This demo does not send SMS, email, calendar invitations, or reminders.
- For production use, replace mock clinic data, add appropriate staff/admin authentication, define data retention and consent policies, and complete a privacy/security review before handling patient information.

## Tests

Run the backend smoke test from the `backend` directory:

```powershell
uv run python scripts/smoke_test.py
```

The smoke test uses a disposable SQLite database. It checks phone normalization, seeds mock clinic data, books and cancels an appointment, verifies that the slot can be booked again, and removes the temporary database. It does not modify the normal demo database.

Run the phone unit tests:

```powershell
uv run python -m unittest discover -s tests
```

## Troubleshooting

**Backend says voice services are not configured**

- Confirm that `backend/.env` exists and contains `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, and `GOOGLE_API_KEY`.
- Restart the backend after changing environment variables.

**Frontend says the backend is offline**

- Confirm that the backend is running on port `7860`.
- Open `http://localhost:7860/api/health` to inspect backend readiness.

**Microphone permission fails**

- Use `http://localhost:5173`, allow microphone permission in the browser, and check that another application is not exclusively using the microphone.

**WebRTC does not connect**

- Try Chrome or Edge, temporarily disable VPN/proxy software for diagnosis, and check firewall permissions for the browser and Python process. SmallWebRTC requires working peer-to-peer connectivity.

**Gemini or ElevenLabs rejects a request or responds slowly**

- Check provider connectivity, API key permissions, model/voice availability, account quota/credits, and provider status. Model IDs can be changed in `backend/.env`.

## Project structure

```text
voicecare-assistant/
├── start-all.bat                 # Start both services (Windows)
├── start-backend.bat             # Start the Pipecat backend (Windows)
├── start-frontend.bat            # Start the Vite frontend (Windows)
├── backend/
│   ├── app/
│   │   ├── api.py                # Dashboard REST endpoints
│   │   ├── config.py             # Environment settings
│   │   ├── database.py           # SQLite engine and sessions
│   │   ├── models.py             # Doctor, Slot, Appointment tables
│   │   ├── seed.py               # Mock data initializer
│   │   ├── voice_prompt.py       # Voice-agent instructions
│   │   ├── voice_tools.py        # Pipecat function tools and call state
│   │   └── services/
│   │       ├── appointments.py   # Appointment business logic
│   │       └── phone.py          # Indian phone normalization
│   ├── scripts/
│   │   └── smoke_test.py         # Isolated backend workflow test
│   ├── tests/
│   │   └── test_phone.py         # Phone-number unit tests
│   ├── bot.py                    # Pipecat pipeline and runner
│   ├── pyproject.toml
│   ├── uv.lock                   # Locked Python dependencies
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx               # Dashboard and browser call controls
│   │   ├── api.js                # REST API client
│   │   ├── main.jsx
│   │   └── styles.css            # Responsive interface styles
│   ├── package.json
│   ├── package-lock.json         # Locked frontend dependencies
│   └── .env.example
├── .gitignore
└── README.md

```

## Pipeline description for the assignment

The browser captures microphone audio and sends it to a Pipecat backend over SmallWebRTC. Pipecat streams the audio through ElevenLabs Realtime STT, passes the transcript to Gemini for conversation and tool selection, and sends the response to ElevenLabs TTS for playback. When the caller requests an appointment action, Gemini invokes Python tools that validate the caller's spoken and confirmed phone number, check or update the SQLite database, and return the result to the conversation. The dashboard reads the same database and displays appointment changes alongside the live transcript.

## Deployment

This repository is designed to run locally for the assignment demonstration. A public deployment is optional; the assignment submission asks for the GitHub repository, a short recording of the running application, and a pipeline description. The browser voice pipeline requires reachable backend services, valid provider credentials, and working WebRTC connectivity, so deploying it is a separate hosting/networking task rather than a prerequisite for the local demo.
