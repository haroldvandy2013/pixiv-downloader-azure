const CACHE_NAME = "pixiv-downloader-cache-v1";
const urlsToCache = [
  "/",
  "/static/manifest.json",
  "/static/style.css",
  "/static/icons/192x192.png",
  "/static/icons/512x512.png"
];

self.addEventListener("install", (event) => {
  console.log('Service Worker installing.');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener('activate', event => {
  console.log('Service Worker activating.');
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(response => {
      return response || fetch(event.request);
    })
  );
});
