(function () {
  var allowed = ["light", "dark", "sunny", "sepia"];

  function normalizeTheme(theme) {
    return allowed.indexOf(theme) >= 0 ? theme : "light";
  }

  function applyTheme(theme) {
    var next = normalizeTheme(theme || localStorage.getItem("theme") || "light");
    document.documentElement.dataset.theme = next;
    localStorage.setItem("theme", next);
  }

  window.setTheme = applyTheme;
  window.getTheme = function () {
    return normalizeTheme(document.documentElement.dataset.theme || localStorage.getItem("theme") || "light");
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { applyTheme(); });
  } else {
    applyTheme();
  }
})();
