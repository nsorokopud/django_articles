export function intVal(v, fallback = 0) {
  const n = parseInt(v ?? '', 10);
  return Number.isFinite(n) ? n : fallback;
}

export async function postJSON(path, { keepalive = false } = {}) {
  try {
    const res = await fetch(`${location.origin}${path}`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': Cookies.get('csrftoken') },
      ...(keepalive ? { keepalive: true } : {}),
    });

    if (!res.ok) return null;

    try {
      return await res.json();
    } catch {
      return null;
    }
  } catch {
    return null;
  }
}
