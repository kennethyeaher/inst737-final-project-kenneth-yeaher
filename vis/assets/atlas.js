/* Interaction bridge for the local county geometry and compact navigation. */
window.dash_clientside = Object.assign({}, window.dash_clientside, {
  atlas: {
    renderMap: function (payload) {
      const container = document.getElementById("atlas-map");
      if (!container) return window.dash_clientside.no_update;
      // SVG is generated from validated local geography, with escaped county labels.
      container.innerHTML = payload && payload.svg ? payload.svg : "<p>No counties in this view.</p>";
      const svg = container.querySelector("svg");
      if (svg) container.dataset.originalBox = svg.getAttribute("viewBox");
      let drag = null;
      container.onpointerdown = function (event) {
        if (!svg || event.button !== 0 || event.pointerType === "touch") return;
        drag = {x: event.clientX, y: event.clientY, box: svg.getAttribute("viewBox").split(" ").map(Number)};
        container.dataset.dragged = "";
      };
      container.onpointermove = function (event) {
        if (!drag) return;
        const dx = event.clientX - drag.x;
        const dy = event.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) < 5) return;
        container.dataset.dragged = "true";
        const bounds = svg.getBoundingClientRect();
        const scale = Math.max(drag.box[2] / bounds.width, drag.box[3] / bounds.height);
        svg.setAttribute("viewBox", [drag.box[0] - dx * scale, drag.box[1] - dy * scale, drag.box[2], drag.box[3]].join(" "));
      };
      container.onpointerup = container.onpointerleave = function () { drag = null; };
      container.onclick = function (event) {
        if (container.dataset.dragged === "true") {
          container.dataset.dragged = "";
          return;
        }
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
  const zoom = event.target.closest("#atlas-zoom-in, #atlas-zoom-out, #atlas-zoom-reset");
  if (zoom) {
    const container = document.getElementById("atlas-map");
    const svg = container && container.querySelector("svg");
    if (svg && container.dataset.originalBox) {
      if (zoom.id === "atlas-zoom-reset") {
        svg.setAttribute("viewBox", container.dataset.originalBox);
      } else {
        const box = svg.getAttribute("viewBox").split(" ").map(Number);
        const original = container.dataset.originalBox.split(" ").map(Number);
        const factor = zoom.id === "atlas-zoom-in" ? .7 : 1 / .7;
        const width = Math.min(original[2] * 2, Math.max(original[2] / 16, box[2] * factor));
        const height = width * box[3] / box[2];
        svg.setAttribute("viewBox", [box[0] + (box[2] - width) / 2, box[1] + (box[3] - height) / 2, width, height].join(" "));
      }
    }
  }
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
