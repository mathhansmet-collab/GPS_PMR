// sw.js — cache hors-ligne de GPS PMR (à placer dans le même dossier que gps-pmr.html, servi en HTTPS)
const APP_CACHE = "gpspmr-app-v2";
const TILE_CACHE = "gpspmr-tiles-v1";
const TILE_HOSTS = ["tiles.openfreemap.org"];
const LIB_HOSTS = ["unpkg.com"];
const MAX_TILES = 8000;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));

// v2 : les paquets hors ligne (tuiles, polices, pictogrammes) passent par le même cache de tuiles
async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > max) await Promise.all(keys.slice(0, keys.length - max).map(k => cache.delete(k)));
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Page de l'application : réseau d'abord, copie locale si hors ligne
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      const cache = await caches.open(APP_CACHE);
      try {
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      } catch {
        return (await cache.match(req)) || (await cache.match(self.registration.scope)) || Response.error();
      }
    })());
    return;
  }

  // Tuiles de carte : cache d'abord (les URL de tuiles sont versionnées)
  if (TILE_HOSTS.includes(url.hostname) && !url.pathname.startsWith("/styles/")) {
    event.respondWith((async () => {
      const cache = await caches.open(TILE_CACHE);
      const hit = await cache.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res.ok) { cache.put(req, res.clone()); trim(TILE_CACHE, MAX_TILES); }
        return res;
      } catch { return Response.error(); }
    })());
    return;
  }

  // Style de carte et bibliothèque MapLibre : copie locale tout de suite, mise à jour en arrière-plan
  if (TILE_HOSTS.includes(url.hostname) || LIB_HOSTS.includes(url.hostname)) {
    event.respondWith((async () => {
      const cache = await caches.open(APP_CACHE);
      const hit = await cache.match(req);
      const net = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
      return hit || (await net) || Response.error();
    })());
  }
});
