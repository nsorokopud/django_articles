// Cross-tab leader-elected polling for "new articles" notifications.
// - Only one tab polls at a time (leader election via localStorage + BroadcastChannel).
// - The next scheduled poll time is persisted across reloads/tab switches so
//   polling doesn’t restart from scratch.
// - Polling is suppressed on the subscriptions page and when the tab is hidden,
//   and throttled while idle.

import { showToast } from './toasts.js';
import { intVal } from './utils.js';

// Cross-tab shared state (localStorage)
const DIGEST_LEADER_KEY = 'digest_leader';
const DIGEST_PREFERRED_LEADER_KEY = 'digest_preferred_leader';
const NEW_ARTICLES_DIGEST_CURSOR_KEY = 'digest_cursor_id';
const NEW_ARTICLES_DIGEST_NEXT_POLL_MS_KEY = 'digest_next_poll_ms';
const SUBS_FEED_LAST_SEEN_TS_KEY = 'subs_last_seen_ts';

// Leader election timing
const DIGEST_HEARTBEAT_MS = 5_000;
const DIGEST_LEADER_TTL_MS = 40_000;
const DIGEST_WATCHDOG_MS = 5_000;
const DIGEST_PREFERRED_LEADER_WINDOW_MS = 15_000;

// Visibility-driven leadership handoff
const DIGEST_VISIBILITY_CLAIM_DELAY_MS = 250;
const DIGEST_VISIBILITY_CLAIM_RETRY_MS = 1_000;
const DIGEST_VISIBILITY_CLAIM_MAX_ATTEMPTS = 3;

// Digest polling timing
const DIGEST_POLL_INTERVAL_MS = 5 * 60 * 1000; // 5 min
const DIGEST_POLL_JITTER_MS = 30 * 1000;

// Maximum allowed carryover when resuming a stored next-poll time.
// Prevents resuming an obviously stale schedule (e.g. after long sleep);
// avoids "catching up" with immediate polls.
const MAX_SCHEDULE_CARRYOVER_MS =
  DIGEST_POLL_INTERVAL_MS + DIGEST_POLL_JITTER_MS + 5_000;

// Idle / suppression behavior
const DIGEST_IDLE_AFTER_MS = 10 * 60 * 1000;
const DIGEST_IDLE_POLL_EVERY_MS = 15 * 60 * 1000;
const SUBS_FEED_COOLDOWN_MS = 5 * 60 * 1000;

// UI behavior
const DIGEST_TOAST_DELAY_MS = 15_000;

const tabId =
  (crypto?.randomUUID && crypto.randomUUID()) ||
  `${Date.now()}_${String(Math.random()).slice(2)}`;

const state = {
  isAuthenticated: false,
  isSubscriptionsPage: false,
  isSubscriptionsFeedPageOne: false,
  latestArticleId: 0,
};

let digestChannel = null;

let lastUserActivityMs = Date.now();
let lastIdleDigestRunMs = 0;

let storageListenerAttached = false;
let idleListenersAttached = false;
let visibilityLeadershipAttached = false;

let leaderElectionStarted = false;
let isDigestLeader = false;

let leaderHeartbeatIntervalId = null;
let leaderWatchdogIntervalId = null;
let digestKickoffTimeoutId = null;
let digestLoopTimeoutId = null;

let newArticlesDigestCursorId = intVal(
  localStorage.getItem(NEW_ARTICLES_DIGEST_CURSOR_KEY),
  0,
);

// Initialization + Setup

export function initNewArticlesDigest({
  isAuthenticated,
  isSubscriptionsPage,
  isSubscriptionsFeedPageOne,
  latestArticleId,
} = {}) {
  state.isAuthenticated = !!isAuthenticated;
  state.isSubscriptionsPage = !!isSubscriptionsPage;
  state.isSubscriptionsFeedPageOne = !!isSubscriptionsFeedPageOne;
  state.latestArticleId = intVal(latestArticleId, 0);

  if (!state.isAuthenticated) return;

  if (!digestChannel && 'BroadcastChannel' in window) {
    digestChannel = new BroadcastChannel('digest-leader');
  }

  setupVisibilityLeadership();
  setupIdleTracking();

  // On subscriptions feed page 1: record "seen recently" (suppresses toasts briefly)
  // and advance the cursor so we don't notify about already-visible items.
  if (state.isSubscriptionsPage && state.isSubscriptionsFeedPageOne) {
    localStorage.setItem(SUBS_FEED_LAST_SEEN_TS_KEY, String(Date.now()));

    const latestId = intVal(state.latestArticleId, 0);

    if (latestId > 0) bumpDigestCursor(latestId);
  }

  syncDigestCursorFromStorage();
  startLeaderElection();

  if (!storageListenerAttached) {
    storageListenerAttached = true;

    window.addEventListener('storage', (e) => {
      if (e.key === NEW_ARTICLES_DIGEST_CURSOR_KEY) {
        syncDigestCursorFromStorage();
        return;
      }

      if (e.key === DIGEST_LEADER_KEY) {
        const cur = readLeader();
        const isFreshOtherLeader =
          cur &&
          cur.id !== tabId &&
          Date.now() - (cur.ts || 0) < DIGEST_LEADER_TTL_MS;

        if (isDigestLeader && isFreshOtherLeader) {
          stepDown('storage');
        }
      }
    });
  }
}

function setupVisibilityLeadership() {
  if (visibilityLeadershipAttached) return;
  visibilityLeadershipAttached = true;

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    if (!state.isAuthenticated) return;

    try {
      // Prefer the most recently visible tab to reduce background polling.
      localStorage.setItem(
        DIGEST_PREFERRED_LEADER_KEY,
        JSON.stringify({ id: tabId, ts: Date.now() }),
      );
    } catch {
      /* noop */
    }

    let attempts = 0;
    const tryClaimLeadership = () => {
      if (isDigestLeader) return;

      if (claimLeadership('preferred-visible')) return;

      if (++attempts < DIGEST_VISIBILITY_CLAIM_MAX_ATTEMPTS)
        setTimeout(tryClaimLeadership, DIGEST_VISIBILITY_CLAIM_RETRY_MS);
    };

    setTimeout(tryClaimLeadership, DIGEST_VISIBILITY_CLAIM_DELAY_MS);
  });
}

function setupIdleTracking() {
  if (idleListenersAttached) return;
  idleListenersAttached = true;

  const opts = { capture: true, passive: true };
  window.addEventListener('mousemove', markUserActive, opts);
  window.addEventListener('mousedown', markUserActive, opts);
  window.addEventListener('keydown', markUserActive, opts);
  window.addEventListener('scroll', markUserActive, opts);
  window.addEventListener('touchstart', markUserActive, opts);
}

function startLeaderElection() {
  if (leaderElectionStarted) return;
  leaderElectionStarted = true;

  claimLeadership('startup');

  leaderHeartbeatIntervalId = setInterval(() => {
    if (!isDigestLeader) return;

    writeLeader({ id: tabId, ts: Date.now() });

    // If another tab was recently visible, yield leadership to it.
    try {
      const pref = JSON.parse(
        localStorage.getItem(DIGEST_PREFERRED_LEADER_KEY) || 'null',
      );

      if (
        pref &&
        pref.id !== tabId &&
        Date.now() - pref.ts < DIGEST_PREFERRED_LEADER_WINDOW_MS
      ) {
        stepDown('preferred-visible-tab');
      }
    } catch {
      /* noop */
    }
  }, DIGEST_HEARTBEAT_MS);

  // Watchdog: non-leaders try to claim only if leader expired
  leaderWatchdogIntervalId = setInterval(() => {
    if (isDigestLeader) return;

    const cur = readLeader();
    const expired = !cur || Date.now() - (cur.ts || 0) > DIGEST_LEADER_TTL_MS;
    if (expired) claimLeadership('watchdog');
  }, DIGEST_WATCHDOG_MS);

  // React instantly to leader announcements (BC)
  digestChannel?.addEventListener('message', (ev) => {
    const msg = ev.data;
    if (!msg || msg.type !== 'leader') return;
    if (msg.id !== tabId && isDigestLeader) stepDown('bc');
  });

  // Release leadership on close / bfcache
  const cleanup = () => {
    if (isDigestLeader) clearLeaderIfMine();
  };
  window.addEventListener('beforeunload', cleanup);
  window.addEventListener('pagehide', cleanup);
}

// Digest polling

function startDigestPolling() {
  if (!state.isAuthenticated || !isDigestLeader) return;

  stopDigestPolling();

  const perTickJitterMs = () =>
    Math.floor(Math.random() * DIGEST_POLL_JITTER_MS);

  const scheduleFromNow = (delayMs) => {
    if (!isDigestLeader) return;

    digestKickoffTimeoutId = setTimeout(async () => {
      await tick();
      scheduleNext();
    }, delayMs);
  };

  const tick = async () => {
    if (!isDigestLeader) return;

    const nextDueMs = Date.now() + DIGEST_POLL_INTERVAL_MS + perTickJitterMs();
    writeNextPollDueMs(nextDueMs);

    if (canRunDigestNow()) {
      await checkNewArticlesDigest();

      // If we just ran while idle, remember it (for throttling)
      if (isUserIdle()) lastIdleDigestRunMs = Date.now();
    }
  };

  const scheduleNext = () => {
    if (!isDigestLeader) return;

    const nextDueMs = readNextPollDueMs();
    const now = Date.now();

    const remainingMs = nextDueMs - now;
    const delayMs =
      remainingMs > 0 && remainingMs <= MAX_SCHEDULE_CARRYOVER_MS
        ? remainingMs
        : DIGEST_POLL_INTERVAL_MS + perTickJitterMs();

    digestLoopTimeoutId = setTimeout(async () => {
      await tick();
      scheduleNext();
    }, delayMs);
  };

  // On startup or leadership takeover, resume the stored schedule if valid.
  // Page reloads or tab switches are not resetting the poll schedule.
  const storedNextDueMs = readNextPollDueMs();
  const now = Date.now();
  const carryoverMs = storedNextDueMs - now;

  if (storedNextDueMs > now && carryoverMs <= MAX_SCHEDULE_CARRYOVER_MS) {
    scheduleFromNow(carryoverMs);
  } else {
    scheduleFromNow(perTickJitterMs());
  }
}

function stopDigestPolling() {
  if (digestKickoffTimeoutId) clearTimeout(digestKickoffTimeoutId);
  if (digestLoopTimeoutId) clearTimeout(digestLoopTimeoutId);
  digestKickoffTimeoutId = null;
  digestLoopTimeoutId = null;
}

async function checkNewArticlesDigest() {
  const sinceId = syncDigestCursorFromStorage();

  try {
    const res = await fetch(digestSummaryUrl(sinceId), {
      credentials: 'same-origin',
    });
    if (!res.ok) return;

    const data = await res.json();
    if (!data.has_new) return;

    const latest = intVal(data.latest_article_id, 0);

    if (latest <= newArticlesDigestCursorId) return;

    bumpDigestCursor(latest);

    showToast({
      id: null,
      title: 'New articles',
      body: 'New articles available! Check your subscriptions feed.',
      timestamp: new Date().toISOString(),
      link: '/subscriptions/',
      markReadOnClick: false,
      delayMs: DIGEST_TOAST_DELAY_MS,
    });
  } catch (e) {
    console.debug('Digest check failed', e);
  }
}

// Leader election helpers

function readLeader() {
  try {
    return JSON.parse(localStorage.getItem(DIGEST_LEADER_KEY) || 'null');
  } catch {
    return null;
  }
}

function writeLeader(value) {
  localStorage.setItem(DIGEST_LEADER_KEY, JSON.stringify(value));
}

function clearLeaderIfMine() {
  const cur = readLeader();
  if (cur && cur.id === tabId) localStorage.removeItem(DIGEST_LEADER_KEY);
}

function claimLeadership(reason = '') {
  const cur = readLeader();
  const expired = !cur || Date.now() - (cur.ts || 0) > DIGEST_LEADER_TTL_MS;

  if (expired || (cur && cur.id === tabId)) {
    writeLeader({ id: tabId, ts: Date.now() });

    if (!isDigestLeader) {
      isDigestLeader = true;
      onBecameLeader();
      digestChannel?.postMessage({ type: 'leader', id: tabId, reason });
    }
    return true;
  }

  if (isDigestLeader) stepDown('claim');
  return false;
}

function stepDown(reason = '') {
  if (!isDigestLeader) return;

  clearLeaderIfMine();

  isDigestLeader = false;
  onLostLeadership();
}

function onBecameLeader() {
  startDigestPolling();
}

function onLostLeadership() {
  stopDigestPolling();
}

// Gating + idle helpers

function digestSummaryUrl(sinceId) {
  const url = new URL(`${location.origin}/notifications/new_articles_summary/`);
  url.searchParams.set('since_id', String(sinceId));
  return url;
}

function syncDigestCursorFromStorage() {
  const stored = intVal(
    localStorage.getItem(NEW_ARTICLES_DIGEST_CURSOR_KEY),
    0,
  );
  if (stored > newArticlesDigestCursorId) newArticlesDigestCursorId = stored;
  return newArticlesDigestCursorId;
}

function bumpDigestCursor(latestId) {
  const current = syncDigestCursorFromStorage();
  const next = Math.max(current, latestId);
  localStorage.setItem(NEW_ARTICLES_DIGEST_CURSOR_KEY, String(next));
  newArticlesDigestCursorId = next;
}

function readNextPollDueMs() {
  return intVal(localStorage.getItem(NEW_ARTICLES_DIGEST_NEXT_POLL_MS_KEY), 0);
}

function writeNextPollDueMs(nextDueMs) {
  localStorage.setItem(NEW_ARTICLES_DIGEST_NEXT_POLL_MS_KEY, String(nextDueMs));
}

function wasSubscriptionPageRecentlyOpened() {
  const ts = intVal(localStorage.getItem(SUBS_FEED_LAST_SEEN_TS_KEY), 0);
  return ts > 0 && Date.now() - ts < SUBS_FEED_COOLDOWN_MS;
}

function isUserIdle() {
  return Date.now() - lastUserActivityMs >= DIGEST_IDLE_AFTER_MS;
}

function canRunDigestNowIgnoringIdleThrottle() {
  if (document.hidden) return false;
  if (state.isSubscriptionsPage) return false;
  if (wasSubscriptionPageRecentlyOpened()) return false;
  return true;
}

function canRunDigestNow() {
  if (document.hidden) return false;
  if (state.isSubscriptionsPage) return false;
  if (wasSubscriptionPageRecentlyOpened()) return false;

  if (isUserIdle()) {
    if (DIGEST_IDLE_POLL_EVERY_MS <= 0) return false;

    if (Date.now() - lastIdleDigestRunMs < DIGEST_IDLE_POLL_EVERY_MS)
      return false;
  }

  return true;
}

function markUserActive() {
  const wasIdle = isUserIdle();
  lastUserActivityMs = Date.now();

  if (wasIdle && isDigestLeader && canRunDigestNowIgnoringIdleThrottle()) {
    checkNewArticlesDigest().finally(() => {
      lastIdleDigestRunMs = Date.now();
    });
  }
}
