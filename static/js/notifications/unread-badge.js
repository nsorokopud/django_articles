import { intVal } from './utils.js';

const UNREAD_COUNT_PATH = '/notifications/unread_count/';
const UNREAD_COUNT_REFRESH_THROTTLE_MS = 2000;

let lastUnreadRefreshMs = 0;

export async function refreshUnreadCount() {
  const now = Date.now();
  if (now - lastUnreadRefreshMs < UNREAD_COUNT_REFRESH_THROTTLE_MS) return;
  lastUnreadRefreshMs = now;

  const res = await fetch(`${location.origin}${UNREAD_COUNT_PATH}`, {
    credentials: 'same-origin',
  });
  if (!res.ok) return;

  const data = await res.json();
  if (data && typeof data.unread === 'number') {
    setUnreadBadgeCount(data.unread);
  }
}

export function adjustUnreadBadgeCountBy(delta) {
  const badge = document.getElementById('notificationCounter');
  if (!badge) return;

  const currentText = (badge.textContent || '0').trim();
  const current = currentText === '999+' ? 999 : intVal(currentText, 0);

  setUnreadBadgeCount(current + delta);
}

export function applyUnreadBadgeCountFromResponse(data) {
  if (data && typeof data.unread_notifications_count !== 'undefined') {
    setUnreadBadgeCount(data.unread_notifications_count);
  }
}

function setUnreadBadgeCount(unreadCount) {
  const badge = document.getElementById('notificationCounter');
  if (!badge) return;

  const n = intVal(unreadCount, 0);

  if (n <= 0) {
    badge.textContent = '0';
    badge.classList.add('invisible');
    return;
  }

  badge.classList.remove('invisible');
  badge.textContent = n > 999 ? '999+' : String(n);
}
