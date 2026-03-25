const WS_PATH = '/ws/notifications/';
const MESSAGE_KINDS = {
  NOTIFICATION: 'notification',
  DIGEST: 'digest',
};

export function initWebSocket({
  onNotification,
  onDigest,
  location = window.location,
  logger = console,
}) {
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const socket = new WebSocket(`${scheme}://${location.host}${WS_PATH}`);

  socket.addEventListener('open', () => logger.debug('WS connected'));
  socket.addEventListener('close', () => logger.debug('WS disconnected'));
  socket.addEventListener('error', (event) => logger.error('WS error', event));

  socket.addEventListener('message', (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch {
      logger.warn('Invalid WS message', event.data);
      return;
    }

    if (!msg || typeof msg !== 'object') {
      logger.debug('Non-object WS message', msg);
      return;
    }

    switch (msg.kind) {
      case MESSAGE_KINDS.NOTIFICATION:
        onNotification?.(msg);
        return;
      case MESSAGE_KINDS.DIGEST:
        onDigest?.(msg);
        return;
      default:
        logger.debug('Unknown WS message', msg);
        return;
    }
  });

  return socket;
}
