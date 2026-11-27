// sw.js — GPS PMR (PWA) · v11 (cache applicatif gps-pmr-app-v11)
// À placer À CÔTÉ de index.html (ex. https://<compte>.github.io/GPS_PMR/sw.js). Servi en HTTPS, portée = son dossier.
//
// Stratégies :
//  • Fichiers de l'application (HTML, manifest, icônes) : RÉSEAU D'ABORD (mises à jour GitHub dès qu'il y a du réseau),
//    repli sur la copie locale si le réseau est absent ou trop lent → ouverture instantanée hors ligne.
//  • Tuiles de carte : CACHE D'ABORD dans un cache dédié, plafonné à 2500 entrées.
//  • Temps réel (positions bus/tram, GTFS-RT, Valhalla, Open-Meteo, Supabase) : RÉSEAU SEUL, jamais mis en cache.
//  • Données (Accèslibre, OpenData…) : RÉSEAU D'ABORD + copie locale (hors ligne = dernières fiches connues).
//  • Style de carte et bibliothèques (MapLibre) : copie locale immédiate + mise à jour en arrière-plan.
// Les requêtes POST (Overpass, Valhalla, Supabase écriture) ne passent jamais par le cache ; l'application mémorise
// elle-même lieux et dernier itinéraire (IndexedDB / localStorage).

const APP_CACHE  = "gps-pmr-app-v11";
const TILE_CACHE = "gps-pmr-tiles-v1";
const DATA_CACHE = "gps-pmr-data-v1";
const MAX_TILES = 3000;   // = plafond du téléchargement de zone (sinon les premières tuiles d'un pack seraient effacées)
const MAX_DATA  = 400;
const NET_TIMEOUT_APP  = 3500;   // ms avant de servir la copie locale d'un fichier de l'appli
const NET_TIMEOUT_DATA = 7000;

// Bibliothèques épinglées, préchargées à l'installation (avatar 3D Three.js + carte MapLibre) : tout fonctionne hors connexion.
// Deux CDN : si le premier échoue, le second est mémorisé (l'application demande jsDelivr quand unpkg ne répond pas).
const LIBS = [
  "https://unpkg.com/three@0.149.0/build/three.min.js", "https://cdn.jsdelivr.net/npm/three@0.149.0/build/three.min.js",
  "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js", "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css"
];
const SHELL = ["./", "index.html", "accueil.html", "manifest.json", "icons/icon-192.png", "icons/icon-512.png", "icons/icon-maskable-512.png", "icons/apple-touch-icon.png"];

const TILE_HOSTS = ["tiles.openfreemap.org", "tile.openstreetmap.org", "a.tile.openstreetmap.org", "b.tile.openstreetmap.org", "c.tile.openstreetmap.org",
  "basemaps.cartocdn.com", "tiles.basemaps.cartocdn.com", "a.basemaps.cartocdn.com", "b.basemaps.cartocdn.com", "c.basemaps.cartocdn.com", "d.basemaps.cartocdn.com"];
const LIB_HOSTS  = ["unpkg.com", "cdn.jsdelivr.net"];
const DATA_HOSTS = ["acceslibre.beta.gouv.fr", "data.angers.fr", "tabular-api.data.gouv.fr", "www.data.gouv.fr", "data.gouv.fr", "transport.data.gouv.fr", "www.irigo.fr", "overpass.private.coffee", "overpass.kumi.systems", "overpass-api.de"];
// TEMPS RÉEL STRICT (Network-Only) : jamais de position bus/tram périmée, jamais de calcul d'itinéraire ou de météo en cache
const isRealtime = u =>
  (u.hostname === "data.angers.fr" && /position|temps-?reel|-tr\/|parking|disponib/i.test(u.pathname)) ||
  u.hostname === "valhalla1.openstreetmap.de" || u.hostname === "api.open-meteo.com" || u.hostname.endsWith(".supabase.co") ||
  /gtfs-?rt|vehicle-?positions|service-?alerts|trip-?updates|realtime|\.pb$/i.test(u.pathname);
const isIgnTile  = u => u.hostname === "data.geopf.fr" && /\/(wmts|tms)/i.test(u.pathname);
const isStyle    = u => u.pathname.startsWith("/styles/") || /\/style\.json$/.test(u.pathname);   // description de la carte : toujours rafraîchie
const isTile     = u => (TILE_HOSTS.includes(u.hostname) && !isStyle(u)) || isIgnTile(u);

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(APP_CACHE);
    await Promise.all(SHELL.map(u => cache.add(new Request(u, { cache: "reload" })).catch(() => {})));   // un fichier manquant n'empêche pas l'installation
    await Promise.all(LIBS.map(u => cache.add(new Request(u, { mode: "cors" })).catch(() => {})));       // idem : l'échec d'un CDN n'empêche pas l'installation
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => event.waitUntil((async () => {
  // Migration : l'ancien cache de tuiles (v3) est recopié dans le nouveau pour ne pas perdre un pack déjà téléchargé
  try {
    if (await caches.has("gpspmr-tiles-v1")) {
      const old = await caches.open("gpspmr-tiles-v1"), neu = await caches.open(TILE_CACHE);
      const keys = (await old.keys()).slice(-MAX_TILES);
      await Promise.all(keys.map(async k => { const r = await old.match(k); if (r) await neu.put(k, r); }));
      await caches.delete("gpspmr-tiles-v1");
    }
  } catch {}
  for (const k of await caches.keys()) {
    if (k.startsWith("gpspmr-app-") || (k.startsWith("gps-pmr-app-") && k !== APP_CACHE)) await caches.delete(k);
  }
  await self.clients.claim();
})()));

self.addEventListener("message", e => {
  const d = e.data;
  if (d === "SKIP_WAITING" || (d && d.type === "SKIP_WAITING")) self.skipWaiting();
  // « Actualiser les données » : purge des données d'accessibilité en cache (les packs hors ligne ont leur propre cache, conservé)
  if (d && d.type === "CLEAR_PMR_DATA_CACHE") {
    e.waitUntil((async () => {
      let ok = false;
      try { ok = await caches.delete(DATA_CACHE); } catch (err) {}
      const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      wins.forEach(c => { try { c.postMessage({ type: "PMR_DATA_CACHE_CLEARED", ok }); } catch (err) {} });
    })());
  }
});

async function trim(name, max) {
  const cache = await caches.open(name), keys = await cache.keys();
  if (keys.length > max) await Promise.all(keys.slice(0, keys.length - max).map(k => cache.delete(k)));
}

// Réseau d'abord ; si le réseau échoue ou dépasse `ms`, on sert la copie locale (le réseau continue et met la copie à jour)
async function networkFirst(req, cacheName, ms, fallbackKeys = []) {
  const cache = await caches.open(cacheName);
  const net = fetch(req).then(res => { if (res && (res.ok || res.type === "opaque")) cache.put(req, res.clone()).then(() => cacheName === DATA_CACHE && trim(DATA_CACHE, MAX_DATA)); return res; });
  const timer = new Promise(r => setTimeout(() => r(null), ms));
  try {
    const first = await Promise.race([net.catch(() => null), timer]);
    if (first) return first;
    const hit = await cache.match(req);
    if (hit) return hit;
    return await net;                                   // pas de copie : on attend le réseau
  } catch {
    const hit = (await cache.match(req)) || (await Promise.all(fallbackKeys.map(k => cache.match(k)))).find(Boolean);
    return hit || Response.error();
  }
}

self.addEventListener("fetch", event => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // 0) Temps réel : on ne touche à rien, la requête part directement sur le réseau
  if (url.origin !== self.location.origin && isRealtime(url)) return;

  // 1) Fichiers de l'application
  if (url.origin === self.location.origin) {
    event.respondWith((async () => {
      try { return await networkFirst(req, APP_CACHE, NET_TIMEOUT_APP, req.mode === "navigate" ? ["index.html", "./"] : []); }
      catch { return Response.error(); }
    })());
    return;
  }

  // 2) Tuiles : cache d'abord (cache dédié, 2500 max)
  if (isTile(url)) {
    event.respondWith((async () => {
      const cache = await caches.open(TILE_CACHE);
      const hit = await cache.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res.ok) { cache.put(req, res.clone()).then(() => trim(TILE_CACHE, MAX_TILES)); }
        return res;
      } catch { return Response.error(); }
    })());
    return;
  }

  // 3) Données lieux / accessibilité : réseau d'abord + copie locale
  if (DATA_HOSTS.includes(url.hostname)) {
    event.respondWith(networkFirst(req, DATA_CACHE, NET_TIMEOUT_DATA).catch(() => Response.error()));
    return;
  }

  // 4) Style de carte et bibliothèques : copie locale tout de suite, mise à jour en arrière-plan
  if (TILE_HOSTS.includes(url.hostname) || LIB_HOSTS.includes(url.hostname)) {
    event.respondWith((async () => {
      const cache = await caches.open(APP_CACHE);
      const hit = await cache.match(req, { ignoreVary: true });
      const net = fetch(req).then(res => { if (res.ok) cache.put(req, res.clone()); return res; }).catch(() => null);
      return hit || (await net) || Response.error();
    })());
  }
});


// ===== Alertes montre : actions des notifications (Étape suivante / Arrêter) =====
// La page ouverte reçoit l'action par postMessage ; sans page ouverte, un simple clic ouvre l'appli.
self.addEventListener("notificationclick", event => {
  const action = event.action || "";
  event.notification.close();
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    wins.forEach(c => { try { c.postMessage({ type: "watch-action", action: action || "open", tag: event.notification.tag }); } catch (e) {} });
    if (action === "next-step" || action === "stop-gps") return;                    // actions silencieuses : pas besoin de rouvrir l'appli
    const target = (event.notification.data && event.notification.data.url) || self.registration.scope;
    const visible = wins.find(c => "focus" in c);
    if (visible) { try { return await visible.focus(); } catch (e) {} }
    return self.clients.openWindow(target);
  })());
});
