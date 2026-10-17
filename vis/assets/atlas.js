/* Interaction bridge for the local county geometry and compact navigation. */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  atlas: {
    renderMap: function (payload) {
      const container = document.getElementById("atlas-map");
      if (!container) return window.dash_clientside.no_update;
      // SVG is generated from validated local geography, with escaped county labels.
      container.innerHTML = payload && payload.svg ? payload.svg : "<p>No counties in this view.</p>";
      container.onclick = function (event) {
        const county = event.target.closest("path[data-fips]");
        if (county) window.dash_clientside.set_props("atlas-map-event", {
          data: {fips: county.dataset.fips, sequence: Date.now()}
        });
      };
      return "County map updated.";
    },
    highlight: function (selected) {
      const container = document.getElementById("atlas-map");
      if (!container) return "";
      container.querySelectorAll("path.selected").forEach(function (path) {
        path.classList.remove("selected");
      });
      if (selected && /^\d{5}$/.test(selected)) {
        const county = container.querySelector('path[data-fips="' + selected + '"]');
        if (county) {
          county.classList.add("selected");
          county.parentNode.appendChild(county);
        }
      }
      return selected ? "County selection updated." : "";
    },
    mobileView: function () {
      const context = window.dash_clientside.callback_context;
      const trigger = context.triggered.length ? context.triggered[0].prop_id.split(".")[0] : "";
      const showMap = trigger === "mobile-map";
      const column = document.getElementById("atlas-map-column");
      if (column) column.classList.toggle("mobile-map-open", showMap);
      ["mobile-map", "mobile-list"].forEach(function (id) {
        const button = document.getElementById(id);
        if (button) button.setAttribute("aria-pressed", String((id === "mobile-map") === showMap));
      });
      return showMap ? "Map view" : "List view";
    }
  }
});

document.addEventListener("click", function (event) {
  const menu = event.target.closest("#mobile-menu");
  const navButton = event.target.closest("#atlas-navigation button");
  const sidebar = document.querySelector(".atlas-sidebar");
  const toggle = document.getElementById("mobile-menu");
  if (menu && sidebar) {
    const open = sidebar.classList.toggle("navigation-open");
    toggle.setAttribute("aria-expanded", String(open));
  } else if (navButton && sidebar && toggle) {
    sidebar.classList.remove("navigation-open");
    toggle.setAttribute("aria-expanded", "false");
  }
});
