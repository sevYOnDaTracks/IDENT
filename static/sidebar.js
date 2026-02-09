// Collapsible sidebar injected on each page that has a toolbar.
// Kept framework-free so it works in pywebview (local HTML).
(function () {
  "use strict";

  const getPath = () => {
    try {
      const p = (window.location.pathname || "").toLowerCase();
      return p.split("/").pop() || "";
    } catch (_) {
      return "";
    }
  };

  const isActive = (href) => {
    const current = getPath();
    const target = String(href || "").toLowerCase();
    return current === target;
  };

  const svg = {
    menu:
      '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path></svg>',
    home:
      '<svg class="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M3 11l9-7 9 7"></path><path d="M9 22V12h6v10"></path></svg>',
    user:
      '<svg class="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M20 21a8 8 0 0 0-16 0"></path><circle cx="12" cy="7" r="4"></circle></svg>',
    building:
      '<svg class="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M3 21h18"></path><path d="M5 21V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v14"></path>' +
      '<path d="M9 9h1"></path><path d="M9 12h1"></path><path d="M9 15h1"></path><path d="M14 9h1"></path><path d="M14 12h1"></path><path d="M14 15h1"></path></svg>',
    book:
      '<svg class="sidebar-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M4 19a2 2 0 0 0 2 2h14"></path><path d="M4 5a2 2 0 0 1 2-2h14v18H6a2 2 0 0 0-2 2V5z"></path></svg>',
  };

  const mount = () => {
    const toolbarLeft = document.querySelector(".toolbar .toolbar-inner .toolbar-left");
    if (!toolbarLeft) return;
    if (document.getElementById("app-sidebar")) return; // already mounted

    const overlay = document.createElement("div");
    overlay.className = "sidebar-overlay";
    overlay.id = "sidebar-overlay";
    overlay.setAttribute("aria-hidden", "true");

    const sidebar = document.createElement("aside");
    sidebar.className = "sidebar";
    sidebar.id = "app-sidebar";
    sidebar.setAttribute("aria-label", "Navigation");

    const header = document.createElement("div");
    header.className = "sidebar-header";
    header.innerHTML =
      '<div class="sidebar-brand">' +
      '<div class="sidebar-title">IDENT V1.0</div>' +
      '<div class="sidebar-sub">Navigation rapide</div>' +
      "</div>" +
      '<button class="icon-button sidebar-close" type="button" aria-label="Fermer la navigation" title="Fermer">&times;</button>';

    const nav = document.createElement("nav");
    nav.className = "sidebar-nav";

    const section = document.createElement("div");
    section.className = "sidebar-section-title";
    section.textContent = "";
    nav.appendChild(section);

    const items = [
      { label: "Accueil", href: "home.html", icon: svg.home },
      { label: "Assurés", href: "assures.html", icon: svg.user },
      { label: "Collectivités", href: "collectivites.html", icon: svg.building },
      { label: "Réferentiel", href: "referentiel.html", icon: svg.book },
    ];

    items.forEach((it) => {
      const a = document.createElement("a");
      a.className = "sidebar-item";
      if (isActive(it.href)) a.classList.add("active");
      a.href = it.href;
      a.innerHTML = it.icon + '<span class="sidebar-label"></span>';
      const label = a.querySelector(".sidebar-label");
      if (label) label.textContent = it.label;
      nav.appendChild(a);
    });

    sidebar.appendChild(header);
    sidebar.appendChild(nav);
    overlay.appendChild(sidebar);
    document.body.appendChild(overlay);

    const burger = document.createElement("button");
    burger.className = "button outline toolbar-burger";
    burger.type = "button";
    burger.setAttribute("aria-label", "Ouvrir le menu");
    burger.setAttribute("title", "Menu");
    burger.setAttribute("aria-expanded", "false");
    burger.innerHTML = svg.menu;
    toolbarLeft.insertBefore(burger, toolbarLeft.firstChild);

    const closeBtn = sidebar.querySelector(".sidebar-close");
    const focusables = () => sidebar.querySelectorAll("a.sidebar-item, button.sidebar-close");

    const setFocusable = (enabled) => {
      focusables().forEach((el) => {
        if (enabled) {
          el.removeAttribute("tabindex");
        } else {
          el.setAttribute("tabindex", "-1");
        }
      });
    };

    // Start closed: keep drawer out of the tab order until opened.
    setFocusable(false);

    const open = () => {
      overlay.classList.add("is-open");
      overlay.setAttribute("aria-hidden", "false");
      document.body.classList.add("sidebar-open");
      burger.setAttribute("aria-expanded", "true");
      setFocusable(true);

      const firstItem = nav.querySelector("a.sidebar-item");
      firstItem?.focus?.();
    };

    const close = () => {
      overlay.classList.remove("is-open");
      overlay.setAttribute("aria-hidden", "true");
      document.body.classList.remove("sidebar-open");
      burger.setAttribute("aria-expanded", "false");
      setFocusable(false);
      burger.focus?.();
    };

    const toggle = () => {
      if (overlay.classList.contains("is-open")) close();
      else open();
    };

    burger.addEventListener("click", toggle);
    closeBtn?.addEventListener("click", close);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && overlay.classList.contains("is-open")) close();
    });

    // Close-on-navigation: when user clicks an item, go directly to the target content.
    nav.querySelectorAll("a.sidebar-item").forEach((a) => {
      a.addEventListener("click", (e) => {
        const href = a.getAttribute("href");
        if (!href) return;
        e.preventDefault();
        e.stopPropagation();
        close();
        window.location.assign(href);
      });
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
