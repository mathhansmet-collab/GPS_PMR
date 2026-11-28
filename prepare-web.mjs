// Copie l'appli web (index.html, sw.js, accueil.html, manifest, icônes) dans www/, le dossier que Capacitor embarque dans l'application.
// Source unique : les fichiers à la racine du dépôt (les mêmes que ceux publiés par GitHub Pages).
import { mkdirSync, copyFileSync, existsSync, cpSync } from "node:fs";

mkdirSync("www", { recursive: true });
if (!existsSync("index.html")) { console.error("index.html introuvable à la racine du dépôt"); process.exit(1); }
for (const f of ["index.html", "sw.js", "accueil.html", "manifest.json"]) if (existsSync(f)) copyFileSync(f, "www/" + f);
if (existsSync("icons")) cpSync("icons", "www/icons", { recursive: true });
console.log("✔ www/ prêt (index.html + sw.js + accueil + manifest + icônes)");
