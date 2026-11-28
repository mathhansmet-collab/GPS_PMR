// Ajoute les autorisations natives nécessaires.
// Usage : node scripts/patch-native.mjs ios | android
//  • iOS : localisation (premier plan + toujours), boussole, modes d'arrière-plan audio + location.
//  • Android : position précise + arrière-plan, service de premier plan, notifications, vibration, écran allumé.
import { readFileSync, writeFileSync, existsSync } from "node:fs";

const platform = process.argv[2];
if (platform === "android") {
  const man = "android/app/src/main/AndroidManifest.xml";
  if (!existsSync(man)) { console.error("AndroidManifest.xml introuvable :", man); process.exit(1); }
  let x = readFileSync(man, "utf8");
  const perms = ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "ACCESS_BACKGROUND_LOCATION", "FOREGROUND_SERVICE",
    "FOREGROUND_SERVICE_LOCATION", "POST_NOTIFICATIONS", "VIBRATE", "WAKE_LOCK", "MODIFY_AUDIO_SETTINGS"];
  let add = "";
  for (const p of perms) if (!x.includes(`android.permission.${p}"`)) add += `    <uses-permission android:name="android.permission.${p}" />\n`;
  if (!x.includes("android.hardware.location.gps")) add += `    <uses-feature android:name="android.hardware.location.gps" android:required="false" />\n`;
  if (add) x = x.replace(/<\/manifest>\s*$/, add + "</manifest>\n");
  writeFileSync(man, x);
  console.log("✔ AndroidManifest.xml mis à jour");
  process.exit(0);
}
if (platform !== "ios") {
  console.log("Rien à patcher pour", platform || "(aucune plateforme)");
  process.exit(0);
}

const file = "ios/App/App/Info.plist";
if (!existsSync(file)) { console.error("Info.plist introuvable :", file); process.exit(1); }
let plist = readFileSync(file, "utf8");

const strings = {
  NSLocationWhenInUseUsageDescription: "GPS PMR utilise votre position pour vous guider.",
  NSLocationAlwaysAndWhenInUseUsageDescription: "GPS PMR continue de vous guider, écran verrouillé.",
  NSLocationAlwaysUsageDescription: "GPS PMR continue de vous guider, écran verrouillé.",
  NSMotionUsageDescription: "GPS PMR utilise la boussole pour orienter la flèche."
};

let additions = "";
for (const [key, text] of Object.entries(strings)) {
  if (!plist.includes(`<key>${key}</key>`)) additions += `\t<key>${key}</key>\n\t<string>${text}</string>\n`;
}

// Modes d'arrière-plan : audio (voix) + location (GPS)
if (plist.includes("<key>UIBackgroundModes</key>")) {
  plist = plist.replace(/(<key>UIBackgroundModes<\/key>\s*<array>)([\s\S]*?)(<\/array>)/, (m, a, body, c) => {
    let b = body;
    for (const mode of ["audio", "location"]) if (!b.includes(`<string>${mode}</string>`)) b += `\n\t\t<string>${mode}</string>`;
    return a + b + "\n\t" + c;
  });
} else {
  additions += "\t<key>UIBackgroundModes</key>\n\t<array>\n\t\t<string>audio</string>\n\t\t<string>location</string>\n\t</array>\n";
}

const idx = plist.lastIndexOf("</dict>");
plist = plist.slice(0, idx) + additions + plist.slice(idx);
writeFileSync(file, plist);
console.log("✔ Info.plist mis à jour");
