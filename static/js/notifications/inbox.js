import { intVal, postJSON } from './utils.js';
import { showToast } from './toasts.js';

const INBOX_PAGE_SIZE = 50;
const NOTIFICATIONS_LIST_PATH = '/notifications/list/';
const UNREAD_COUNT_PATH = '/notifications/unread_count/';
const UNREAD_COUNT_SYNC_THROTTLE_MS = 2000;

let inboxNewestId = 0;
let inboxOldestId = 0;
let lastUnreadSyncMs = 0;

export function initInboxUI() {
  initInboxUnreadBadge();
  setupInboxModalLoading();
}

export function onNotificationReceived(n) {
  showToast({
    id: n.id,
    title: n.title,
    body: n.body,
    timestamp: n.timestamp,
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
    {
      credentials: 'same-origin',
    },
  );

  setInboxLoading(false);
  if (!res.ok) return;

  const data = await res.json();
  renderInboxItems(data.items, { mode: 'replace' });

  updateInboxBounds(data.items);
  updateLoadMoreButton(data.has_more);
}

async function loadOlderNotifications() {
  if (!inboxOldestId) return;

  const res = await fetch(
    `${location.origin}${NOTIFICATIONS_LIST_PATH}?limit=${INBOX_PAGE_SIZE}&before_id=${inboxOldestId}`,
    { credentials: 'same-origin' },
  );
  if (!res.ok) return;

  const data = await res.json();
  renderInboxItems(data.items, { mode: 'append' });

  updateInboxBounds(data.items);
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
  showInboxUI();

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

  switch (mode) {
    case 'prepend':
      container.prepend(fragment);
      break;
    case 'replace':
    case 'append':
    default:
      container.appendChild(fragment);
  }
}

function prependInboxItem(n) {
  showInboxUI();
  setInboxEmpty(false);

  const container = document.getElementById('notificationsContainer');
  if (!container) return;

  const existing = document.getElementById(`notification-${n.id}`);
  const nextEl = createInboxNotificationElement(n);

  if (existing) {
    existing.replaceWith(nextEl);
  } else {
    container.prepend(nextEl);
  }

  if (!inboxNewestId || n.id > inboxNewestId) inboxNewestId = n.id;
  if (!inboxOldestId || n.id < inboxOldestId) inboxOldestId = n.id;
}

function updateInboxBounds(items) {
  if (!items || !items.length) return;

  const ids = items.map((x) => x.id);
  const maxId = Math.max(...ids);
  const minId = Math.min(...ids);

  inboxNewestId = inboxNewestId ? Math.max(inboxNewestId, maxId) : maxId;
  inboxOldestId = inboxOldestId ? Math.min(inboxOldestId, minId) : minId;
}

function setInboxLoading(isLoading) {
  showInboxUI();
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

function showInboxUI() {
  const modalTitle = document.getElementById('modalTitle');
  const modalBody = document.getElementsByClassName('modal-body')[0] || null;
  const modalFooter =
    document.getElementsByClassName('modal-footer')[0] || null;

  if (modalTitle) modalTitle.innerText = 'Notifications';
  if (modalBody) modalBody.classList.remove('d-none');
  if (modalFooter) modalFooter.classList.remove('d-none');
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
  const link = n.payload?.link || n.payload?.url || null;

  const notification = document.createElement('div');
  notification.id = `notification-${n.id}`;
  notification.classList.add('notification');
  if (n.is_read) notification.classList.add('read');

  notification.addEventListener('touchstart', () =>
    notification.classList.add('notification-hover'),
  );
  notification.addEventListener('touchend', () =>
    notification.classList.remove('notification-hover'),
  );

  notification.addEventListener('click', async () => {
    if (notification.dataset.busy === '1') return;
    notification.dataset.busy = '1';

    const hasLink = !!link;

    try {
      if (hasLink) {
        notification.classList.add('read');
        n.is_read = true;

        postJSON(`/notification/${n.id}/read/`, {
          keepalive: true,
        }).then((data) => {
          if (data) applyUnreadCountFromResponse(data);
        });

        window.location.replace(link);
        return;
      }

      const data = await postJSON(`/notification/${n.id}/read/`);
      if (data) {
        applyUnreadCountFromResponse(data);
        notification.classList.add('read');
        n.is_read = true;
      }
    } finally {
      notification.dataset.busy = '0';
    }
  });

  const notificationMain = (() => {
    const el = document.createElement('div');
    el.classList.add('notification-main');
    return el;
  })();
  const circle = (() => {
    const el = document.createElement('div');
    el.classList.add('rounded-circle');
    return el;
  })();
  const content = (() => {
    const el = document.createElement('div');
    el.classList.add('notification-content');
    return el;
  })();

  const header = document.createElement('h6');
  header.classList.add('notification-header');

  const title = (() => {
    const el = document.createElement('span');
    el.classList.add('notification-title', 'me-3');
    return el;
  })();
  title.innerHTML = n.title || '';

  const time = (() => {
    const el = document.createElement('span');
    el.classList.add('notification-time');
    return el;
  })();
  time.innerText = luxon.DateTime.fromJSDate(new Date(n.timestamp)).toFormat(
    'HH:mm dd-MM-yyyy',
  );

  const msg = (() => {
    const el = document.createElement('div');
    el.classList.add('notification-message');
    return el;
  })();
  msg.innerHTML = n.body || '';

  header.append(title, time);
  content.append(header, msg);
  notificationMain.append(circle, content);

  const del = document.createElement('button');
  del.classList.add('notification-delete-button', 'btn', 'btn-danger', 'p-1');
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

  notification.append(notificationMain, del);
  return notification;
}

function updateEmptyUIIfInboxEmpty() {
  const container = document.getElementById('notificationsContainer');
  if (!container || container.children.length > 0) return;

  const modalFooter =
    document.getElementsByClassName('modal-footer')[0] || null;
  if (modalFooter) modalFooter.classList.add('d-none');

  setInboxEmpty(true);
}
