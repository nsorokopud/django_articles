import { postJSON } from './utils.js';

const TOAST_DELAY_MS = 10 * 60 * 1000; // 10 min

export function showToast({
  id,
  title,
  body,
  timestamp,
  link,
  markReadOnClick,
  delayMs,
}) {
  const toastContainer = document.getElementById('toastContainer');
  if (!toastContainer) return;

  const toastEl = document.createElement('div');
  toastEl.classList.add('toast');

  const toastHeader = document.createElement('div');
  toastHeader.classList.add('toast-header');

  const headerText = document.createElement('strong');
  headerText.classList.add('me-auto');
  headerText.innerHTML = title || '';

  const headerTime = document.createElement('small');
  try {
    headerTime.innerText = luxon.DateTime.fromJSDate(
      new Date(timestamp),
    ).toFormat('HH:mm dd-MM-yyyy');
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
  toastBody.innerHTML = body || '';

  toastEl.appendChild(toastHeader);
  toastEl.appendChild(toastBody);
  toastContainer.appendChild(toastEl);

  const delay = typeof delayMs === 'number' ? delayMs : TOAST_DELAY_MS;
  const toast = new bootstrap.Toast(toastEl, { delay });

  toastEl.addEventListener('hidden.bs.toast', () => {
    toastEl.remove();
  });

  toast.show();

  if (link) {
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

      window.location.replace(link);
    });
  }
}
