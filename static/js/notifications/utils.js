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

export function safeInternalPath(value) {
  if (typeof value !== 'string') return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  // Only allow same-site absolute paths
  if (!trimmed.startsWith('/')) return null;

  // Reject protocol-relative URLs like //evil.com
  if (trimmed.startsWith('//')) return null;

  // Reject backslash variants
  if (trimmed.includes('\\')) return null;

  // Reject ASCII control characters
  if (/\p{Cc}/u.test(trimmed)) return null;

  return trimmed;
}
