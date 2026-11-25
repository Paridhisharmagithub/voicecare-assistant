import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  ArrowRight,
  CalendarCheck,
  CalendarDays,
  Check,
  ChevronDown,
  Clock3,
  Headphones,
  HeartPulse,
  Mic,
  MicOff,
  Phone,
  PhoneOff,
  Search,
  ShieldCheck,
  Stethoscope,
  UserRound,
  Volume2,
  VolumeX,
  Wifi,
  X,
} from 'lucide-react';
import { PipecatClient } from '@pipecat-ai/client-js';
import { SmallWebRTCTransport } from '@pipecat-ai/small-webrtc-transport';
import { api, formatAppointmentDate, maskPhone, PIPECAT_URL } from './api.js';

const PAGE_IDS = ['assistant', 'doctors', 'appointments', 'availability'];
const PAGE_COPY = {
  assistant: {
    title: 'Appointments, made conversational.',
    subtitle: 'Talk to your clinic assistant to book, check or cancel an appointment.',
  },
  doctors: {
    title: 'Meet the people behind your care.',
    subtitle: 'Explore the clinic team, their specialties and upcoming appointment times.',
  },
  appointments: {
    title: 'Your appointments.',
    subtitle: 'A clear view of the appointments recorded by your clinic assistant.',
  },
  availability: {
    title: 'Find a time that works.',
    subtitle: 'Browse upcoming availability by doctor. Reservations are confirmed by voice.',
  },
};

function formatDuration(seconds) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, '0');
  const remainder = (seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
}

function formatToday() {
  return new Intl.DateTimeFormat('en-IN', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  }).format(new Date());
}

function formatDateTime(value) {
  if (!value) return 'No upcoming time listed';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'No upcoming time listed';
  return new Intl.DateTimeFormat('en-IN', {
    weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  }).format(date);
}

function initials(name = '') {
  return name.replace(/^Dr\.\s*/i, '').split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toUpperCase();
}

function localDateValue(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function DoctorAvatar({ doctor, large = false }) {
  return (
    <div className={`doctor-avatar${large ? ' doctor-avatar--large' : ''}`} aria-hidden="true">
      {doctor.initials || initials(doctor.name)}
    </div>
  );
}

function AppointmentCard({ appointment }) {
  const date = new Date(`${appointment.date}T12:00:00`);
  const isBooked = appointment.status === 'booked';
  return (
    <article className="appointment-card">
      <div className="appointment-date">
        <strong>{Number.isNaN(date.getTime()) ? '—' : date.getDate()}</strong>
        <span>{Number.isNaN(date.getTime()) ? 'Date' : new Intl.DateTimeFormat('en-IN', { month: 'short' }).format(date)}</span>
      </div>
      <div className="appointment-card-main">
        <div className="appointment-title-row">
          <h3>{appointment.doctor_name}</h3>
          <span className={`status-badge ${isBooked ? 'confirmed' : 'cancelled'}`}>
            {isBooked ? <Check size={12} /> : <X size={12} />}
            {isBooked ? 'Confirmed' : 'Cancelled'}
          </span>
        </div>
        <p>{appointment.speciality || 'Consultation'} · {maskPhone(appointment.phone_number)}</p>
        <div className="appointment-meta">
          <span><CalendarDays size={14} /> {formatAppointmentDate(appointment.date)}</span>
          <span><Clock3 size={14} /> {appointment.time}</span>
          {appointment.reference && <span className="appointment-reference">Ref. {appointment.reference}</span>}
        </div>
      </div>
    </article>
  );
}

function App() {
  const [activePage, setActivePage] = useState(() => {
    const requested = window.location.hash.replace('#', '').toLowerCase();
    return PAGE_IDS.includes(requested) ? requested : 'assistant';
  });
  const [health, setHealth] = useState(null);
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [expandedDoctor, setExpandedDoctor] = useState(null);
  const [doctorSlots, setDoctorSlots] = useState({});
  const [loadingSlots, setLoadingSlots] = useState(null);
  const [doctorSearch, setDoctorSearch] = useState('');
  const [appointmentFilter, setAppointmentFilter] = useState('booked');
  const [availabilityDoctorId, setAvailabilityDoctorId] = useState('');
  const [availabilityDate, setAvailabilityDate] = useState('');
  const [availabilitySlots, setAvailabilitySlots] = useState([]);
  const [availabilityLoading, setAvailabilityLoading] = useState(false);
  const [availabilityReload, setAvailabilityReload] = useState(0);
  const [availabilityError, setAvailabilityError] = useState('');
  const [callStatus, setCallStatus] = useState('idle');
  const [callScreenOpen, setCallScreenOpen] = useState(false);
  const [callScreenPhase, setCallScreenPhase] = useState('idle');
  const [callError, setCallError] = useState('');
  const [muted, setMuted] = useState(false);
  const [speakerMuted, setSpeakerMuted] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [transcript, setTranscript] = useState([]);
  const [dataError, setDataError] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const clientRef = useRef(null);
  const audioRef = useRef(null);
  const phoneTranscriptRef = useRef(null);
  const callStartedAtRef = useRef(null);

  const navigate = useCallback((page) => {
    if (!PAGE_IDS.includes(page)) return;
    setActivePage(page);
    const hash = `#${page}`;
    if (window.location.hash !== hash) window.history.pushState({ page }, '', hash);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  useEffect(() => {
    const syncPage = () => {
      const requested = window.location.hash.replace('#', '').toLowerCase();
      setActivePage(PAGE_IDS.includes(requested) ? requested : 'assistant');
    };
    window.addEventListener('popstate', syncPage);
    window.addEventListener('hashchange', syncPage);
    return () => {
      window.removeEventListener('popstate', syncPage);
      window.removeEventListener('hashchange', syncPage);
    };
  }, []);

  const loadData = useCallback(async () => {
    const [healthResult, doctorResult, appointmentResult] = await Promise.allSettled([
      api.health(), api.doctors(), api.appointments(),
    ]);
    const failures = [];
    if (healthResult.status === 'fulfilled') setHealth(healthResult.value);
    else failures.push('backend health');
    if (doctorResult.status === 'fulfilled') setDoctors(doctorResult.value.doctors || []);
    else failures.push('doctors');
    if (appointmentResult.status === 'fulfilled') setAppointments(appointmentResult.value.appointments || []);
    else failures.push('appointments');
    setDataError(failures.length ? `Could not load ${failures.join(', ')}. Check that the backend is running.` : '');
    setLastUpdated(new Date());
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (callStatus !== 'connected') return undefined;
    const timer = window.setInterval(() => {
      if (callStartedAtRef.current) setElapsed(Math.floor((Date.now() - callStartedAtRef.current) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [callStatus]);

  useEffect(() => {
    if (!callScreenOpen || !phoneTranscriptRef.current) return;
    phoneTranscriptRef.current.scrollTop = phoneTranscriptRef.current.scrollHeight;
  }, [transcript, callScreenOpen]);

  useEffect(() => {
    if (!callScreenOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = previousOverflow; };
  }, [callScreenOpen]);

  useEffect(() => () => {
    if (clientRef.current) {
      Promise.resolve(clientRef.current.disconnect()).catch(() => {});
      clientRef.current = null;
    }
  }, []);

  const appendTranscript = (role, text) => {
    if (!text || !String(text).trim()) return;
    setTranscript((current) => [...current, {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      role,
      text: String(text).trim(),
      time: new Date(),
    }]);
  };

  const startCall = async () => {
    if (clientRef.current || callStatus === 'connecting' || callStatus === 'connected') return;
    setCallError('');
    setTranscript([]);
    setElapsed(0);
    setMuted(false);
    setSpeakerMuted(false);
    setCallStatus('connecting');
    setCallScreenOpen(true);
    setCallScreenPhase('connecting');

    const client = new PipecatClient({
      transport: new SmallWebRTCTransport(),
      enableMic: true,
      enableCam: false,
      callbacks: {
        onConnected: () => {
          callStartedAtRef.current = Date.now();
          setCallStatus('connected');
          setCallScreenPhase('connected');
        },
        onBotReady: () => {
          callStartedAtRef.current = callStartedAtRef.current || Date.now();
          setCallStatus('connected');
          setCallScreenPhase('connected');
        },
        onDisconnected: () => {
          setCallStatus('idle');
          setCallScreenPhase('ended');
          setMuted(false);
          setSpeakerMuted(false);
          callStartedAtRef.current = null;
          clientRef.current = null;
          loadData();
        },
        onError: (error) => {
          const message = typeof error === 'string' ? error : (error?.message || 'A voice service reported an error.');
          setCallError(message);
          // Provider errors (for example, TTS failure) can occur while WebRTC
          // remains connected and STT continues. Only onDisconnected ends the call.
          setCallStatus((current) => current === 'connected' ? 'connected' : 'error');
        },
        onUserTranscript: (data) => {
          if (data?.final) appendTranscript('caller', data.text);
        },
        onBotTranscript: (data) => {
          if (!data?.text || !String(data.text).trim()) return;
          setTranscript((current) => {
            const next = [...current];
            const last = next[next.length - 1];
            if (last?.role === 'assistant' && last.streaming) {
              next[next.length - 1] = { ...last, text: last.text + data.text };
            } else {
              next.push({
                id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                role: 'assistant',
                text: String(data.text),
                time: new Date(),
                streaming: true,
              });
            }
            return next;
          });
        },
        onBotStoppedSpeaking: () => {
          setTranscript((current) => {
            if (!current.length) return current;
            const next = [...current];
            const last = next[next.length - 1];
            if (last?.role === 'assistant' && last.streaming) next[next.length - 1] = { ...last, streaming: false };
            return next;
          });
        },
        onTrackStarted: (track, participant) => {
          if (track.kind === 'audio' && !participant?.local && audioRef.current) {
            audioRef.current.srcObject = new MediaStream([track]);
            audioRef.current.play().catch(() => {});
          }
        },
        onTrackStopped: (track) => {
          if (track?.kind === 'audio' && audioRef.current) audioRef.current.srcObject = null;
        },
      },
    });

    clientRef.current = client;
    try {
      await client.initDevices();
      await client.startBotAndConnect({
        endpoint: `${PIPECAT_URL}/start`,
        requestData: { transport: 'webrtc', enableDefaultIceServers: true },
      });
    } catch (error) {
      try { await client.disconnect(); } catch { /* connection may not have started */ }
      if (clientRef.current === client) clientRef.current = null;
      setCallError(error?.message || 'Could not start the call. Check microphone permission and backend status.');
      setCallStatus('error');
      setCallScreenPhase('error');
    }
  };

  const endCall = async () => {
    const client = clientRef.current;
    const callWasActive = Boolean(client) || ['connecting', 'connected'].includes(callStatus);
    clientRef.current = null;
    if (callWasActive) {
      setCallScreenOpen(true);
      setCallScreenPhase('ended');
    }
    setCallStatus('idle');
    setMuted(false);
    setSpeakerMuted(false);
    callStartedAtRef.current = null;
    if (client) {
      try { await client.disconnect(); } catch (error) { console.warn('Disconnect:', error); }
    }
    if (audioRef.current) audioRef.current.srcObject = null;
    await loadData();
  };

  const dismissCallScreen = () => {
    setCallScreenOpen(false);
    if (callScreenPhase === 'ended' || callScreenPhase === 'error') {
      setCallScreenPhase('idle');
      setCallError('');
      if (callStatus === 'error') setCallStatus('idle');
    }
  };

  const showCallScreen = () => {
    setCallScreenOpen(true);
    setCallScreenPhase(callStatus === 'connected' ? 'connected' : 'connecting');
  };

  const toggleSpeaker = () => {
    const nextMuted = !speakerMuted;
    if (audioRef.current) audioRef.current.muted = nextMuted;
    setSpeakerMuted(nextMuted);
  };

  const toggleMute = () => {
    const client = clientRef.current;
    if (!client || callStatus !== 'connected') return;
    const nextMuted = !muted;
    try {
      client.enableMic(!nextMuted);
      setMuted(nextMuted);
    } catch (error) {
      setCallError(error?.message || 'Could not change microphone state.');
    }
  };

  useEffect(() => {
    if (expandedDoctor == null || activePage !== 'doctors') return undefined;
    let active = true;
    const refreshDoctorSlots = async () => {
      try {
        const result = await api.doctorSlots(expandedDoctor);
        if (active) setDoctorSlots((current) => ({ ...current, [expandedDoctor]: result.slots || [] }));
      } catch (error) {
        if (active) setDataError(error.message || 'Could not refresh doctor availability.');
      } finally {
        if (active) setLoadingSlots(null);
      }
    };
    setLoadingSlots(expandedDoctor);
    refreshDoctorSlots();
    return () => {
      active = false;
    };
  }, [expandedDoctor, activePage]);

  useEffect(() => {
    if (!availabilityDoctorId && doctors.length) setAvailabilityDoctorId(String(doctors[0].id));
  }, [doctors, availabilityDoctorId]);

  useEffect(() => {
    if (activePage !== 'availability' || !availabilityDoctorId) return undefined;
    let active = true;
    const refreshAvailability = async () => {
      setAvailabilityLoading(true);
      setAvailabilitySlots([]);
      setAvailabilityError('');
      try {
        const result = await api.doctorSlots(availabilityDoctorId, availabilityDate || undefined);
        if (active) setAvailabilitySlots(result.slots || []);
      } catch (error) {
        if (active) setAvailabilityError(error.message || 'Could not load available times.');
      } finally {
        if (active) setAvailabilityLoading(false);
      }
    };
    refreshAvailability();
    return () => {
      active = false;
    };
  }, [activePage, availabilityDoctorId, availabilityDate, availabilityReload]);

  const filteredDoctors = useMemo(() => {
    const query = doctorSearch.trim().toLowerCase();
    if (!query) return doctors;
    return doctors.filter((doctor) => `${doctor.name} ${doctor.speciality} ${doctor.qualification}`.toLowerCase().includes(query));
  }, [doctors, doctorSearch]);

  const visibleAppointments = useMemo(() => {
    if (appointmentFilter === 'all') return appointments;
    return appointments.filter((appointment) => appointment.status === appointmentFilter);
  }, [appointments, appointmentFilter]);

  const activeAppointments = appointments.filter((item) => item.status === 'booked');
  const callOutcome = useMemo(() => {
    for (let index = transcript.length - 1; index >= 0; index -= 1) {
      const message = transcript[index];
      if (message.role !== 'assistant') continue;
      const isBooking = /\b(?:i(?:'ve| have) booked|successfully booked|appointment is confirmed|booking confirmed)\b/i.test(message.text);
      const isCancellation = /\b(?:successfully cancelled|successfully canceled|appointment has been cancelled|appointment has been canceled|your appointment is cancelled|your appointment is canceled)\b/i.test(message.text);
      const reference = message.text.match(/\bVC-\d+\b/i)?.[0] || null;
      if ((isBooking && reference) || isCancellation) {
        return { kind: isCancellation ? 'cancelled' : 'booked', reference, text: message.text };
      }
    }
    return null;
  }, [transcript]);
  const selectedAvailabilityDoctor = doctors.find((doctor) => String(doctor.id) === String(availabilityDoctorId));
  const pageCopy = PAGE_COPY[activePage];
  const callLabel = callStatus === 'connected' ? 'Call in progress' : callStatus === 'connecting' ? 'Connecting' : callStatus === 'error' ? 'Connection issue' : 'Assistant ready';

  const toggleDoctorSlots = (doctorId) => setExpandedDoctor((current) => current === doctorId ? null : doctorId);
  const showDoctorAvailability = (doctorId) => {
    setAvailabilityDoctorId(String(doctorId));
    setAvailabilityDate('');
    navigate('availability');
  };
  const clearCallError = () => {
    setCallError('');
    if (callStatus === 'error') setCallStatus('idle');
  };

  const renderCallPanel = () => (
    <article className="panel call-panel">
      <div className="panel-topline">
        <span className="section-kicker">VOICE ASSISTANT</span>
        <span className={`call-status ${callStatus}`}><span className="status-dot" />{callLabel}</span>
      </div>
      <div className="call-center">
        <div className={`call-symbol ${callStatus === 'connected' ? 'is-connected' : ''}`}>
          {callStatus === 'connected' ? <Activity size={29} strokeWidth={1.55} /> : <Phone size={28} strokeWidth={1.5} />}
        </div>
        <h2>{callStatus === 'connected' ? 'You’re speaking with VoiceCare' : callStatus === 'connecting' ? 'Connecting your call' : 'Hello. How can we help?'}</h2>
        <p>{callStatus === 'connected' ? 'The assistant is listening and ready to help.' : callStatus === 'connecting' ? 'Allow microphone access if your browser asks.' : 'Book, check or cancel a doctor appointment by voice.'}</p>
        {callStatus === 'connected' ? (
          <div className="call-clock"><span className="recording-dot" /> {formatDuration(elapsed)}</div>
        ) : (
          <div className="call-hint"><Mic size={14} /> Browser microphone · WebRTC</div>
        )}
      </div>
      {callStatus === 'connected' ? (
        <div className="call-controls">
          <button className={`control-button ${muted ? 'selected' : ''}`} onClick={toggleMute} aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}>
            {muted ? <MicOff size={18} /> : <Mic size={18} />}<span>{muted ? 'Unmute' : 'Mute'}</span>
          </button>
          <button className="end-call-button" onClick={endCall}><PhoneOff size={17} /> End call</button>
          <button className={`control-button ${speakerMuted ? 'selected' : ''}`} onClick={toggleSpeaker} aria-label={speakerMuted ? 'Unmute speaker' : 'Mute speaker'}>
            {speakerMuted ? <VolumeX size={18} /> : <Volume2 size={18} />}<span>{speakerMuted ? 'Unmute audio' : 'Speaker'}</span>
          </button>
        </div>
      ) : (
        <div className="call-actions">
          <button className="start-call-button" onClick={startCall} disabled={callStatus === 'connecting' || !health?.voice_configured}>
            <Phone size={17} /> {callStatus === 'connecting' ? 'Connecting…' : callStatus === 'error' ? 'Try again' : 'Start a call'}
          </button>
          {!health?.voice_configured && health?.status === 'ok' && (
            <span className="call-footnote">Add the provider keys in <code>backend/.env</code> to enable calling.</span>
          )}
        </div>
      )}
      {callError && <div className="inline-error"><span>{callError}</span><button onClick={clearCallError} aria-label="Dismiss error"><X size={14} /></button></div>}
    </article>
  );

  const renderTranscriptPanel = () => (
    <article className="panel transcript-panel">
      <div className="panel-heading">
        <div><span className="section-kicker">CONVERSATION</span><h2>Live transcript</h2></div>
        <span className={`live-indicator ${callStatus === 'connected' ? 'active' : ''}`}><span className="status-dot" />{callStatus === 'connected' ? 'Live' : 'Waiting'}</span>
      </div>
      <div className="transcript-list" aria-live="polite" aria-label="Conversation transcript">
        {transcript.length === 0 ? (
          <div className="transcript-empty">
            <div className="empty-icon"><Headphones size={20} /></div>
            <strong>Your conversation will appear here.</strong>
            <span>Start a call to see the caller and assistant messages in real time.</span>
          </div>
        ) : transcript.map((message) => (
          <div className={`transcript-message ${message.role}`} key={message.id}>
            <span className="message-avatar">{message.role === 'caller' ? <UserRound size={14} /> : <HeartPulse size={14} />}</span>
            <div className="message-content">
              <div className="message-meta"><strong>{message.role === 'caller' ? 'Caller' : 'VoiceCare assistant'}</strong><time>{message.time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</time></div>
              <p>{message.text}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="transcript-footer">
        <span><span className={`status-dot ${callStatus === 'connected' ? 'green' : ''}`} />{callStatus === 'connected' ? 'Listening for the next turn' : 'Transcript appears during a call'}</span>
        {transcript.length > 0 && <button onClick={() => setTranscript([])}>Clear transcript</button>}
      </div>
    </article>
  );

  const renderAssistantPage = () => (
    <>
      <section className="assistant-grid" aria-label="Voice assistant workspace">
        {renderCallPanel()}
        {renderTranscriptPanel()}
      </section>
      <section className="assistant-support-grid" aria-label="How VoiceCare works">
        <article className="panel support-card privacy-card">
          <div className="support-icon"><ShieldCheck size={19} /></div>
          <div>
            <span className="section-kicker">PRIVATE BY DESIGN</span>
            <h2>Your number is confirmed before any change.</h2>
            <p>The assistant repeats the caller’s phone number and asks for confirmation before booking or cancelling an appointment.</p>
          </div>
        </article>
        <article className="panel support-card steps-card">
          <div className="support-heading">
            <div><span className="section-kicker">WHAT THE ASSISTANT CAN DO</span><h2>Care, in a few simple steps.</h2></div>
            <HeartPulse size={19} className="muted-icon" />
          </div>
          <div className="support-steps">
            <div><span>01</span><p><strong>Find a doctor</strong><small>Explore specialties and available times.</small></p></div>
            <div><span>02</span><p><strong>Manage a visit</strong><small>Book a new slot or check existing appointments.</small></p></div>
            <div><span>03</span><p><strong>Confirm by voice</strong><small>Review details before an appointment is changed.</small></p></div>
          </div>
          <button className="inline-action" onClick={() => navigate('doctors')}>Explore the doctors <ArrowRight size={15} /></button>
        </article>
      </section>
    </>
  );

  const renderDoctorsPage = () => (
    <section className="page-section">
      <div className="page-toolbar">
        <label className="search-field">
          <Search size={17} />
          <input value={doctorSearch} onChange={(event) => setDoctorSearch(event.target.value)} placeholder="Search by doctor or specialty" aria-label="Search doctors" />
          {doctorSearch && <button onClick={() => setDoctorSearch('')} aria-label="Clear search"><X size={15} /></button>}
        </label>
        <span className="results-count">{filteredDoctors.length} {filteredDoctors.length === 1 ? 'doctor' : 'doctors'}</span>
      </div>
      {doctors.length === 0 ? (
        !dataError && <div className="panel empty-state"><div className="loading-mark" /><h2>Loading the clinic team</h2><p>Doctor information will appear here shortly.</p></div>
      ) : filteredDoctors.length ? (
        <div className="doctor-card-grid">
          {filteredDoctors.map((doctor) => (
            <article className="panel doctor-card" key={doctor.id}>
              <div className="doctor-card-header">
                <DoctorAvatar doctor={doctor} large />
                <div className="doctor-card-title"><span className="doctor-speciality">{doctor.speciality}</span><h2>{doctor.name}</h2><p>{doctor.qualification}</p></div>
              </div>
              <p className="doctor-bio">{doctor.bio || 'Available for consultations at VoiceCare Clinic.'}</p>
              <div className="doctor-facts">
                <div><span>Experience</span><strong>{doctor.experience_years ?? '—'}{doctor.experience_years != null ? ' years' : ''}</strong></div>
                <div><span>Consultation</span><strong>{doctor.consultation_fee != null ? `₹${doctor.consultation_fee}` : 'Ask clinic'}</strong></div>
              </div>
              <div className="doctor-next-slot"><Clock3 size={15} /><span>Next available</span><strong>{formatDateTime(doctor.next_available)}</strong></div>
              <div className="doctor-card-actions">
                <button className="quiet-button" onClick={() => toggleDoctorSlots(doctor.id)}>
                  <CalendarDays size={15} /> {expandedDoctor === doctor.id ? 'Hide times' : 'View times'}
                </button>
                <button className="primary-text-button" onClick={() => showDoctorAvailability(doctor.id)}>Full availability <ArrowRight size={15} /></button>
              </div>
              {expandedDoctor === doctor.id && (
                <div className="doctor-expanded-slots">
                  <div className="expanded-slots-heading">Upcoming available times</div>
                  {loadingSlots === doctor.id ? <p className="subtle-text">Loading available times…</p> : (doctorSlots[doctor.id] || []).length ? (
                    <div className="slot-chip-list">
                      {doctorSlots[doctor.id].slice(0, 6).map((slot) => <span className="slot-chip" key={slot.slot_id}>{formatAppointmentDate(slot.date)} · {slot.time}</span>)}
                    </div>
                  ) : <p className="subtle-text">No upcoming slots found for this doctor.</p>}
                </div>
              )}
            </article>
          ))}
        </div>
      ) : (
        <div className="panel empty-state"><div className="empty-icon"><Stethoscope size={21} /></div><h2>No doctors found</h2><p>Try a different name or specialty.</p><button className="quiet-button" onClick={() => setDoctorSearch('')}>Clear search</button></div>
      )}
    </section>
  );

  const renderAppointmentsPage = () => (
    <section className="page-section">
      <div className="page-toolbar appointments-toolbar">
        <div className="filter-tabs" role="group" aria-label="Filter appointments">
          <button className={appointmentFilter === 'booked' ? 'selected' : ''} onClick={() => setAppointmentFilter('booked')}>Upcoming <span>{activeAppointments.length}</span></button>
          <button className={appointmentFilter === 'all' ? 'selected' : ''} onClick={() => setAppointmentFilter('all')}>All appointments <span>{appointments.length}</span></button>
          <button className={appointmentFilter === 'cancelled' ? 'selected' : ''} onClick={() => setAppointmentFilter('cancelled')}>Cancelled <span>{appointments.filter((item) => item.status === 'cancelled').length}</span></button>
        </div>
        <span className="updated-label">{lastUpdated ? `Synced ${lastUpdated.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}` : 'Waiting for clinic data'}</span>
      </div>
      {visibleAppointments.length ? (
        <div className="appointments-page-list">
          {visibleAppointments.map((appointment) => <AppointmentCard appointment={appointment} key={appointment.id} />)}
        </div>
      ) : (
        <div className="panel empty-state appointments-empty">
          <div className="empty-icon"><CalendarCheck size={21} /></div>
          <h2>{appointmentFilter === 'cancelled' ? 'No cancelled appointments' : 'Nothing scheduled just yet'}</h2>
          <p>{appointmentFilter === 'cancelled' ? 'Cancelled visits will appear here.' : 'Start a conversation with VoiceCare to book your first visit or check an existing appointment.'}</p>
          {appointmentFilter !== 'cancelled' && <button className="primary-button" onClick={() => navigate('assistant')}><Phone size={15} /> Talk to the assistant</button>}
        </div>
      )}
      <div className="page-note"><ShieldCheck size={17} /><span>Bookings and cancellations are completed through the voice assistant after the caller’s phone number and appointment details are confirmed.</span></div>
    </section>
  );

  const renderAvailabilityPage = () => (
    <section className="page-section">
      <div className="panel availability-filters">
        <div className="field-group">
          <label htmlFor="availability-doctor">Choose a doctor</label>
          <select id="availability-doctor" value={availabilityDoctorId} onChange={(event) => setAvailabilityDoctorId(event.target.value)}>
            {doctors.map((doctor) => <option value={doctor.id} key={doctor.id}>{doctor.name} · {doctor.speciality}</option>)}
          </select>
        </div>
        <div className="field-group date-field-group">
          <label htmlFor="availability-date">Filter by date</label>
          <input id="availability-date" type="date" min={localDateValue()} value={availabilityDate} onChange={(event) => setAvailabilityDate(event.target.value)} />
        </div>
        <button className="clear-date-button" onClick={() => setAvailabilityDate('')} disabled={!availabilityDate}>Clear date</button>
      </div>

      {selectedAvailabilityDoctor && (
        <div className="availability-doctor-summary">
          <DoctorAvatar doctor={selectedAvailabilityDoctor} />
          <div><span>{selectedAvailabilityDoctor.speciality}</span><h2>{selectedAvailabilityDoctor.name}</h2><p>{selectedAvailabilityDoctor.qualification}</p></div>
          <div className="availability-fee"><span>Consultation</span><strong>{selectedAvailabilityDoctor.consultation_fee != null ? `₹${selectedAvailabilityDoctor.consultation_fee}` : 'Ask clinic'}</strong></div>
        </div>
      )}

      {!doctors.length ? (
        !dataError && <div className="panel empty-state"><div className="loading-mark" /><h2>Loading clinic availability</h2><p>Doctor schedules will appear here shortly.</p></div>
      ) : availabilityLoading && !availabilitySlots.length ? (
        <div className="panel empty-state"><div className="loading-mark" /><h2>Checking available times</h2><p>Refreshing the clinic schedule.</p></div>
      ) : availabilityError ? (
        <div className="panel empty-state"><div className="empty-icon"><Wifi size={21} /></div><h2>Could not load availability</h2><p>{availabilityError}</p><button className="quiet-button" onClick={() => setAvailabilityReload((current) => current + 1)}>Try again</button></div>
      ) : availabilitySlots.length ? (
        <div className="availability-results">
          <div className="availability-results-heading"><div><span className="section-kicker">OPEN APPOINTMENT TIMES</span><h2>{availabilitySlots.length} available {availabilitySlots.length === 1 ? 'slot' : 'slots'}</h2></div><span className="live-indicator active"><span className="status-dot" />Live schedule</span></div>
          <div className="slot-card-grid">
            {availabilitySlots.map((slot) => (
              <article className="panel available-slot-card" key={slot.slot_id}>
                <div className="slot-date-line"><CalendarDays size={16} /><span>{formatAppointmentDate(slot.date)}</span></div>
                <strong className="slot-time">{slot.time}</strong>
                <div className="slot-card-bottom"><span>{slot.consultation_fee != null ? `₹${slot.consultation_fee} consultation` : 'Consultation'}</span><span className="slot-open"><span className="status-dot" />Available</span></div>
                <button className="slot-book-button" onClick={() => navigate('assistant')}>Book by voice <ArrowRight size={14} /></button>
              </article>
            ))}
          </div>
        </div>
      ) : (
        <div className="panel empty-state"><div className="empty-icon"><CalendarDays size={21} /></div><h2>No times available</h2><p>{availabilityDate ? 'There are no open slots for this doctor on the selected date. Try another day.' : 'There are no upcoming open slots for this doctor right now. Check again shortly or choose another doctor.'}</p><button className="quiet-button" onClick={() => setAvailabilityDate('')}>Show all upcoming dates</button></div>
      )}

      <div className="page-note"><ShieldCheck size={17} /><span>To reserve a time, speak with the assistant. It will repeat your phone number and appointment details and ask for confirmation before booking.</span></div>
    </section>
  );

  const renderPage = () => {
    if (activePage === 'doctors') return renderDoctorsPage();
    if (activePage === 'appointments') return renderAppointmentsPage();
    if (activePage === 'availability') return renderAvailabilityPage();
    return renderAssistantPage();
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => navigate('assistant')} aria-label="VoiceCare home">
          <span className="brand-mark"><HeartPulse size={22} strokeWidth={1.65} /></span>
          <span><strong>voicecare</strong><small>clinic assistant</small></span>
        </button>
        <div className="sidebar-rule" />
        <p className="nav-label">WORKSPACE</p>
        <nav className="navigation" aria-label="Main navigation">
          <button className={`nav-item ${activePage === 'assistant' ? 'active' : ''}`} onClick={() => navigate('assistant')} aria-current={activePage === 'assistant' ? 'page' : undefined}><Phone size={17} /> <span>Voice assistant</span></button>
          <button className={`nav-item ${activePage === 'doctors' ? 'active' : ''}`} onClick={() => navigate('doctors')} aria-current={activePage === 'doctors' ? 'page' : undefined}><Stethoscope size={17} /> <span>Doctors</span></button>
          <button className={`nav-item ${activePage === 'appointments' ? 'active' : ''}`} onClick={() => navigate('appointments')} aria-current={activePage === 'appointments' ? 'page' : undefined}><CalendarCheck size={17} /> <span>Appointments</span></button>
          <button className={`nav-item ${activePage === 'availability' ? 'active' : ''}`} onClick={() => navigate('availability')} aria-current={activePage === 'availability' ? 'page' : undefined}><CalendarDays size={17} /> <span>Availability</span></button>
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <ShieldCheck size={17} />
            <div><strong>Private by design</strong><span>Phone number is confirmed during the call.</span></div>
          </div>
          <div className="sidebar-clinic"><span className="clinic-dot" /> Clinic demo environment</div>
        </div>
      </aside>

      <main className="main-content" id="top">
        <header className="page-header">
          <div>
            <div className="eyebrow">{formatToday()}</div>
            <h1>{pageCopy.title}</h1>
            <p>{pageCopy.subtitle}</p>
          </div>
          <div className="header-tools">
            <span className={`connection-pill ${health?.status === 'ok' ? 'online' : 'offline'}`}>
              <span className="status-dot" /> {health?.status === 'ok' ? 'Clinic online' : 'Backend offline'}
            </span>
            <div className="profile-chip"><span className="profile-initial">VC</span><span>Clinic</span><ChevronDown size={14} /></div>
          </div>
        </header>

        {['connected', 'connecting'].includes(callStatus) && activePage !== 'assistant' && (
          <div className="active-call-banner" role="status">
            <span className="recording-dot" /> <strong>{callStatus === 'connected' ? 'VoiceCare call in progress' : 'Connecting to VoiceCare'}</strong>
            <button onClick={() => { navigate('assistant'); showCallScreen(); }}>Return to call</button>
            <button className="active-call-end" onClick={endCall}><PhoneOff size={14} /> End call</button>
          </div>
        )}

        {dataError && (
          <div className="notice notice-warning" role="status">
            <Wifi size={16} /><span>{dataError}</span><button onClick={loadData}>Retry</button>
          </div>
        )}

        {renderPage()}
        {callScreenOpen && (
          <div className="call-overlay">
            <section className="call-dialog" role="dialog" aria-modal="true" aria-labelledby="phone-call-title">
              <header className="call-dialog-header">
                <div className="call-dialog-brand">
                  <span className="call-dialog-brand-mark"><HeartPulse size={19} /></span>
                  <span><strong>VoiceCare Clinic</strong><small>APPOINTMENT ASSISTANT</small></span>
                </div>
                <button className="call-dialog-dismiss" onClick={dismissCallScreen} aria-label={['connected', 'connecting'].includes(callStatus) ? 'Minimize call window' : 'Close call window'}>
                  {['connected', 'connecting'].includes(callStatus) ? 'Minimize' : 'Close'} <X size={15} />
                </button>
              </header>

              <div className={`phone-call-state ${callScreenPhase}`} aria-live="polite">
                <div className={`phone-call-avatar ${callScreenPhase === 'connected' ? 'is-live' : ''}`}>
                  {callScreenPhase === 'ended' ? <PhoneOff size={29} /> : callScreenPhase === 'error' ? <Wifi size={28} /> : <HeartPulse size={31} />}
                </div>
                <span className={`phone-call-status ${callScreenPhase}`}><span className="status-dot" />{callScreenPhase === 'connecting' ? 'CONNECTING' : callScreenPhase === 'connected' ? 'LIVE CALL' : callScreenPhase === 'ended' ? 'CALL ENDED' : 'CONNECTION ISSUE'}</span>
                <h2 id="phone-call-title">{callScreenPhase === 'connecting' ? 'Connecting to VoiceCare' : callScreenPhase === 'connected' ? 'You’re speaking with VoiceCare' : callScreenPhase === 'ended' ? 'Your call has ended' : 'We couldn’t connect your call'}</h2>
                <div className="phone-caller-identity"><strong>Browser caller</strong><span>VoiceCare Clinic · Appointment assistant</span></div>
                {callScreenPhase === 'connected' || callScreenPhase === 'ended' ? (
                  <div className="phone-call-duration"><span className={callScreenPhase === 'connected' ? 'recording-dot' : 'duration-dot'} />{formatDuration(elapsed)}</div>
                ) : (
                  <p className="phone-call-hint">{callScreenPhase === 'connecting' ? 'Preparing your microphone and secure audio connection…' : (callError || 'Check your microphone permission and backend connection, then try again.')}</p>
                )}
              </div>

              {callOutcome && (
                <div className={`phone-outcome-card ${callOutcome.kind}`} role="status">
                  <span className="phone-outcome-icon"><Check size={15} /></span>
                  <div><strong>{callOutcome.kind === 'booked' ? 'Appointment booked' : 'Appointment cancelled'}</strong>
                    {callOutcome.reference && <small>Reference {callOutcome.reference}</small>}
                    <p>{callOutcome.text}</p>
                  </div>
                </div>
              )}

              <section className="phone-transcript-section" aria-label="Live call transcript">
                <div className="phone-transcript-heading"><div><span className="section-kicker">LIVE CONVERSATION</span><h3>Call transcript</h3></div><span className={`live-indicator ${callScreenPhase === 'connected' ? 'active' : ''}`}><span className="status-dot" />{callScreenPhase === 'connected' ? 'Listening' : callScreenPhase === 'connecting' ? 'Starting' : 'Ended'}</span></div>
                <div className="phone-transcript-list" ref={phoneTranscriptRef} aria-live="polite">
                  {transcript.length === 0 ? (
                    <div className="phone-transcript-empty"><Headphones size={19} /><span>{callScreenPhase === 'connecting' ? 'Your conversation will appear here once connected.' : 'No conversation was recorded.'}</span></div>
                  ) : transcript.map((message) => (
                    <div className={`transcript-message ${message.role}`} key={`phone-${message.id}`}>
                      <span className="message-avatar">{message.role === 'caller' ? <UserRound size={13} /> : <HeartPulse size={13} />}</span>
                      <div className="message-content"><div className="message-meta"><strong>{message.role === 'caller' ? 'You' : 'VoiceCare'}</strong><time>{message.time.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}</time></div><p>{message.text}</p></div>
                    </div>
                  ))}
                </div>
              </section>

              {callScreenPhase === 'connected' ? (
                <div className="phone-call-controls">
                  <button className={`phone-control-button ${muted ? 'selected' : ''}`} onClick={toggleMute} aria-label={muted ? 'Unmute microphone' : 'Mute microphone'}>{muted ? <MicOff size={19} /> : <Mic size={19} />}<span>{muted ? 'Unmute' : 'Mute'}</span></button>
                  <button className="phone-end-call-button" onClick={endCall}><PhoneOff size={18} />End call</button>
                  <button className={`phone-control-button ${speakerMuted ? 'selected' : ''}`} onClick={toggleSpeaker} aria-label={speakerMuted ? 'Turn speaker on' : 'Turn speaker off'}>{speakerMuted ? <VolumeX size={19} /> : <Volume2 size={19} />}<span>{speakerMuted ? 'Speaker off' : 'Speaker'}</span></button>
                </div>
              ) : callScreenPhase === 'connecting' ? (
                <div className="phone-connecting-footer"><span className="loading-mark" />Please allow microphone access when prompted.</div>
              ) : callScreenPhase === 'error' ? (
                <div className="phone-ended-actions"><button className="phone-end-call-button" onClick={startCall}><Phone size={16} />Try again</button><button className="phone-close-button" onClick={dismissCallScreen}>Close</button></div>
              ) : (
                <div className="phone-ended-actions"><span>Thank you for contacting VoiceCare.</span><button className="phone-close-button" onClick={dismissCallScreen}>Close call window</button></div>
              )}
              <footer className="phone-dialog-footer"><ShieldCheck size={14} /><span>Your phone number is confirmed during the conversation before an appointment is changed.</span></footer>
            </section>
          </div>
        )}
        <audio ref={audioRef} autoPlay playsInline className="visually-hidden" />
        <footer className="page-footer"><span>VoiceCare · Clinic assistant</span><span>Mock clinic data for demonstration only</span></footer>
      </main>
    </div>
  );
}

export default App;
