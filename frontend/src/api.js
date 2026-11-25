const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:7860').replace(/\/$/, '');

async function request(path) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  health: () => request('/api/health'),
  doctors: () => request('/api/doctors'),
  doctorSlots: (doctorId, date) => request(`/api/doctors/${doctorId}/slots${date ? `?date=${encodeURIComponent(date)}` : ''}`),
  appointments: () => request('/api/appointments'),
};

export const PIPECAT_URL = (import.meta.env.VITE_PIPECAT_URL || 'http://localhost:7860').replace(/\/$/, '');

export function formatAppointmentDate(value) {
  if (!value) return 'Date to be confirmed';
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', weekday: 'short' }).format(date);
}

export function maskPhone(value) {
  const digits = String(value || '').replace(/\D/g, '');
  return digits.length >= 4 ? `+91 ••••• ${digits.slice(-4)}` : 'Phone not available';
}
