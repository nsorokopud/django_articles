import { initNewArticlesDigest } from './new-articles.js';
import {
  initInboxUI,
  onNotificationReceived,
  onNotificationDigestReceived,
} from './inbox.js';
import { initWebSocket } from './ws.js';

const dataset = document.body?.dataset;

const isAuthenticated = dataset?.isAuthenticated === '1';
const isSubscriptionsPage = dataset?.page === 'subscriptions';
const isSubscriptionsFeedPageOne = dataset?.isSubscriptionsFeedPageOne === '1';
const latestArticleId = Number(dataset?.latestArticleId) || 0;

if (isAuthenticated) {
  initInboxUI();
  initWebSocket({
    onNotification: onNotificationReceived,
    onDigest: onNotificationDigestReceived,
  });

  initNewArticlesDigest({
    isAuthenticated,
    isSubscriptionsPage,
    isSubscriptionsFeedPageOne,
    latestArticleId,
  });
}
