import { formatRelativeTime, postJSON, safeInternalPath } from './utils.js';
import { showToast } from './toasts.js';
import {
  adjustUnreadBadgeCountBy,
  applyUnreadBadgeCountFromResponse,
  refreshUnreadCount,
} from './unread-badge.js';

const INBOX_PAGE_SIZE = 50;
const INBOX_LIST_PATH = '/notifications/list/';
const NOTIFICATION_RELATIVE_TIME_REFRESH_MS = 30_000; // every 30 seconds

let oldestNotificationCursor = null;
let relativeTimeRefreshStarted = false;

export function initInboxUI() {
  const modal = document.getElementById('modal');
  const loadMoreButton = document.getElementById('notificationsLoadMore');
  const container = document.getElementById('notificationsContainer');

  modal?.addEventListener('shown.bs.modal', async () => {
    await refreshUnreadCount();
    await loadInbox();
  });

  loadMoreButton?.addEventListener('click', async (event) => {
    const button = event.currentTarget;
    button.disabled = true;

    try {
      await loadInbox(true);
    } finally {
      button.disabled = false;
    }
  });

  container?.addEventListener('click', handleInboxClick);
  container?.addEventListener('touchstart', toggleTouchHover);
  container?.addEventListener('touchend', toggleTouchHover);
  container?.addEventListener('touchcancel', toggleTouchHover);

  startRelativeTimeRefresh();
}

export function onNotificationReceived(notification) {
  const lastEventAt = notification.last_event_at || notification.timestamp;
  const link = notification.payload?.link || notification.payload?.url || null;

  showToast({
    id: notification.id,
    title: notification.title,
    body: notification.body,
    timestamp: notification.timestamp,
    lastEventAt,
    link,
    markReadOnClick: true,
  });

  if (notification.is_new_unread) {
    adjustUnreadBadgeCountBy(1);
  }

  if (!isInboxOpen()) return;

  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  document.getElementById(`notification-${notification.id}`)?.remove();

  container.prepend(
    createNotificationElement({
      ...notification,
      payload: notification.payload || {},
      last_event_at: lastEventAt,
      is_read: false,
    }),
  );

  setInboxEmpty(false);
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

  if (isInboxOpen()) {
    loadInbox();
  }
}

async function loadInbox(append = false) {
  if (append && !oldestNotificationCursor) return;

  const loading = document.getElementById('notificationsLoading');
  if (!append) loading?.classList.remove('d-none');

  try {
    const url = new URL(INBOX_LIST_PATH, location.origin);
    url.searchParams.set('limit', INBOX_PAGE_SIZE);

    if (append) {
      url.searchParams.set(
        'before_last_event_at',
        oldestNotificationCursor.last_event_at,
      );
      url.searchParams.set('before_id', oldestNotificationCursor.id);
    }

    const response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) return;

    const data = await response.json();

    renderNotifications(data.items, append);
    oldestNotificationCursor = data.next_before_cursor || null;

    const loadMoreButton = document.getElementById('notificationsLoadMore');
    loadMoreButton?.classList.toggle('d-none', !data.has_more);
  } finally {
    if (!append) loading?.classList.add('d-none');
  }
}

function renderNotifications(items = [], append = false) {
  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  if (!append) {
    container.replaceChildren();
  }

  const fragment = document.createDocumentFragment();

  for (const notification of items) {
    if (append) {
      document.getElementById(`notification-${notification.id}`)?.remove();
    }

    fragment.append(createNotificationElement(notification));
  }

  container.append(fragment);
  setInboxEmpty(container.childElementCount === 0);
}

function createNotificationElement(notification) {
  const element = createElement('div', 'notification');
  const main = createElement('div', 'notification-main');
  const circle = createElement('div', 'rounded-circle');
  const content = createElement('div', 'notification-content');
  const header = createElement('h6', 'notification-header');
  const title = createElement('span', 'notification-title', 'me-3');
  const time = createElement('span', 'notification-time');
  const message = createElement('div', 'notification-message');
  const deleteButton = createElement(
    'button',
    'notification-delete-button',
    'btn',
    'btn-danger',
    'p-1',
  );

  const timestamp = notification.last_event_at || notification.timestamp;

  element.id = `notification-${notification.id}`;
  element.dataset.id = notification.id;
  element.dataset.read = notification.is_read ? '1' : '0';
  element.dataset.link =
    safeInternalPath(
      notification.payload?.link || notification.payload?.url || null,
    ) || '';

  element.classList.toggle('read', notification.is_read);

  title.textContent = notification.title || '';
  message.textContent = notification.body || '';
  time.dataset.relativeTimestamp = timestamp;
  time.textContent = formatRelativeTime(timestamp);
  deleteButton.textContent = 'Delete';

  header.append(title, time);
  content.append(header, message);
  main.append(circle, content);
  element.append(main, deleteButton);

  return element;
}

async function handleInboxClick(event) {
  const notification = event.target.closest('.notification');
  if (!notification) return;

  if (event.target.closest('.notification-delete-button')) {
    event.preventDefault();

    const data = await postJSON(
      `/notification/${notification.dataset.id}/delete/`,
    );
    if (!data) return;

    notification.remove();
    applyUnreadBadgeCountFromResponse(data);
    const container = document.getElementById('notificationsContainer');
    setInboxEmpty(!container?.childElementCount);
    return;
  }

  if (notification.dataset.busy === '1') return;

  notification.dataset.busy = '1';
  const link = notification.dataset.link;

  try {
    if (notification.dataset.read === '0') {
      const data = await postJSON(
        `/notification/${notification.dataset.id}/read/`,
      );

      if (data) {
        applyUnreadBadgeCountFromResponse(data);
        notification.classList.add('read');
        notification.dataset.read = '1';
      }
    }
  } catch (error) {
    console.warn('Failed to mark notification as read', error);
  } finally {
    if (link) {
      window.location.assign(link);
    } else {
      delete notification.dataset.busy;
    }
  }
}

function toggleTouchHover(event) {
  event.target
    .closest('.notification')
    ?.classList.toggle('notification-hover', event.type === 'touchstart');
}

function createElement(tag, ...classes) {
  const element = document.createElement(tag);
  element.classList.add(...classes);
  return element;
}

function setInboxEmpty(empty) {
  const emptyMessage = document.getElementById('notificationsEmpty');
  const container = document.getElementById('notificationsContainer');

  emptyMessage?.classList.toggle('d-none', !empty);
  container?.classList.toggle('d-none', empty);
}

function isInboxOpen() {
  return document.getElementById('modal')?.classList.contains('show') ?? false;
}

function startRelativeTimeRefresh() {
  if (relativeTimeRefreshStarted) return;

  relativeTimeRefreshStarted = true;
  refreshRelativeTimestamps();
  setInterval(refreshRelativeTimestamps, NOTIFICATION_RELATIVE_TIME_REFRESH_MS);
}

function refreshRelativeTimestamps() {
  document.querySelectorAll('[data-relative-timestamp]').forEach((element) => {
    element.textContent = formatRelativeTime(element.dataset.relativeTimestamp);
  });
}
