import("./chunk-lazy.js");
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}
window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); });
document.addEventListener("visibilitychange", () => {});
