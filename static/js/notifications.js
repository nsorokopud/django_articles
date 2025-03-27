const notificationElements = document.querySelectorAll('.notification');
const notificationDeleteButtons = document.querySelectorAll(
  '.notification-delete-button',
);

notificationElements.forEach((element) => {
  addEventListenersToNotificationElement(element);
});
notificationDeleteButtons.forEach((button) => {
  addEventListenerToNotificaionDeleteButton(button);
});

const wsScheme = window.location.protocol == 'https:' ? 'wss' : 'ws';
const socket = new WebSocket(
  `${wsScheme}://${window.location.host}/ws/notifications/`,
);
addEventListenersToWebSocket(socket);

function addEventListenersToWebSocket(socket) {
  socket.onopen = () => {
    console.log('WebSocket connection opened.');
  };
  socket.onmessage = (event) => {
    console.log('New notification received.');
    const eventDataJson = JSON.parse(event.data);
    const toastContainer = document.getElementById('toastContainer');
    const newToastElement = createToastElement(
      eventDataJson.id,
      eventDataJson.title,
      eventDataJson.text,
      eventDataJson.timestamp,
      eventDataJson.link,
    );
    toastContainer.appendChild(newToastElement);
    let toastDisplayDuration = 1000 * 60 * 10; // 10 min
    let newToast = new bootstrap.Toast(newToastElement, {
      delay: toastDisplayDuration,
    });
    newToast.show();

    let notificationCounter = document.getElementById('notificationCounter');
    let oldNotificationCount = notificationCounter.textContent.trim();
    if (oldNotificationCount == '0') {
      notificationCounter.textContent = '1';
      notificationCounter.classList.remove('invisible');
    } else if (oldNotificationCount != '999+') {
      notificationCounter.textContent = parseInt(oldNotificationCount) + 1;
    }

    const newNotificationElement = createNotificationElement(
      eventDataJson.id,
      eventDataJson.title,
      eventDataJson.text,
      eventDataJson.link,
      eventDataJson.timestamp,
    );

    const notificationContainer = document.getElementById(
      'notificationsContainer',
    );

    if (notificationContainer.children.length == 0) {
      const modalTitle = document.querySelector('.modal-title');
      modalTitle.textContent = 'Notifications';
      const modalBody = document.querySelector('.modal-body');
      modalBody.classList.remove('d-none');
      const modalFooter = document.querySelector('.modal-footer');
      modalFooter.classList.remove('d-none');
    }
    notificationContainer.insertBefore(
      newNotificationElement,
      notificationContainer.firstChild,
    );
  };
  socket.onclose = () => {
    console.log('WebSocket connection closed.');
  };
}

function getCookie(name) {
  var re = new RegExp(name + '=([^;]+)');
  var value = re.exec(document.cookie);
  return value != null ? value[1] : null;
}

function addEventListenersToNotificationElement(element) {
  element.addEventListener('touchstart', () => {
    element.classList.add('notification-hover');
  });
  element.addEventListener('touchend', () => {
    element.classList.remove('notification-hover');
  });
  element.addEventListener('click', () => {
    let notificationId = element
      .getAttribute('id')
      .replace('notification-', '');
    let xmlHttp = new XMLHttpRequest();
    xmlHttp.open(
      'POST',
      `${location.origin}/notification/${notificationId}/read/`,
      false,
    );
    xmlHttp.setRequestHeader('X-CSRFToken', getCookie('csrftoken')),
      xmlHttp.send(null);
    window.location.replace(element.getAttribute('href'));
  });
}

function addEventListenerToNotificaionDeleteButton(button) {
  button.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const notificationElement = button.parentElement;

    const notificationMain =
      notificationElement.getElementsByClassName('notification-main')[0];
    const notificationId = notificationElement.getAttribute('id');
    const notificationIdNumber = notificationId.replace('notification-', '');

    notificationElement.style.maxHeight =
      notificationElement.offsetHeight + 'px';
    notificationMain.style.visibility = 'hidden';
    const notificationContainer = document.getElementById(
      'notificationsContainer',
    );

    let xmlHttp = new XMLHttpRequest();
    xmlHttp.onreadystatechange = function () {
      if (xmlHttp.readyState == XMLHttpRequest.DONE) {
        let response = JSON.parse(xmlHttp.responseText);

        $('#' + notificationId).animate(
          { opacity: 'hide', width: 'toggle' },
          'fast',
          'linear',
          function () {
            $('#' + notificationId).remove();
            if (notificationContainer.children.length == 0) {
              const modalTitle = document.getElementById('modalTitle');
              modalTitle.innerText = 'No notifications';
              const modalBody =
                document.getElementsByClassName('modal-body')[0];
              const modalFooter =
                document.getElementsByClassName('modal-footer')[0];
              modalBody.classList.add('d-none');
              modalFooter.classList.add('d-none');
            }

            let notificationCounter = document.getElementById(
              'notificationCounter',
            );
            let newNotificationCount = response.unread_notifications_count;
            notificationCounter.innerText = newNotificationCount;
            if (newNotificationCount == 0) {
              notificationCounter.classList.add('invisible');
            }
          },
        );
      }
    };
    xmlHttp.open(
      'POST',
      `${location.origin}/notification/${notificationIdNumber}/delete/`,
      true,
    );
    xmlHttp.setRequestHeader('X-CSRFToken', getCookie('csrftoken')),
      xmlHttp.send(null);
  });
}

function createNotificationElement(id, title, message, link, timestamp) {
  const notification = document.createElement('div');
  notification.setAttribute('id', 'notification-' + id);
  notification.classList.add('notification');
  notification.setAttribute('href', link);
  addEventListenersToNotificationElement(notification);

  const notificationMain = document.createElement('div');
  notificationMain.classList.add('notification-main');

  const circle = document.createElement('div');
  circle.classList.add('rounded-circle');

  const notificationContent = document.createElement('div');
  notificationContent.classList.add('notification-content');

  const notificationHeader = document.createElement('h6');
  notificationHeader.classList.add('notification-header');

  const notificationTitle = document.createElement('span');
  notificationTitle.classList.add('notification-title', 'me-3');
  notificationTitle.innerText = title;

  const notificationTime = document.createElement('span');
  notificationTime.classList.add('notification-time');
  notificationTime.innerText = luxon.DateTime.fromJSDate(
    new Date(timestamp),
  ).toFormat('HH:mm dd-MM-yyyy');

  const notificationMessage = document.createElement('div');
  notificationMessage.classList.add('notification-message');
  notificationMessage.innerText = message;

  const deleteButton = document.createElement('button');
  deleteButton.classList.add(
    'notification-delete-button',
    'btn',
    'btn-danger',
    'p-1',
  );
  deleteButton.innerText = 'Delete';
  addEventListenerToNotificaionDeleteButton(deleteButton);

  notificationHeader.appendChild(notificationTitle);
  notificationHeader.appendChild(notificationTime);
  notificationContent.appendChild(notificationHeader);
  notificationContent.appendChild(notificationMessage);

  notificationMain.appendChild(circle);
  notificationMain.appendChild(notificationContent);
  notification.appendChild(notificationMain);
  notification.appendChild(deleteButton);
  return notification;
}

function createToastElement(id, title, message, time, link = null) {
  const toast = document.createElement('div');
  toast.classList.add('toast');

  const toastHeader = document.createElement('div');
  toastHeader.classList.add('toast-header');

  const headerText = document.createElement('strong');
  headerText.classList.add('me-auto');
  headerText.innerText = title;

  const headerTime = document.createElement('small');
  headerTime.innerText = luxon.DateTime.fromJSDate(new Date(time)).toFormat(
    'HH:mm dd-MM-yyyy',
  );

  const closeButton = document.createElement('button');
  closeButton.classList.add('btn-close');
  closeButton.setAttribute('type', 'button');
  closeButton.setAttribute('data-bs-dismiss', 'toast');
  closeButton.setAttribute('aria-label', 'Close');
  closeButton.addEventListener('click', (event) => {
    event.stopImmediatePropagation();
    new CustomEvent('notification-toast-remove', { detail: closeButton });
  });

  toastHeader.appendChild(headerText);
  toastHeader.appendChild(headerTime);
  toastHeader.appendChild(closeButton);

  const toastBody = document.createElement('div');
  toastBody.classList.add('toast-body');
  if (link !== null) {
    toastBody.innerHTML = `<span>${message}.</span>`;
  } else toastBody.innerText = message;

  toast.appendChild(toastHeader);
  toast.appendChild(toastBody);

  if (link) {
    toast.addEventListener('click', () => {
      let xmlHttp = new XMLHttpRequest();
      xmlHttp.open(
        'POST',
        `${location.origin}/notification/${id}/read/`,
        false,
      );
      xmlHttp.setRequestHeader('X-CSRFToken', getCookie('csrftoken')),
        xmlHttp.send(null);
      window.location.replace(link);
    });
  }
  return toast;
}
