/* Service Worker for Web Push - deployed with doorways */
self.addEventListener('push', function(e) {
  var data = {};
  try {
    data = e.data ? e.data.json() : {};
  } catch (_) {}
  var title = data.title || 'Уведомление';
  var opts = {
    body: data.body || '',
    icon: data.icon || '/favicon.ico',
    data: { url: data.url || '/' },
  };
  e.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', function(e) {
  e.notification.close();
  var url = e.notification.data && e.notification.data.url;
  if (url) {
    e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(cs) {
      for (var i = 0; i < cs.length; i++) {
        if (cs[i].url.indexOf(self.location.origin) === 0) {
          cs[i].navigate(url);
          cs[i].focus();
          return;
        }
      }
      if (clients.openWindow) clients.openWindow(url);
    }));
  }
});
