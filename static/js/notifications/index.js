import {
  initInboxUI,
  onNotificationReceived,
  onNotificationDigestReceived,
} from './inbox.js';
import { initWebSocket } from './ws.js';

const dataset = document.body?.dataset;

const isAuthenticated = dataset?.isAuthenticated === '1';

if (isAuthenticated) {
  initInboxUI();
  initWebSocket({
    onNotification: onNotificationReceived,
    onDigest: onNotificationDigestReceived,
  });
}
