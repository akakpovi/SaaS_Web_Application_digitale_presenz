// Service Worker Presence SaaS PWA
const CACHE_NAME = "presence-cache-v1";

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(clients.claim());
});

// Gestionnaire Fetch obligatoire pour le critère d'installation PWA
self.addEventListener("fetch", (event) => {
  // Pass-through pour laisser passer le trafic réseau normal
  event.respondWith(
    fetch(event.request).catch(() => {
      return new Response("Application hors ligne. Veuillez vérifier votre connexion.");
    })
  );
});

// Réception des Notifications Push
self.addEventListener("push", (event) => {
  let payload = { title: "🚨 Presence Alerte", body: "Changement de statut détecté sur votre site web." };
  try {
    if (event.data) {
      payload = event.data.json();
    }
  } catch (e) {
    if (event.data) payload.body = event.data.text();
  }

  const options = {
    body: payload.body || "Alerte de surveillance.",
    icon: "/icons/icon-192.svg",
    badge: "/icons/icon-192.svg",
    vibrate: [200, 100, 200],
    data: {
      url: payload.url || "/app/dashboard"
    }
  };

  event.waitUntil(
    self.registration.showNotification(payload.title || "Presence Alerte", options)
  );
});

// Clic sur la notification Push
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/app/dashboard";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (let client of windowClients) {
        if (client.url.includes("/app/") && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
