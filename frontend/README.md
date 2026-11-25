# VoiceCare Frontend

Updated multi-page React frontend for the VoiceCare voice appointment assistant. This package contains **only the frontend**; it does not replace or modify your existing backend.


## What's updated

- Sidebar items now open separate views instead of scrolling through one long dashboard.
- **Voice assistant:** browser call controls and live transcript, using the existing Pipecat/WebRTC connection.
- **Doctors:** searchable doctor directory with specialties, qualifications, consultation fees, experience, and expandable upcoming times.
- **Appointments:** upcoming, all, and cancelled appointment views backed by the existing appointments API.
- **Availability:** choose a doctor, optionally filter by date, and view open slots refreshed from the backend. Booking remains voice-confirmed through the assistant.
- Browser back/forward navigation is supported. The audio element stays mounted while changing pages so an active call is not interrupted by navigation.
- Responsive layout for desktop, tablet, and mobile.

## Install and run

Keep this `frontend` folder alongside your existing `backend` folder. From this folder, run:

```bash
npm install
npm run dev
```

Open `http://localhost:5173`.

The frontend expects the existing backend at `http://localhost:7860`. For a different local backend URL, copy `.env.example` to `.env` and update:

```dotenv
VITE_API_BASE_URL=http://localhost:7860
VITE_PIPECAT_URL=http://localhost:7860
```

Do not put ElevenLabs or Gemini provider keys in this frontend. Keep those secrets in your existing `backend/.env` file.

## Updating an existing project

1. Stop the frontend dev server with `Ctrl+C`.
2. Extract this ZIP into the existing VoiceCare project root (the folder that contains `backend`).
3. Merge the ZIP's `frontend` folder into your existing `frontend` folder and replace matching source files. Do not delete the existing folder; keep any local `.env` and `node_modules` folders. Do not replace or delete `backend`.
4. Reopen a terminal in `frontend` and run `npm run dev`. Run `npm install` only if the frontend reports that a dependency is missing.

The ZIP includes `.env.example`, not your local `.env`; keep your existing `frontend/.env` if you created one.
