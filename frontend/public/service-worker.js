// Ryliox no longer uses a service worker: the app needs its local server for
// everything, and a cached shell made a stopped server look like a working app.
// Browsers that installed the old worker fetch this file on their next update
// check. It deletes the old caches and unregisters itself. It has no fetch
// handler, so requests go straight to the network.
self.addEventListener('install', () => self.skipWaiting());

self.addEventListener('activate', event => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter(key => key.startsWith('ryliox')).map(key => caches.delete(key)));
      await self.registration.unregister();
    })()
  );
});
