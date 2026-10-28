// Runs before first paint (loaded from layout.js) so the saved theme never flashes.
// Keep the storage key in sync with src/config/theme.js.
(function () {
  try {
    var saved = localStorage.getItem("theme");
    if (saved === "light" || saved === "dark" || saved === "system") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) {}
})();
