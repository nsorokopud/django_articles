import { postJSON, safeInternalPath } from './utils.js';

const TOAST_DISPLAY_DURATION_MS = 10 * 60 * 1000; // 10 min

export function showToast({
  id,
  title,
  body,
  timestamp,
  payload,
  link,
  markReadOnClick,
  displayDurationMs,
}) {
  const toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) return;

  if (id != null) {
    const existing = toastContainer.querySelector(
      `[data-toast-id="${String(id)}"]`,
    );
    if (existing) {
      const existingToast = bootstrap.Toast.getInstance(existing);
      if (existingToast) existingToast.dispose();
      existing.remove();
    }
  }

  const toastEl = document.createElement('div');
  toastEl.classList.add('toast');

  if (id != null) {
    toastEl.dataset.toastId = String(id);
  }

  const toastHeader = document.createElement('div');
  toastHeader.classList.add('toast-header');

  const headerText = document.createElement('strong');
  headerText.classList.add('me-auto');
  headerText.textContent = title || '';

  const headerTime = document.createElement('small');
  try {
    const effectiveTimestamp = getToastTimestamp(timestamp, payload);
    headerTime.dataset.relativeTimestamp = effectiveTimestamp;
    headerTime.innerText =
      luxon.DateTime.fromJSDate(new Date(effectiveTimestamp)).toRelative() ||
      '';
  } catch {
    headerTime.innerText = '';
  }

  const closeButton = document.createElement('button');
  closeButton.classList.add('btn-close');
  closeButton.setAttribute('type', 'button');
  closeButton.setAttribute('data-bs-dismiss', 'toast');
  closeButton.setAttribute('aria-label', 'Close');

  toastHeader.appendChild(headerText);
  toastHeader.appendChild(headerTime);
  toastHeader.appendChild(closeButton);

  const toastBody = document.createElement('div');
  toastBody.classList.add('toast-body');
  toastBody.textContent = body || '';

  toastEl.appendChild(toastHeader);
  toastEl.appendChild(toastBody);
  toastContainer.appendChild(toastEl);

  const displayDuration =
    typeof displayDurationMs === 'number'
      ? displayDurationMs
      : TOAST_DISPLAY_DURATION_MS;
  const toast = new bootstrap.Toast(toastEl, { delay: displayDuration });

  toastEl.addEventListener('hidden.bs.toast', () => {
    toastEl.remove();
  });

  toast.show();

  const safeLink = safeInternalPath(link);

  if (safeLink) {
    toastEl.style.cursor = 'pointer';

    let clicked = false;
    toastEl.addEventListener('click', async (ev) => {
      // Clicking close should NOT navigate
      const target = ev.target;
      if (
        target instanceof Element &&
        target.closest('[data-bs-dismiss="toast"]')
      ) {
        return;
      }

      if (clicked) return;
      clicked = true;

      if (markReadOnClick && id != null) {
        await postJSON(`/notification/${id}/read/`);
      }

      window.location.replace(safeLink);
    });
  }
}

function getToastTimestamp(timestamp, payload) {
  if (
    payload &&
    payload.kind === 'comment_aggregate' &&
    payload.last_comment_at
  ) {
    return payload.last_comment_at;
  }
  return timestamp;
}
