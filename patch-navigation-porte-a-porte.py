p='gps-pmr.html'; s=open(p,encoding='utf-8').read()
def rep(a,b,c=1):
    global s
    assert s.count(a)==c,(s.count(a),a[:80]); s=s.replace(a,b)

# ---------- 1. Hors-itinéraire : seuil + durée + cooldown par mode ----------
rep('''      // 1. Sortie d'itinéraire → recalcul après 3 positions consécutives hors tracé
      if (p.off > (car ? 50 : 30)) {
        if (!nav.rerouting) {
          nav.offCount++;
          if (nav.offCount >= 3) rerouteFrom(lat, lon);
        }
        updateHud();
        return;
      }
      nav.offCount = 0;''','''      // 1. Sortie d'itinéraire (écart au tracé Valhalla décodé) → recalcul si l'écart dure assez longtemps
      //    Fauteuil : > 20 m pendant > 3 s, pause 8 s • Voiture : > 35 m pendant > 2 s, pause 5 s • Bus/Tram : > 30 m, 3 s, pause 15 s
      const rule = OFFROUTE[activeTransportTab] || OFFROUTE.other;
      if (p.off > rule.dist) {
        if (!nav.offSince) nav.offSince = Date.now();
        nav.offCount++;                                            // pilote l'affichage orange du HUD
        if (!nav.rerouting && Date.now() - nav.offSince > rule.ms) rerouteFrom(lat, lon, rule.cool);
        updateHud();
        return;
      }
      nav.offCount = 0; nav.offSince = 0;''')
rep('    function buildNavState(route) {','''    const OFFROUTE = {
      wheelchair: { dist: 20, ms: 3000, cool: 8000 },
      car:        { dist: 35, ms: 2000, cool: 5000 },
      other:      { dist: 30, ms: 3000, cool: 15000 }
    };
    // Message discret visible aussi en mode navigation (le panneau d'état est masqué pendant le guidage)
    function navToast(msg, ms = 6000) {
      const el = document.getElementById("navToast"); if (!el) return;
      el.textContent = msg; el.style.display = "block"; clearTimeout(navToast._t);
      navToast._t = setTimeout(() => { el.style.display = "none"; }, ms);
    }

    function buildNavState(route) {''')
rep('          nav.offCount = 2;                       // loin du départ prévu : recalcul dès la prochaine position','          nav.offCount = 1; nav.offSince = Date.now() - 60000;   // loin du départ prévu : recalcul dès la prochaine position')
a=s.index("    // Recalcul depuis la position actuelle\n    async function rerouteFrom(lat, lon) {")
b=s.index("    function beginGuidanceState() {")
s=s[:a]+'''    // Recalcul depuis la position actuelle (mêmes options : profil fauteuil complet ou costing auto)
    async function rerouteFrom(lat, lon, cooldown = 15000) {
      if (!nav || nav.rerouting || Date.now() - nav.lastReroute < cooldown) return;
      const offlineMsg = "Hors ligne : impossible de recalculer, rejoignez le tracé";
      if (!navigator.onLine) {                       // le tracé actuel reste affiché sur la carte
        nav.lastReroute = Date.now();
        if (!nav.offlineWarned) { nav.offlineWarned = true; navToast("📴 " + offlineMsg, 8000); speakFR("Pas de réseau. Rejoignez le tracé affiché."); }
        return;
      }
      nav.rerouting = true;
      nav.lastReroute = Date.now();
      speakFR("Vous vous éloignez de l'itinéraire. Recalcul en cours.");
      updateHud();

      const r = currentRoute;
      const stamp = nav.lastReroute;
      const ok = await routeTo(r.destLat, r.destLon, r.destName, { ...r.options, isReroute: true, originOverride: [lon, lat] });
      if (!isNavigating || !nav) return;
      if (ok) {
        beginGuidanceState();
        nav.lastReroute = stamp;
        speakFR("Nouvel itinéraire. " + (currentRoute.steps[0] ? currentRoute.steps[0].instruction : ""));
      } else {
        nav.rerouting = false;
        if (!nav.offlineWarned) { nav.offlineWarned = true; navToast("📴 " + offlineMsg, 8000); speakFR("Recalcul impossible. Rejoignez le tracé affiché."); }
        updateHud();
      }
    }

'''+s[b:]

# ---------- 3. Arrivée au parking : vitesse < 3 km/h pendant 4 s à moins de 15 m, ou bouton ----------
rep('''      // 3. Arrivée
      const remaining = Math.max(0, nav.geo.total - nav.progress);
      if (remaining <= (car ? 25 : 15)) { arriveGuidance(); return; }''','''      // 3. Arrivée
      const remaining = Math.max(0, nav.geo.total - nav.progress);
      const po = currentRoute.options || {};
      if (car && po.isParkingRoute && po.finalDestLat != null) {
        // Trajet voiture → parking → fauteuil : « garé » = < 15 m de la place et vitesse < 3 km/h pendant 4 s (ou bouton « Je suis garé »)
        const dT = distanceMeters(lat, lon, currentRoute.destLat, currentRoute.destLon);
        if (dT <= 15 && (simActive || lastSpeed < 0.83)) {
          nav.slowSince = nav.slowSince || Date.now();
          if (simActive || Date.now() - nav.slowSince >= 4000) { pkParked(); return; }
        } else nav.slowSince = 0;
      } else if (remaining <= (car ? 25 : 15)) { arriveGuidance(); return; }''')
rep('''      if (!nav || nav.arrived) return;
      nav.arrived = true;
      if (!simActive && currentRoute) addHistory''','''      if (!nav || nav.arrived) return;
      nav.arrived = true;
      if (currentRoute && currentRoute.options && currentRoute.options.isParkingRoute && currentRoute.options.finalDestLat != null) { pkParked(); return; }
      if (!simActive && currentRoute) addHistory''')
rep('''      const parkedOpts = currentRoute && currentRoute.options && currentRoute.options.isParkingRoute && currentRoute.options.finalDestLat != null ? currentRoute.options : null;
      speakFR(parkedOpts ? "Vous êtes arrivé au parking." : "Vous êtes arrivé à destination.");
      if ("vibrate" in navigator) { try { navigator.vibrate([200, 100, 200]); } catch {} }
      if (parkedOpts) pkOnParked(parkedOpts);''','''      const backToCar = currentRoute && currentRoute.options && currentRoute.options.isCarReturn;
      speakFR(backToCar ? "Vous êtes revenu à votre voiture." : "Vous êtes arrivé à destination.");
      if ("vibrate" in navigator) { try { navigator.vibrate([200, 100, 200]); } catch {} }
      if (backToCar) pkReturnArrived();''')
rep("if (!options.isReroute && !options.isParkingRoute) addHistory(lat, lon, name, false);","if (!options.isReroute && !options.isParkingRoute && !options.isCarReturn) addHistory(lat, lon, name, false);")

# ---------- 2/3/4 : bloc parking ----------
rep("const PK = { cands: [], target: null, dest: null, timer: null, token: 0, busy: false };","const PK = { cands: [], target: null, dest: null, timer: null, token: 0, busy: false, occupied: [], occBusy: false };")
rep('''    async function pkFetchLive(signal) {
      const feeds = CONFIG.parking.liveFeeds.filter(f => !f.angersOnly || (PK.dest && isNearAngers(PK.dest.lat, PK.dest.lon)));''','''    async function pkFetchLive(signal, near) {
      const ref = near || PK.dest;
      const feeds = CONFIG.parking.liveFeeds.filter(f => !f.angersOnly || (ref && isNearAngers(ref.lat, ref.lon)));''')
rep("const nx = PK.cands.find(x => x !== t && (!x.live || pkAvailable(fresh.find(y => y.id === x.id) || x)));","const nx = PK.cands.find(x => x !== t && !pkIsOccupied(x) && (!x.live || pkAvailable(fresh.find(y => y.id === x.id) || x)));")
rep("      const dest = PK.dest = { lat: destLat, lon: destLon, name: destName };","      if (!PK.dest || distanceMeters(PK.dest.lat, PK.dest.lon, destLat, destLon) > 30) PK.occupied = [];   // nouvelle destination : les places « occupées » de la session précédente sont oubliées\n      const dest = PK.dest = { lat: destLat, lon: destLon, name: destName };")
a=s.index("    // Une fois garé (arrivée au parking) : bascule en mode Fauteuil")
b=s.index("    function clearParkingProposal() {")
s=s[:a]+r'''    // ---- « Place occupée → Suivante » : mémorise la place comme occupée (session) et redirige vers la suivante ----
    function pkIsOccupied(c) { return PK.occupied.some(o => (o.id && o.id === c.id) || distanceMeters(o.lat, o.lon, c.lat, c.lon) < 12); }
    async function pkCollect(lat, lon) {
      const R = CONFIG.parking.radius, dLa = R / 111320, dLo = R / (111320 * Math.cos(lat * Math.PI / 180));
      const local = allPlaces.filter(p => p.cat === "parking").map(p => ({ id: "loc:" + p.id, live: false, name: p.name || "Place PMR", lat: p.lat, lon: p.lon, n: null, source: "Carte locale" }));
      const [live, street] = await Promise.all([
        pkFetchLive(null, { lat, lon }).catch(() => []),
        pkFetchStreet(lat, lon, null).catch(() => []),
        Promise.race([PmrDataUpdater.loadCells(PmrDataUpdater.cellsFor({ s: lat - dLa, n: lat + dLa, w: lon - dLo, e: lon + dLo }, 6), {}), new Promise(r => setTimeout(r, 5000))]).catch(() => null)
      ]);
      return pkRank(pkMerge([...live, ...street, ...pkFromStore(lat, lon), ...local], lat, lon));
    }
    async function pkOccupiedNext() {
      if (!isNavigating || !nav || !currentRoute || PK.occBusy) return;
      PK.occBusy = true; const btn = gid("pkOccBtn"); if (btn) btn.disabled = true;
      try {
        const r = currentRoute, o = r.options || {}, pos = currentPosition();
        if (o.isParkingRoute) PK.occupied.push({ id: PK.target && Math.abs(PK.target.lat - r.destLat) < 1e-5 ? PK.target.id : null, lat: r.destLat, lon: r.destLon });
        // Référence : destination finale (trajet voiture + fauteuil), sinon position GPS actuelle
        const fin = o.isParkingRoute ? (o.finalDestLat != null ? { lat: o.finalDestLat, lon: o.finalDestLon, name: o.finalDestName } : null) : { lat: r.destLat, lon: r.destLon, name: r.destName };
        const ref = fin || (pos ? { lat: pos.lat, lon: pos.lon } : { lat: r.destLat, lon: r.destLon });
        const cands = await pkCollect(ref.lat, ref.lon);
        if (!isNavigating || !nav) return;
        const nx = cands.find(c => !pkIsOccupied(c) && (!c.live || pkAvailable(c)));
        if (!nx) { speakFR("Place occupée. Aucune autre place PMR recensée à proximité."); navToast("🅿️ Aucune autre place PMR recensée à proximité", 7000); return; }
        PK.cands = cands; PK.target = nx; if (fin) PK.dest = fin;
        const opts = fin ? { isParkingRoute: true, finalDestName: fin.name, finalDestLat: fin.lat, finalDestLon: fin.lon, parkingDist: nx.dist } : { isParkingRoute: true };
        const ok = await routeTo(nx.lat, nx.lon, `Parking PMR (${nx.name})`, { ...opts, isReroute: true, originOverride: pos ? [pos.lon, pos.lat] : undefined });
        if (!isNavigating || !nav) return;
        if (!ok) { navToast("Recalcul impossible : réessayez dans un instant", 6000); return; }
        beginGuidanceState(); nav.lastReroute = Date.now();
        const msg = `Place occupée. Nouvel itinéraire vers la place PMR la plus proche à ${nx.dist} mètres${fin ? " de votre destination" : ""}`;
        speakFR(msg); navToast("🅿️ " + msg, 7000);
        sendWatchGuidanceNotification("🅿️ Place occupée", `Nouvelle place : ${nx.name} (${nx.dist} m)`, "gps-pmr-step");
        if (nx.live) pkWatchStart(); else pkWatchStop();
        if (fin) pkLeg(nx, fin).then(leg => { if (PK.target === nx) pkRender(nx, leg, fin); }); else { pkDrawLeg(null); }
      } catch {} finally { PK.occBusy = false; if (btn) btn.disabled = false; pkUpdateActions(); }
    }
    // Boutons d'action rapides pendant le guidage voiture
    function pkUpdateActions() {
      const box = gid("pkActions"); if (!box) return;
      const o = (currentRoute && currentRoute.options) || {};
      const on = !!(isNavigating && nav && !nav.arrived && currentRoute && activeTransportTab === "car");
      const rem = on ? Math.max(0, nav.geo.total - nav.progress) : Infinity;
      const showOcc = on && (!!o.isParkingRoute || rem <= 150), showPark = on && !!o.isParkingRoute && o.finalDestLat != null;
      gid("pkOccBtn").hidden = !showOcc; gid("pkParkedBtn").hidden = !showPark;
      box.style.display = (showOcc || showPark) ? "flex" : "none";
    }

    // ---- Stationnement mémorisé : « Ma voiture garée » + « Retour à ma voiture » ----
    const PARK_KEY = "gps_pmr_parked_v1";
    let parkedMarker = null, parkedBusy = false;
    function pkLoadParked() { try { const j = JSON.parse(localStorage.getItem(PARK_KEY) || "null"); return j && isFinite(j.lat) && isFinite(j.lon) ? j : null; } catch { return null; } }
    function pkSaveParked(v) { try { if (v) localStorage.setItem(PARK_KEY, JSON.stringify(v)); else localStorage.removeItem(PARK_KEY); } catch {} }
    function pkShowParkedMarker() {
      if (parkedMarker) { parkedMarker.remove(); parkedMarker = null; }
      const v = pkLoadParked(); if (!v || typeof map === "undefined" || !map) return;
      const el = document.createElement("div"); el.className = "pk-pin parked"; el.textContent = "🚗 Ma voiture garée";
      const when = new Date(v.ts).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
      parkedMarker = new maplibregl.Marker({ element: el }).setLngLat([v.lon, v.lat]).setPopup(new maplibregl.Popup().setHTML(`<b>Ma voiture garée</b><br>${escapeHTML(v.label || "")}<br><small>${when}</small>`)).addTo(map);
    }
    function pkReturnRefresh() {
      const bar = gid("pkReturnBar"); if (!bar) return;
      bar.style.display = (pkLoadParked() && !isNavigating && activeTransportTab === "wheelchair") ? "flex" : "none";
    }
    // Garé (détection automatique ou bouton) → mémorise, bascule en Fauteuil et calcule le dernier tronçon
    async function pkParked() {
      const o = currentRoute && currentRoute.options;
      if (parkedBusy || !o || o.finalDestLat == null) return;
      parkedBusy = true; pkWatchStop();
      try {
        const wasSim = simActive, pos = currentPosition() || { lat: currentRoute.destLat, lon: currentRoute.destLon };
        const label = String(currentRoute.destName || "").replace(/^Parking PMR \((.*)\)$/, "$1") || "Stationnement";
        pkSaveParked({ lat: pos.lat, lon: pos.lon, ts: Date.now(), label });
        pkShowParkedMarker();
        clearTimeout(arriveTimer); if (nav || isNavigating) stopGuidance();
        const sd = selectedDest; selectedDest = null;          // évite le double calcul de switchModeTab : on calcule nous-mêmes depuis le stationnement
        switchModeTab("wheelchair"); selectedDest = sd;
        const ok = await routeTo(o.finalDestLat, o.finalDestLon, o.finalDestName, { originOverride: [pos.lon, pos.lat] });
        speakFR("Vous êtes arrivé au stationnement. Début du guidage en fauteuil vers votre destination.");
        if (ok) startGuidance(wasSim); else setStatus("♿ Garé. Itinéraire fauteuil indisponible : réessayez.", "error");
      } finally { parkedBusy = false; pkReturnRefresh(); }
    }
    async function pkReturnToCar() {
      const v = pkLoadParked(); if (!v) return;
      if (isNavigating) stopGuidance();
      const sd = selectedDest; selectedDest = null;
      if (activeTransportTab !== "wheelchair") switchModeTab("wheelchair");
      selectedDest = sd;
      const pos = currentPosition();
      const ok = await routeTo(v.lat, v.lon, "Ma voiture garée", { isCarReturn: true, originOverride: pos ? [pos.lon, pos.lat] : undefined });
      if (ok) startGuidance(false);
    }
    function pkReturnArrived() {
      const d = gid("pkReturnDone"); if (d) d.hidden = false;
    }
    function pkFreeParked(fromDone, toCar) {
      pkSaveParked(null); if (parkedMarker) { parkedMarker.remove(); parkedMarker = null; }
      const d = gid("pkReturnDone"); if (d) d.hidden = true;
      if (toCar) { if (isNavigating) stopGuidance(); selectedDest = null; gid("destInput").value = ""; switchModeTab("car"); }
      pkReturnRefresh();
      if (!toCar) navToast("Emplacement de la voiture libéré", 3500);
    }
    setTimeout(function boot() { try { pkShowParkedMarker(); pkReturnRefresh(); } catch { setTimeout(boot, 600); } }, 800);

'''+s[b:]

# hooks
rep('''    function updateHud() {
      if (!nav || !currentRoute) return;''','''    function updateHud() {
      try { pkUpdateActions(); } catch {}
      if (!nav || !currentRoute) return;''')
rep('''      if (selectedDest && ((prevMode === "car" && mode !== "car") || (prevMode !== "car" && mode === "car"))) {''','''      try { pkReturnRefresh(); pkUpdateActions(); } catch {}
      if (selectedDest && ((prevMode === "car" && mode !== "car") || (prevMode !== "car" && mode === "car"))) {''')
rep('''      document.body.classList.remove("nav-mode");   // réaffiche les menus''','''      document.body.classList.remove("nav-mode");   // réaffiche les menus
      try { pkUpdateActions(); pkReturnRefresh(); } catch {}''')
rep('''      document.body.classList.add("nav-mode");       // masque les menus du haut et du bas''','''      document.body.classList.add("nav-mode");       // masque les menus du haut et du bas
      try { pkReturnRefresh(); } catch {}''')

# ---------- HTML / CSS ----------
rep('  <div id="voiceOverlay" class="voice-overlay"','''  <div id="navToast" class="nav-toast" role="status" aria-live="polite"></div>
  <div id="pkActions" class="pk-actions" style="display:none;">
    <button id="pkOccBtn" type="button" class="pk-occ" hidden onclick="pkOccupiedNext()">🚫 Place occupée → Suivante</button>
    <button id="pkParkedBtn" type="button" class="pk-parked" hidden onclick="pkParked()">🅿️ Je suis garé → Continuer en Fauteuil</button>
  </div>
  <div id="pkReturnBar" class="pk-return" style="display:none;">
    <button type="button" onclick="pkReturnToCar()">↩️ Retour à ma voiture</button>
    <button type="button" class="pk-free" onclick="pkFreeParked()" aria-label="Libérer l'emplacement mémorisé de la voiture" title="Libérer l'emplacement">✕</button>
  </div>
  <div id="pkReturnDone" class="pk-return-done" role="alertdialog" aria-live="assertive" hidden>
    <b>🚗 Vous êtes revenu à votre voiture</b>
    <div class="pk-row">
      <button type="button" onclick="pkFreeParked(true)">Supprimer le marqueur</button>
      <button type="button" class="go" onclick="pkFreeParked(true, true)">🚗 Mode Voiture</button>
    </div>
  </div>
  <div id="voiceOverlay" class="voice-overlay"''')
rep('    .pk-pin.live { background: #16a34a; }','''    .pk-pin.parked { background: #7c3aed; font-size: 13px; }
    .nav-toast { display: none; position: fixed; z-index: 46; left: 50%; transform: translateX(-50%); top: calc(96px + env(safe-area-inset-top)); width: min(520px, calc(100% - 24px)); background: rgba(20,23,28,.94); color: #fff; font: 600 14px/1.3 system-ui, sans-serif; padding: 10px 14px; border-radius: 14px; text-align: center; box-shadow: 0 6px 18px rgba(0,0,0,.4); }
    .pk-actions { position: fixed; z-index: 47; left: 50%; transform: translateX(-50%); bottom: calc(76px + env(safe-area-inset-bottom)); width: min(440px, calc(100% - 24px)); flex-direction: column; gap: 10px; }
    .pk-actions button { min-height: 60px; font-size: 19px; font-weight: 800; border: none; border-radius: 18px; color: #fff; box-shadow: 0 8px 22px rgba(0,0,0,.4); cursor: pointer; }
    .pk-actions button[hidden] { display: none; }
    .pk-occ { background: #d97706; } .pk-parked { background: #16a34a; }
    .pk-return { position: fixed; z-index: 60; left: 50%; transform: translateX(-50%); bottom: calc(120px + env(safe-area-inset-bottom)); gap: 8px; }
    .pk-return button { min-height: 52px; padding: 0 20px; border-radius: 999px; border: none; background: #7c3aed; color: #fff; font-size: 17px; font-weight: 800; box-shadow: 0 6px 18px rgba(0,0,0,.4); cursor: pointer; }
    .pk-return button.pk-free { background: #475569; padding: 0 16px; }
    .pk-return-done { position: fixed; z-index: 70; left: 50%; top: 50%; transform: translate(-50%, -50%); width: min(380px, calc(100% - 28px)); background: #14171c; color: #fff; border-radius: 20px; padding: 18px; text-align: center; box-shadow: 0 14px 40px rgba(0,0,0,.5); }
    .pk-return-done[hidden] { display: none; }
    .pk-return-done .pk-row { display: flex; gap: 10px; margin-top: 14px; }
    .pk-return-done button { flex: 1; min-height: 52px; border-radius: 14px; border: none; font-size: 15px; font-weight: 800; background: #334155; color: #fff; cursor: pointer; }
    .pk-return-done button.go { background: #16a34a; }
    .pk-pin.live { background: #16a34a; }''')
open(p,'w',encoding='utf-8').write(s)
