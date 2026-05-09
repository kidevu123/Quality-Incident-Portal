self.addEventListener("push", function (event) {
  var data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (err) {
      data = { title: "Nexus Resolve", body: event.data.text() };
    }
  }
  var title = data.title || "Nexus Resolve";
  var options = {
    body: data.body || "New ticket activity.",
    icon: "/static/brand/icon-192.png",
    badge: "/static/brand/badge-96.png",
    tag: data.tag || "nexus-resolve",
    data: {
      url: data.url || "/notifications/"
    },
    timestamp: data.timestamp || Date.now()
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var url = event.notification.data && event.notification.data.url ? event.notification.data.url : "/notifications/";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
      for (var i = 0; i < clientList.length; i += 1) {
        var client = clientList[i];
        if ("focus" in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
      return undefined;
    })
  );
});
