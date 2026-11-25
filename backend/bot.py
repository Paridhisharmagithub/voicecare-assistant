from __future__ import annotations

from loguru import logger

from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.runner.run import app, main
from pipecat.runner.utils import create_transport
from pipecat.services.elevenlabs.stt import CommitStrategy, ElevenLabsRealtimeSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.workers.runner import WorkerRunner

from app.api import register_api_routes
from app.config import settings
from app.seed import init_database
from app.voice_prompt import build_system_prompt
from app.voice_tools import CallState, build_voice_tools


# Pipecat's development runner owns this FastAPI application and its /start route.
# The clinic's dashboard API routes are mounted on the same server.
register_api_routes(app)
init_database()


async def bot(runner_args) -> None:
    """Create one isolated voice pipeline and caller state for each browser call."""
    missing = [
        name
        for name, value in (
            ("ELEVENLABS_API_KEY", settings.elevenlabs_api_key),
            ("ELEVENLABS_VOICE_ID", settings.elevenlabs_voice_id),
            ("GOOGLE_API_KEY", settings.google_api_key),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Voice services are not configured. Copy backend/.env.example to backend/.env "
            f"and set: {', '.join(missing)}"
        )

    transport = await create_transport(
        runner_args,
        {
            "webrtc": lambda: TransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
            )
        },
    )

    # Use ElevenLabs VAD to commit a turn after 0.8 seconds of silence.
    # This is a latency/accuracy compromise; increase to 1.0-1.2 seconds if
    # callers' phone numbers are being split when they pause between digit groups.
    stt = ElevenLabsRealtimeSTTService(
        api_key=settings.elevenlabs_api_key,
        commit_strategy=CommitStrategy.VAD,
        settings=ElevenLabsRealtimeSTTService.Settings(
            model="scribe_v2_realtime",
            vad_silence_threshold_secs=0.8,
            vad_threshold=0.4,
            min_speech_duration_ms=100,
            min_silence_duration_ms=100,
            keyterms=[
                "VoiceCare Clinic",
                "Dr. Ananya Sharma",
                "Dr. Kabir Shah",
                "Dr. Priya Nair",
                "Dr. Rohan Mehta",
            ],
        ),
    )

    llm = GoogleLLMService(
        api_key=settings.google_api_key,
        settings=GoogleLLMService.Settings(
            model=settings.gemini_model,
            system_instruction=build_system_prompt(),
            max_tokens=256,
        ),
    )

    tts = ElevenLabsTTSService(
        api_key=settings.elevenlabs_api_key,
        settings=ElevenLabsTTSService.Settings(
            model=settings.elevenlabs_tts_model,
            voice=settings.elevenlabs_voice_id,
            stability=0.62,
            similarity_boost=0.82,
            speed=1.0,
        ),
    )

    call_state = CallState()
    context = LLMContext(tools=build_voice_tools(call_state))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi) -> None:
        context.add_message(
            {
                "role": "developer",
                "content": (
                    f"A caller has connected to {settings.clinic_name}. Greet them in one short, "
                    "friendly sentence and ask how you can help with a doctor appointment. "
                    "When the caller wants to check availability, book, or cancel an appointment, "
                    "collect their mobile number and verify it BEFORE calling any availability "
                    "or appointment tool. Do not call check_doctor_availability, "
                    "list_my_appointments, prepare_appointment, or cancellation tools until "
                    "confirm_phone_number has returned verified=true. Ask for the number only "
                    "after the caller expresses an appointment-related intent; do not ask again "
                    "once it has been verified. Keep spoken responses concise and ask one "
                    "question at a time."
                ),
            }
        )
        await worker.queue_frames([LLMRunFrame()])


    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client) -> None:
        logger.info("VoiceCare browser call disconnected")
        await runner.cancel()

    await runner.run()


if __name__ == "__main__":
    main()
