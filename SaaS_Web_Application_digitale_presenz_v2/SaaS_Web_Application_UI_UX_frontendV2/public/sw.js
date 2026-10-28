/* Presence service worker — Web Push only.
 *
 * A push subscription can only be created from a ServiceWorkerRegistration,
 * so this file is what makes /notifications/push/subscribe/ reachable from the
 * browser. It deliberately does not cache application assets: offline caching
 * is not implemented yet, and a stale cache would hide deployed fixes.
 */

self.addEventListener("push", (event) => {
  let payload = {}
  try {
    payload = event.data ? event.data.json() : {}
  } catch {
    payload = { body: event.data ? event.data.text() : "" }
  }

  const title = payload.title || "Presence"
  const options = {
    body: payload.body || "",
    icon: payload.icon || "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    data: { url: payload.url || "/app/dashboard" },
  }

  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  const target =
    (event.notification.data && event.notification.data.url) || "/app/dashboard"

  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        for (const client of windows) {
          if ("focus" in client) {
            client.navigate(target)
            return client.focus()
          }
        }
        return clients.openWindow(target)
      }),
  )
})
