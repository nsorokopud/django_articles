import {
  formatRelativeTime,
  intVal,
  postJSON,
  safeInternalPath,
} from './utils.js';
import { showToast } from './toasts.js';

const INBOX_PAGE_SIZE = 50;
const NOTIFICATIONS_LIST_PATH = '/notifications/list/';
const UNREAD_COUNT_PATH = '/notifications/unread_count/';
const UNREAD_COUNT_SYNC_THROTTLE_MS = 2000;
const RELATIVE_TIME_REFRESH_INTERVAL_MS = 30 * 1000;

let inboxOldestCursor = null;
let lastUnreadSyncMs = 0;
let relativeTimeRefreshStarted = false;

export function initInboxUI() {
  initInboxUnreadBadge();
  setupInboxModalLoading();
  startRelativeTimeRefresh();
}

export function onNotificationReceived(n) {
  showToast({
    id: n.id,
    title: n.title,
    body: n.body,
    timestamp: n.timestamp,
    lastEventAt: n.last_event_at || n.timestamp,
    link: n.payload?.link || n.payload?.url || null,
    markReadOnClick: true,
  });

  if (n.is_new_unread) {
    adjustUnreadBadgeCountBy(1);
  }

  if (isInboxModalOpen()) {
    prependInboxItem({
      id: n.id,
      title: n.title,
      body: n.body,
      payload: n.payload || {},
      timestamp: n.timestamp,
      last_event_at: n.last_event_at || n.timestamp,
      is_read: false,
    });
  }
}

export function onNotificationDigestReceived() {
  showToast({
    id: null,
    title: 'New Notifications',
    body: 'You have new notifications. Check your inbox.',
    timestamp: new Date().toISOString(),
    link: null,
    markReadOnClick: false,
  });

  refreshUnreadCount();

  if (isInboxModalOpen()) {
    loadInitialInboxPage();
  }
}

function setupInboxModalLoading() {
  const modalEl = document.getElementById('modal');
  if (!modalEl) return;

  modalEl.addEventListener('shown.bs.modal', async () => {
    await refreshUnreadCount();
    await loadInitialInboxPage();
  });
}

async function refreshUnreadCount() {
  const now = Date.now();
  if (now - lastUnreadSyncMs < UNREAD_COUNT_SYNC_THROTTLE_MS) return;
  lastUnreadSyncMs = now;

  const res = await fetch(`${location.origin}${UNREAD_COUNT_PATH}`, {
    credentials: 'same-origin',
  });
  if (!res.ok) return;

  const data = await res.json();
  if (data && typeof data.unread === 'number') {
    setUnreadBadgeCount(data.unread);
  }
}

async function loadInitialInboxPage() {
  setInboxLoading(true);

  const res = await fetch(
    `${location.origin}${NOTIFICATIONS_LIST_PATH}?limit=${INBOX_PAGE_SIZE}`,
    { credentials: 'same-origin' },
  );

  setInboxLoading(false);
  if (!res.ok) return;

  const data = await res.json();

  renderInboxItems(data.items, { mode: 'replace' });

  inboxOldestCursor = normalizeCursor(data.next_before_cursor);

  updateLoadMoreButton(data.has_more);
}

async function loadOlderNotifications() {
  if (!inboxOldestCursor) return;

  const url = new URL(`${location.origin}${NOTIFICATIONS_LIST_PATH}`);
  url.searchParams.set('limit', String(INBOX_PAGE_SIZE));
  url.searchParams.set('before_last_event_at', inboxOldestCursor.lastEventAt);
  url.searchParams.set('before_id', String(inboxOldestCursor.id));

  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) return;

  const data = await res.json();
  renderInboxItems(data.items, { mode: 'append' });

  inboxOldestCursor = normalizeCursor(data.next_before_cursor);

  updateLoadMoreButton(data.has_more);
}

function updateLoadMoreButton(hasMore) {
  const btn = document.getElementById('notificationsLoadMore');
  if (!btn) return;

  btn.classList.toggle('d-none', !hasMore);
  if (!hasMore) return;

  btn.onclick = async () => {
    btn.disabled = true;
    try {
      await loadOlderNotifications();
    } finally {
      btn.disabled = false;
    }
  };
}

function renderInboxItems(items, { mode } = { mode: 'replace' }) {
  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  if (mode === 'replace') container.innerHTML = '';

  if ((!items || items.length === 0) && container.children.length === 0) {
    setInboxEmpty(true);
    return;
  }

  setInboxEmpty(false);

  const fragment = document.createDocumentFragment();

  for (const n of items) {
    if (mode !== 'replace') {
      const existing = document.getElementById(`notification-${n.id}`);
      if (existing) existing.remove();
    }
    fragment.appendChild(createInboxNotificationElement(n));
  }

  container.appendChild(fragment);
}

function prependInboxItem(n) {
  setInboxEmpty(false);

  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  const existing = document.getElementById(`notification-${n.id}`);
  const nextEl = createInboxNotificationElement(n);

  if (existing) {
    existing.remove();
  }
  container.prepend(nextEl);
}

function setInboxLoading(isLoading) {
  const loading = document.getElementById('notificationsLoading');
  if (!loading) return;
  loading.classList.toggle('d-none', !isLoading);
}

function setInboxEmpty(isEmpty) {
  const container = document.getElementById('notificationsContainer');
  const empty = document.getElementById('notificationsEmpty');

  if (empty) empty.classList.toggle('d-none', !isEmpty);
  if (container) container.classList.toggle('d-none', isEmpty);
}

function isInboxModalOpen() {
  const modalEl = document.getElementById('modal');
  return modalEl && modalEl.classList.contains('show');
}

function initInboxUnreadBadge() {
  const meta = document.getElementById('inboxUnreadCount');
  if (!meta) return;
  const n = intVal(meta.dataset.count, 0);
  setUnreadBadgeCount(n);
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

function adjustUnreadBadgeCountBy(delta) {
  const badge = document.getElementById('notificationCounter');
  if (!badge) return;

  const currentText = (badge.textContent || '0').trim();
  const current = currentText === '999+' ? 999 : intVal(currentText, 0);

  setUnreadBadgeCount(current + delta);
}

function applyUnreadCountFromResponse(data) {
  if (data && typeof data.unread_notifications_count !== 'undefined') {
    setUnreadBadgeCount(data.unread_notifications_count);
  }
}

function createInboxNotificationElement(n) {
  const link = safeInternalPath(n.payload?.link || n.payload?.url || null);

  const notification = createElement('div', 'notification');
  notification.id = `notification-${n.id}`;
  if (n.is_read) notification.classList.add('read');

  attachNotificationHoverHandlers(notification);
  attachNotificationClickHandler(notification, n, link);

  notification.append(
    createNotificationMain(n),
    createDeleteButton(notification, n),
  );
  return notification;
}

function attachNotificationHoverHandlers(notification) {
  notification.addEventListener('touchstart', () =>
    notification.classList.add('notification-hover'),
  );
  notification.addEventListener('touchend', () =>
    notification.classList.remove('notification-hover'),
  );
}

function attachNotificationClickHandler(notification, n, link) {
  notification.addEventListener('click', async () => {
    if (notification.dataset.busy === '1') return;
    notification.dataset.busy = '1';

    const hasLink = !!link;

    try {
      if (!n.is_read) {
        const data = await postJSON(`/notification/${n.id}/read/`);

        if (data) {
          applyUnreadCountFromResponse(data);
          notification.classList.add('read');
          n.is_read = true;
        }
      }

      if (hasLink) {
        window.location.assign(link);
        return;
      }
    } catch (err) {
      console.warn('Failed to mark notification as read', err);

      if (hasLink) {
        window.location.assign(link);
        return;
      }
    } finally {
      if (!hasLink) {
        notification.dataset.busy = '0';
      }
    }
  });
}

function createNotificationMain(n) {
  const notificationMain = createElement('div', 'notification-main');
  const circle = createElement('div', 'rounded-circle');
  const content = createElement('div', 'notification-content');
  const msg = createElement('div', 'notification-message');

  msg.textContent = n.body || '';
  content.append(createNotificationHeader(n), msg);

  notificationMain.append(circle, content);
  return notificationMain;
}

function createNotificationHeader(n) {
  const header = createElement('h6', 'notification-header');
  const title = createElement('span', 'notification-title', 'me-3');
  const time = createElement('span', 'notification-time');

  title.textContent = n.title || '';

  time.dataset.relativeTimestamp = n.last_event_at || n.timestamp;
  time.innerText = formatRelativeTime(time.dataset.relativeTimestamp);

  header.append(title, time);
  return header;
}

function createDeleteButton(notification, n) {
  const del = createElement(
    'button',
    'notification-delete-button',
    'btn',
    'btn-danger',
    'p-1',
  );
  del.innerText = 'Delete';

  del.addEventListener('click', async (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const data = await postJSON(`/notification/${n.id}/delete/`);
    if (!data) return;

    notification.remove();
    applyUnreadCountFromResponse(data);
    updateEmptyUIIfInboxEmpty();
  });

  return del;
}

function createElement(tagName, ...classNames) {
  const el = document.createElement(tagName);
  if (classNames.length) el.classList.add(...classNames);
  return el;
}

function refreshRelativeTimeElements() {
  const elements = document.querySelectorAll('[data-relative-timestamp]');
  elements.forEach((el) => {
    const ts = el.dataset.relativeTimestamp;
    if (!ts) return;
    el.innerText = formatRelativeTime(ts);
  });
}

function startRelativeTimeRefresh() {
  if (relativeTimeRefreshStarted) return;
  relativeTimeRefreshStarted = true;

  refreshRelativeTimeElements();
  setInterval(refreshRelativeTimeElements, RELATIVE_TIME_REFRESH_INTERVAL_MS);
}

function updateEmptyUIIfInboxEmpty() {
  const container = document.getElementById('notificationsContainer');
  if (!container || container.children.length > 0) return;

  setInboxEmpty(true);
}

function normalizeCursor(cursor) {
  if (!cursor || !cursor.last_event_at || cursor.id == null) return null;

  const id = Number(cursor.id);
  const ts = Date.parse(cursor.last_event_at);

  if (!Number.isFinite(id) || id <= 0) return null;
  if (!Number.isFinite(ts)) return null;

  return { lastEventAt: cursor.last_event_at, id };
}
