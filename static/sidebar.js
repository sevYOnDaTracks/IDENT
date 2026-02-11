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
    search:
      '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
  };

  const setupToolbar = () => {
    const toolbarLeft = document.querySelector(".toolbar .toolbar-inner .toolbar-left");
    const toolbarRight = document.querySelector(".toolbar .toolbar-inner .toolbar-right");
    if (!toolbarLeft || !toolbarRight) return;

    // Remove "Accueil" button from the right side toolbar.
    toolbarRight.querySelectorAll(".toolbar-home").forEach((el) => el.remove());

    // Move Back/Forward buttons to the left side, right after logos.
    const rightNavButtons = Array.from(toolbarRight.querySelectorAll(".toolbar-nav"));
    if (rightNavButtons.length) {
      const logos = Array.from(toolbarLeft.querySelectorAll(".toolbar-logo"));
      let insertAfter = logos.length ? logos[logos.length - 1] : toolbarLeft.lastElementChild;
      rightNavButtons.forEach((btn) => {
        btn.classList.add("toolbar-left-nav");
        if (insertAfter && insertAfter.parentNode === toolbarLeft) {
          insertAfter.insertAdjacentElement("afterend", btn);
          insertAfter = btn;
        } else {
          toolbarLeft.appendChild(btn);
          insertAfter = btn;
        }
      });
    }

    // Remove the old expandable search (kept from previous UX) if present.
    toolbarRight.querySelectorAll(".toolbar-inline-search").forEach((el) => el.remove());
    document.body.classList.remove("toolbar-quicksearch-open");
    document.body.classList.remove("toolbar-search-open");

    // Keep toolbar search only on the home page.
    const currentPage = getPath();
    const isHomePage = currentPage === "home.html" || currentPage === "";
    if (!isHomePage) return;

    // Inject a permanent center search bar (same behavior as home page search).
    const toolbarCenter = document.querySelector(".toolbar .toolbar-inner .toolbar-center");
    if (!toolbarCenter) return;
    if (toolbarCenter.querySelector(".toolbar-search")) return;
    const form = document.createElement("form");
    form.className = "toolbar-search toolbar-search--shared";
    form.setAttribute("autocomplete", "off");
    form.setAttribute("novalidate", "novalidate");

    const field = document.createElement("div");
    field.className = "toolbar-search-field";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Rechercher un assure ou une collectivite...";
    input.setAttribute("aria-label", "Recherche globale");

    const suggest = document.createElement("div");
    suggest.className = "toolbar-suggest hidden";

    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "button outline toolbar-search-collapse-toggle";
    toggle.setAttribute("aria-label", "Ouvrir la recherche");
    toggle.setAttribute("title", "Recherche");
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = svg.search;

    field.appendChild(input);
    field.appendChild(suggest);
    form.appendChild(field);
    form.appendChild(toggle);
    toolbarCenter.appendChild(form);

    const goToAssure = (nni) => {
      const raw = String(nni || "").trim();
      if (!raw) return;
      const normalized = raw.replace(/\D/g, "") || raw;
      try {
        localStorage.setItem("assure_nni_target", normalized);
      } catch (_) {}
      window.location.href = `assures.html?nir=${encodeURIComponent(normalized)}&from=global`;
    };

    const goToCollect = (numero) => {
      const raw = String(numero || "").trim();
      if (!raw) return;
      try {
        localStorage.setItem("collect_id_target", raw);
      } catch (_) {}
      window.location.href = `collectivites.html?collect=${encodeURIComponent(raw)}&from=global`;
    };

    const clearSuggest = () => {
      suggest.innerHTML = "";
      suggest.classList.add("hidden");
    };

    const collapseMedia = window.matchMedia("(max-width: 1420px)");
    const isCollapsible = () => collapseMedia.matches;
    const isCollapsedOpen = () => form.classList.contains("is-open");

    const closeCollapsed = () => {
      form.classList.remove("is-open");
      document.body.classList.remove("toolbar-search-open");
      toggle.setAttribute("aria-expanded", "false");
    };

    const openCollapsed = () => {
      if (!isCollapsible()) return;
      form.classList.add("is-open");
      document.body.classList.add("toolbar-search-open");
      toggle.setAttribute("aria-expanded", "true");
      window.setTimeout(() => input.focus(), 60);
    };

    const syncCollapseMode = () => {
      const collapsible = isCollapsible();
      form.classList.toggle("is-collapsible", collapsible);
      toggle.tabIndex = collapsible ? 0 : -1;
      toggle.setAttribute("aria-hidden", collapsible ? "false" : "true");
      if (!collapsible) {
        closeCollapsed();
      } else if (!isCollapsedOpen()) {
        document.body.classList.remove("toolbar-search-open");
      }
    };

    const renderSuggest = (assures, collectivites) => {
      suggest.innerHTML = "";

      const buildSection = (title, rows, onClick, formatter) => {
        const section = document.createElement("div");
        section.className = "suggest-section";

        const heading = document.createElement("div");
        heading.className = "suggest-title";
        heading.textContent = title;
        section.appendChild(heading);

        if (!rows.length) {
          const empty = document.createElement("div");
          empty.className = "suggest-empty";
          empty.textContent = "Aucun resultat";
          section.appendChild(empty);
          return section;
        }

        rows.forEach((row) => {
          const item = document.createElement("button");
          item.type = "button";
          item.className = "suggest-item";
          item.innerHTML = formatter(row);
          item.addEventListener("click", () => onClick(row));
          section.appendChild(item);
        });
        return section;
      };

      suggest.appendChild(
        buildSection(
          "Assures",
          assures,
          (r) => goToAssure(r.nir),
          (r) => `<strong>${r.nom_usage || "-"} ${r.prenom_usage || ""}</strong><span>${r.nir || "-"}</span>`
        )
      );
      suggest.appendChild(
        buildSection(
          "Collectivites",
          collectivites,
          (r) => goToCollect(r.numero),
          (r) => `<strong>${r.denom1 || "-"}</strong><span>${r.numero || "-"}</span>`
        )
      );
      suggest.classList.toggle("hidden", !assures.length && !collectivites.length);
    };

    let suggestTimer;
    const fetchSuggest = async () => {
      const query = String(input.value || "").trim();
      if (query.length < 2) {
        clearSuggest();
        return;
      }
      if (!window.pywebview?.api?.search_global) {
        clearSuggest();
        return;
      }
      try {
        const resp = await window.pywebview.api.search_global("", "", query, 8);
        if (resp?.ok !== "true") {
          clearSuggest();
          return;
        }
        const assures = (resp.data?.assures || []).slice(0, 5);
        const collectivites = (resp.data?.collectivites || []).slice(0, 5);
        renderSuggest(assures, collectivites);
      } catch (_) {
        clearSuggest();
      }
    };

    input.addEventListener("input", () => {
      clearTimeout(suggestTimer);
      suggestTimer = setTimeout(fetchSuggest, 250);
    });

    input.addEventListener("focus", () => {
      if (isCollapsible()) openCollapsed();
      if (String(input.value || "").trim().length >= 2) {
        fetchSuggest();
      }
    });

    input.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (isCollapsible() && isCollapsedOpen()) {
          closeCollapsed();
          clearSuggest();
          toggle.focus?.();
          return;
        }
        clearSuggest();
      }
    });

    toggle.addEventListener("click", () => {
      if (!isCollapsible()) return;
      if (!isCollapsedOpen()) {
        openCollapsed();
        return;
      }
      const query = String(input.value || "").trim();
      if (!query) {
        clearSuggest();
        closeCollapsed();
        return;
      }
      clearSuggest();
      closeCollapsed();
      window.location.href = `search_results.html?q=${encodeURIComponent(query)}`;
    });

    document.addEventListener("click", (event) => {
      if (form.contains(event.target)) return;
      clearSuggest();
      if (isCollapsible()) closeCollapsed();
    });

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const query = String(input.value || "").trim();
      if (!query) {
        if (isCollapsible()) openCollapsed();
        return;
      }
      clearSuggest();
      if (isCollapsible()) closeCollapsed();
      window.location.href = `search_results.html?q=${encodeURIComponent(query)}`;
    });

    syncCollapseMode();
    if (typeof collapseMedia.addEventListener === "function") {
      collapseMedia.addEventListener("change", syncCollapseMode);
    } else if (typeof collapseMedia.addListener === "function") {
      collapseMedia.addListener(syncCollapseMode);
    }
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
      { label: "Assures", href: "assures.html", icon: svg.user },
      { label: "Collectivites", href: "collectivites.html", icon: svg.building },
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

    // Apply shared toolbar UX (left nav + quick search).
    setupToolbar();

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
