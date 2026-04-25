const Storefront = (() => {
  const state = {
    access: localStorage.getItem("anaacoss_access"),
    refresh: localStorage.getItem("anaacoss_refresh"),
    isAuthenticated: Boolean(localStorage.getItem("anaacoss_access")) || document.body?.dataset.userAuthenticated === "true",
    sessionPromise: null,
    user: null,
    addresses: [],
    selectedAddressId: null,
    cart: null,
    cartSelectedIds: new Set(JSON.parse(localStorage.getItem("anaacoss_cart_selected") || "[]")),
    pendingRequests: 0,
    authReturnUrl: "",
    pendingAuthAction: null,
    heroTimer: null,
    categoryMarqueeRaf: null,
    navigationController: null,
    navigationToken: 0,
    bootstrapped: false,
    handlersBound: {
      navigation: false,
      mobileNavigation: false,
      auth: false,
      products: false,
      cart: false,
      location: false,
      dashboardAddress: false,
      accountTrigger: false,
      homeFeed: false,
    },
    homeFeed: {
      page: 1,
      hasNext: true,
      loading: false,
      currentPanel: "sort",
      loadedIds: new Set(),
      filters: {
        sort: "",
        category: "",
        gender: "",
        min_price: "",
        max_price: "",
        brand: "",
        availability: "",
      },
    },
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const defaultSearchSuggestions = [
    { label: "Matte Lipstick", query: "lipstick", icon: "fa-solid fa-wand-magic-sparkles" },
    { label: "Hydrating Serum", query: "serum", icon: "fa-solid fa-droplet" },
    { label: "Daily Moisturizer", query: "moisturizer", icon: "fa-solid fa-spa" },
    { label: "Full Coverage Foundation", query: "foundation", icon: "fa-solid fa-palette" },
    { label: "Vitamin C Skincare", query: "skincare", icon: "fa-solid fa-sun" },
  ];
  const rotatingSearchTerms = [
    "Mascara",
    "Lipstick",
    "Face Wash",
    "Foundation",
    "Serum",
    "Moisturizer",
    "Sunscreen",
    "Kajal",
    "Perfume",
  ];
  let authMessageTimer = null;
  let sharePayload = null;

  function currentUrl() {
    return `${window.location.pathname}${window.location.search}${window.location.hash}`;
  }

  function toast(message) {
    const el = $("[data-toast]");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    window.setTimeout(() => el.classList.remove("show"), 2600);
  }

  function clearAuthMessage() {
    const el = $("[data-auth-message]");
    if (authMessageTimer) {
      window.clearTimeout(authMessageTimer);
      authMessageTimer = null;
    }
    if (el) el.textContent = "";
  }

  function setAuthMessage(message, autoClear = false) {
    const el = $("[data-auth-message]");
    if (!el) return;
    clearAuthMessage();
    el.textContent = message || "";
    if (message && autoClear) {
      authMessageTimer = window.setTimeout(() => {
        if (el) el.textContent = "";
        authMessageTimer = null;
      }, 3500);
    }
  }

  function toggleGlobalLoader(active) {
    const loader = $("[data-global-loader]");
    if (!loader) return;
    loader.classList.toggle("is-visible", Boolean(active));
  }

  function beginPending() {
    state.pendingRequests += 1;
    if (state.bootstrapped) toggleGlobalLoader(true);
  }

  function endPending() {
    state.pendingRequests = Math.max(0, state.pendingRequests - 1);
    if (state.bootstrapped) toggleGlobalLoader(state.pendingRequests > 0);
    else toggleGlobalLoader(false);
  }

  async function runWithPending(task, active = true) {
    if (!active) return task();
    beginPending();
    try {
      return await task();
    } finally {
      endPending();
    }
  }

  async function withLockedButton(button, task) {
    if (!button) return task();
    if (button.disabled) return null;
    button.disabled = true;
    button.classList.add("is-loading");
    button.setAttribute("aria-busy", "true");
    try {
      return await task();
    } finally {
      button.disabled = false;
      button.classList.remove("is-loading");
      button.removeAttribute("aria-busy");
    }
  }

  function setCountBadge(counts, value) {
    counts.forEach((count) => {
      count.textContent = value;
      count.hidden = value < 1;
    });
  }

  function normalizeNavPath(path) {
    const clean = (path || "/").replace(/\/+$/, "") || "/";
    if (clean === "/" || clean === "") return "/";
    if (clean.startsWith("/shop")) return "/shop/";
    if (clean.startsWith("/cart")) return "/cart/";
    if (clean.startsWith("/orders")) return "/orders/";
    if (clean.startsWith("/dashboard")) return "/dashboard/";
    return "/";
  }

  function updateMobileNavState() {
    const current = normalizeNavPath(window.location.pathname);
    $$(".mobile-bottom-nav .mobile-bottom-link").forEach((link) => {
      const href = link.getAttribute("href") || "/";
      const isCurrent = normalizeNavPath(href) === current;
      if (isCurrent) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
  }

  function syncPageChrome() {
    const current = normalizeNavPath(window.location.pathname);
    document.body.classList.toggle("cart-page-active", current === "/cart/");
    document.body.classList.toggle("checkout-flow-active", window.location.pathname.startsWith("/checkout"));
    const checkoutRoot = $("#page-root [data-checkout-mode='true']");
    const inCheckoutMode = Boolean(checkoutRoot);
    document.body.classList.toggle("checkout-mode", inCheckoutMode);
    $$("[data-default-chrome]").forEach((node) => node.classList.toggle("page-chrome-hidden", inCheckoutMode));
    const checkoutHeader = $("[data-checkout-header]");
    checkoutHeader?.classList.toggle("page-chrome-hidden", !inCheckoutMode);
    const checkoutTitle = $("[data-checkout-page-title]");
    if (checkoutTitle) checkoutTitle.textContent = checkoutRoot?.dataset.checkoutTitle || "";
    const checkoutTrail = $("[data-checkout-header-trail]");
    if (checkoutTrail) {
      const walletValue = checkoutRoot?.dataset.checkoutWallet;
      checkoutTrail.innerHTML = walletValue !== undefined
        ? `<span class="checkout-wallet-pill"><i class="fa-solid fa-wallet" aria-hidden="true"></i><span>₹${walletValue}</span></span>`
        : "";
    }
    const search = $("[data-search-box]");
    if (search) {
      const shouldHideSearch = inCheckoutMode || Boolean($("#page-root [data-hide-header-search='true']"));
      search.classList.toggle("is-hidden", shouldHideSearch);
    }
  }

  function fullName(user) {
    if (!user) return "Guest";
    const name = [user.first_name, user.last_name].filter(Boolean).join(" ").trim();
    return name || user.username || "Guest";
  }

  function selectedAddress() {
    return state.addresses.find((item) => String(item.id) === String(state.selectedAddressId)) || null;
  }

  function addressLocationText(address) {
    if (!address) return "Add your delivery address";
    return [address.label, address.city, address.postal_code].filter(Boolean).join(", ");
  }

  function addressFullText(address) {
    return [address.line1, address.line2, address.city, address.state, address.postal_code].filter(Boolean).join(", ");
  }

  function normalizeAddressList(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.results)) return payload.results;
    return [];
  }

  function setAuthTab(mode = "login") {
    $$("[data-auth-tab]").forEach((tab) => tab.classList.toggle("active", tab.dataset.authTab === mode));
    $$("[data-auth-form]").forEach((form) => form.classList.toggle("active", form.dataset.authForm === mode));
  }

  function openModal(modal, trigger) {
    if (!modal) return;
    modal._returnFocusEl = trigger || document.activeElement;
    modal.setAttribute("aria-hidden", "false");
    modal.classList.add("open");
    document.body.classList.add("modal-open");
    const dialog = modal.querySelector('[role="dialog"]');
    const autofocusTarget = modal.querySelector("input, button, select, textarea, a[href], [tabindex]:not([tabindex='-1'])");
    (autofocusTarget || dialog)?.focus?.();
  }

  function closeModal(modal) {
    if (!modal) return;
    const returnFocusEl = modal._returnFocusEl;
    if (modal.contains(document.activeElement)) document.activeElement.blur?.();
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    if (!$$(".modal-shell.open").length) document.body.classList.remove("modal-open");
    if (returnFocusEl && document.contains(returnFocusEl)) returnFocusEl.focus?.();
  }

  function openAuthModal(trigger, options = {}) {
    state.authReturnUrl = options.returnUrl || currentUrl();
    state.pendingAuthAction = options.onSuccess || null;
    setAuthTab(options.tab || trigger?.dataset.authTab || "login");
    clearAuthMessage();
    openModal($("[data-auth-modal]"), trigger);
  }

  function fillCheckoutForm(user, address) {
    const form = $("[data-checkout-form]");
    if (!form) return;
    const addressField = $("[data-checkout-address-input]", form);
    const note = $("[data-checkout-address-note]");
    if (addressField && address?.id) addressField.value = address.id;
    if (note) {
      note.textContent = address
        ? `Delivering to ${address.full_name} at ${address.label}.`
        : "Select or add an address before placing your order.";
    }
  }

  function selectedItemIdsFromUrl() {
    const params = new URLSearchParams(window.location.search);
    const items = params.get("items") || "";
    return items.split(",").map((item) => item.trim()).filter(Boolean);
  }

  function syncSelectedAddressCard(address) {
    const card = $("[data-checkout-selected-card]");
    if (!card || !address) return;
    card.dataset.addressId = address.id;
    const name = $("[data-selected-address-name]", card);
    const line = $("[data-selected-address-line]", card);
    const phone = $("[data-selected-address-phone]", card);
    if (name) name.textContent = address.full_name;
    if (line) line.textContent = addressFullText(address);
    if (phone) phone.textContent = address.phone || "";
    const tags = $(".checkout-selected-address-tags", card);
    if (tags) {
      tags.innerHTML = `${address.is_default ? '<span class="checkout-address-default">Default</span>' : ""}<span class="checkout-address-tag">${(address.label || "Home").toUpperCase()}</span>`;
    }
    card.classList.remove("checkout-selected-address-empty");
  }

  function syncCheckoutContinueLink(page) {
    const continueButton = $("[data-checkout-continue]", page);
    if (!continueButton) return;
    const selectedIds = selectedItemIdsFromUrl();
    const addressId = state.selectedAddressId || $("[data-checkout-selected-card]", page)?.dataset.addressId;
    const params = new URLSearchParams();
    if (selectedIds.length) params.set("items", selectedIds.join(","));
    if (addressId) params.set("address", String(addressId));
    continueButton.setAttribute("href", `${continueButton.dataset.checkoutPaymentUrl}?${params.toString()}`);
  }

  async function startUpiPayment(appName) {
    const page = $("[data-payment-page]");
    const form = $("[data-checkout-form]", page || document);
    if (!page || !form) return;
    const addressId = form.elements.namedItem("address_id")?.value || page.dataset.paymentAddressId;
    const selectedIds = selectedItemIdsFromUrl();
    if (!addressId) {
      toast("Select a saved address to continue");
      return;
    }
    if (!selectedIds.length) {
      toast("Please select at least one item.");
      return;
    }
    const button = $(`[data-upi-pay="${appName}"]`, page);
    await withLockedButton(button, async () => {
      try {
        const data = await api("/api/orders/start-upi/", {
          method: "POST",
          body: JSON.stringify({
            app_name: appName,
            address_id: addressId,
            selected_item_ids: selectedIds,
          }),
        });
        toast(`Opening ${data.selected_payment_method}`);
        window.setTimeout(() => {
          window.location.href = data.pending_url;
        }, 1800);
        window.location.href = data.intent_url;
        window.setTimeout(() => {
          window.location.href = data.fallback_url;
        }, 900);
      } catch (error) {
        toast(flattenError(error));
      }
    });
  }

  async function api(url, options = {}) {
    const { silent = false, ...fetchOptions } = options;
    return runWithPending(async () => {
      const isFormData = fetchOptions.body instanceof FormData;
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 15000);
      const headers = {
        "X-Requested-With": "XMLHttpRequest",
        ...(fetchOptions.headers || {}),
      };
      if (!isFormData) headers["Content-Type"] = "application/json";
      if (state.access) headers.Authorization = `Bearer ${state.access}`;
      try {
        const response = await fetch(url, { ...fetchOptions, headers, signal: controller.signal, credentials: "same-origin" });
        if (response.status === 401 && state.refresh && !url.includes("/api/auth/token/refresh/")) {
          const refreshed = await refreshTokens(controller.signal);
          if (refreshed) return api(url, options);
          clearTokens();
        }
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw data;
        return data;
      } catch (error) {
        if (error?.name === "AbortError") {
          throw { detail: "Request timed out. Please try again." };
        }
        throw error;
      } finally {
        window.clearTimeout(timeout);
      }
    }, !silent);
  }

  function setTokens(access, refresh) {
    state.access = access;
    state.refresh = refresh;
    state.isAuthenticated = true;
    document.body?.setAttribute("data-user-authenticated", "true");
    localStorage.setItem("anaacoss_access", access);
    if (refresh) localStorage.setItem("anaacoss_refresh", refresh);
  }

  function clearTokens() {
    state.access = null;
    state.refresh = null;
    state.isAuthenticated = false;
    state.sessionPromise = null;
    state.user = null;
    state.addresses = [];
    state.selectedAddressId = null;
    document.body?.setAttribute("data-user-authenticated", "false");
    localStorage.removeItem("anaacoss_access");
    localStorage.removeItem("anaacoss_refresh");
  }

  async function refreshTokens(signal = undefined) {
    const response = await fetch("/api/auth/token/refresh/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(state.refresh ? { refresh: state.refresh } : {}),
      signal,
      credentials: "same-origin",
    });
    if (!response.ok) {
      clearTokens();
      return null;
    }
    const data = await response.json().catch(() => ({}));
    setTokens(data.access, data.refresh || state.refresh);
    return data;
  }

  function flattenError(error) {
    if (typeof error === "string") return error;
    return Object.entries(error || {}).map(([key, value]) => {
      const text = Array.isArray(value) ? value.join(", ") : value;
      if (key === "non_field_errors" || key === "detail") return text;
      return `${key}: ${text}`;
    }).join(" ");
  }

  function saveCartSelection() {
    localStorage.setItem("anaacoss_cart_selected", JSON.stringify([...state.cartSelectedIds]));
  }

  function syncCartSelection(cart) {
    const itemIds = new Set((cart?.items || []).map((item) => String(item.id)));
    state.cartSelectedIds = new Set([...state.cartSelectedIds].filter((id) => itemIds.has(String(id))));
    if (!state.cartSelectedIds.size && localStorage.getItem("anaacoss_cart_selected") === null) {
      (cart?.items || []).forEach((item) => state.cartSelectedIds.add(String(item.id)));
    }
    saveCartSelection();
  }

  function selectedCartItems(cart = state.cart) {
    if (!cart?.items?.length) return [];
    return cart.items.filter((item) => state.cartSelectedIds.has(String(item.id)));
  }

  function cartSelectionTotals(cart = state.cart) {
    const items = selectedCartItems(cart);
    const subtotal = items.reduce((sum, item) => sum + Number(item.line_total || 0), 0);
    const originalSubtotal = items.reduce((sum, item) => sum + (Number(item.product?.price || item.unit_price || 0) * Number(item.quantity || 0)), 0);
    const savings = Math.max(0, originalSubtotal - subtotal);
    const couponDiscount = Number(cart?.coupon && Number(cart?.subtotal || 0) > 0 ? (subtotal / Number(cart.subtotal || 1)) * Number(cart.discount || 0) : 0);
    const shipping = subtotal <= 0 ? 0 : (subtotal >= 2500 ? 0 : 149);
    const total = Math.max(0, subtotal - couponDiscount + shipping);
    return {
      items,
      count: items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
      subtotal,
      originalSubtotal,
      savings,
      couponDiscount,
      shipping,
      total,
    };
  }

  function currency(value) {
    return `Rs. ${Math.round(Number(value || 0))}`;
  }

  function homeFeedQuery(page = 1) {
    const params = new URLSearchParams();
    params.set("page", String(page));
    Object.entries(state.homeFeed.filters).forEach(([key, value]) => {
      if (value !== "" && value !== null && value !== undefined) params.set(key, value);
    });
    return `/api/products/?${params.toString()}`;
  }

  function resetHomeFeedState() {
    state.homeFeed.page = 1;
    state.homeFeed.hasNext = true;
    state.homeFeed.loading = false;
    state.homeFeed.loadedIds = new Set();
    $$("[data-home-product-grid] [data-product-id]").forEach((card) => state.homeFeed.loadedIds.add(String(card.dataset.productId)));
  }

  function renderHomeFilterPills() {
    const root = $("[data-home-filter-pills]");
    if (!root) return;
    const labels = [];
    const { sort, category, gender, min_price, max_price, brand, availability } = state.homeFeed.filters;
    if (sort) labels.push({ key: "sort", label: `Sort: ${sort.replace("_", " ")}` });
    if (category) {
      const categoryLabels = category.split(",").filter(Boolean);
      labels.push({ key: "category", label: categoryLabels.length > 1 ? `Categories: ${categoryLabels.length}` : `Category: ${categoryLabels[0]}` });
    }
    if (gender) labels.push({ key: "gender", label: `Gender: ${gender}` });
    if (brand) labels.push({ key: "brand", label: `Brand: ${brand}` });
    if (availability) labels.push({ key: "availability", label: "In Stock" });
    if (min_price || max_price) labels.push({ key: "price", label: `Price: ${min_price || 0}-${max_price || "max"}` });
    if (!labels.length) {
      root.innerHTML = "";
      root.hidden = true;
      syncHomeFilterTriggerState();
      return;
    }
    root.hidden = false;
    root.innerHTML = labels.map((item) => `<button class="home-filter-pill" type="button" data-home-filter-pill="${item.key}">${item.label} <i class="fa-solid fa-xmark"></i></button>`).join("");
    syncHomeFilterTriggerState();
  }

  function setHomeFeedLoading(active) {
    state.homeFeed.loading = active;
    const loader = $("[data-home-feed-loader]");
    if (loader) loader.hidden = !active;
  }

  function setHomeFeedEnd(show) {
    const end = $("[data-home-feed-end]");
    if (end) end.hidden = !show;
  }

  function setHomeFeedCount(count) {
    const badge = $("[data-home-feed-count]");
    if (!badge) return;
    const total = Number(count) || 0;
    badge.textContent = `${total} item${total === 1 ? "" : "s"}`;
  }

  function syncHomeFilterTriggerState() {
    $$("[data-home-filter-open]").forEach((button) => {
      const panel = button.dataset.homeFilterOpen;
      let isActive = false;
      if (panel === "sort") isActive = Boolean(state.homeFeed.filters.sort);
      if (panel === "category") isActive = Boolean(state.homeFeed.filters.category);
      if (panel === "gender") isActive = Boolean(state.homeFeed.filters.gender);
      if (panel === "filter") {
        const { min_price, max_price, brand, availability } = state.homeFeed.filters;
        isActive = Boolean(min_price || max_price || brand || availability);
      }
      button.classList.toggle("is-active", isActive);
    });
  }

  async function loadHomeFeedPage(page, options = {}) {
    const grid = $("[data-home-product-grid]");
    if (!grid || state.homeFeed.loading || (!state.homeFeed.hasNext && page !== 1)) return;
    setHomeFeedLoading(true);
    try {
      const payload = await api(homeFeedQuery(page), { method: "GET", silent: true });
      const results = Array.isArray(payload?.results) ? payload.results : [];
      setHomeFeedCount(payload?.count ?? results.length);
      if (page === 1) {
        grid.innerHTML = results.length ? results.map((product) => productCardHtml(product)).join("") : `<p class="empty-state">No products match these filters.</p>`;
        state.homeFeed.loadedIds = new Set(results.map((product) => String(product.id)));
      } else {
        const fresh = results.filter((product) => !state.homeFeed.loadedIds.has(String(product.id)));
        if (fresh.length) {
          grid.insertAdjacentHTML("beforeend", fresh.map((product) => productCardHtml(product)).join(""));
          fresh.forEach((product) => state.homeFeed.loadedIds.add(String(product.id)));
        }
      }
      state.homeFeed.page = page;
      state.homeFeed.hasNext = Boolean(payload?.next);
      setHomeFeedEnd(!payload?.next && page > 1);
      if (!results.length && page === 1) setHomeFeedEnd(false);
    } catch (error) {
      toast(flattenError(error) || "Unable to load products");
    } finally {
      setHomeFeedLoading(false);
    }
  }

  async function refreshHomeFeed() {
    state.homeFeed.page = 1;
    state.homeFeed.hasNext = true;
    state.homeFeed.loadedIds = new Set();
    setHomeFeedEnd(false);
    await loadHomeFeedPage(1);
  }

  function syncHomeFilterModal() {
    const currentPanel = state.homeFeed.currentPanel;
    const title = $("[data-home-filter-title]");
    const kicker = $("[data-home-filter-kicker]");
    const titles = {
      sort: "Sort By",
      category: "Choose Category",
      gender: "Choose Gender",
      filter: "Advanced Filters",
    };
    $$("[data-home-filter-panel]").forEach((panel) => {
      panel.hidden = panel.dataset.homeFilterPanel !== currentPanel;
    });
    if (title) title.textContent = titles[currentPanel] || "Refine products";
    if (kicker) kicker.textContent = currentPanel === "filter" ? "Refine" : "Browse";
    $$("[data-home-filter-value]").forEach((button) => {
      const key = button.dataset.homeFilterValue;
      button.classList.toggle("active", state.homeFeed.filters[key] === button.dataset.value);
    });
    const categoryForm = $(".home-category-filter-form");
    if (categoryForm) {
      const selectedCategories = state.homeFeed.filters.category ? state.homeFeed.filters.category.split(",").filter(Boolean) : [];
      $$('input[name="category"]', categoryForm).forEach((field) => {
        field.checked = selectedCategories.includes(field.value);
      });
      const clearField = $("[data-home-category-clear]", categoryForm);
      if (clearField) clearField.checked = !selectedCategories.length;
    }
    const form = $(".home-advanced-filter-form");
    if (form) {
      Object.entries(state.homeFeed.filters).forEach(([key, value]) => {
        const field = form.elements.namedItem(key);
        if (field) field.value = value;
      });
    }
  }

  async function copyToClipboard(value) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(value);
        return true;
      }
    } catch {}
    const field = document.createElement("textarea");
    field.value = value;
    field.setAttribute("readonly", "");
    field.style.position = "absolute";
    field.style.left = "-9999px";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    document.body.removeChild(field);
    return copied;
  }

  function productSharePayload(trigger) {
    const title = trigger.dataset.shareTitle || "Anaacoss";
    const url = new URL(trigger.dataset.shareUrl || currentUrl(), window.location.origin).toString();
    const text = trigger.dataset.shareText || `Check out ${title} on Anaacoss.`;
    return { title, text, url };
  }

  async function openNativeShare(payload) {
    if (!navigator.share) return false;
    try {
      await navigator.share(payload);
      return true;
    } catch (error) {
      if (error?.name === "AbortError") return true;
      return false;
    }
  }

  function updateShareModal() {
    const title = $("[data-share-modal-title]");
    const copy = $("[data-share-modal-copy]");
    const nativeBtn = $("[data-share-native]");
    if (title) title.textContent = sharePayload?.title || "Share";
    if (copy) copy.textContent = sharePayload ? `Send ${sharePayload.title} through WhatsApp, Instagram, or any other app.` : "Send this product through WhatsApp, Instagram, or any other app.";
    if (nativeBtn) nativeBtn.hidden = !navigator.share;
  }

  async function openShare(trigger) {
    sharePayload = productSharePayload(trigger);
    const usedNative = await openNativeShare(sharePayload);
    if (usedNative) return;
    updateShareModal();
    openModal($("[data-share-modal]"), trigger);
  }

  function renderSavedAddresses() {
    const root = $("[data-saved-addresses]");
    if (!root) return;
    if (!state.user) {
      root.innerHTML = `<p class="location-empty">Login to see your saved delivery addresses.</p>`;
      return;
    }
    if (!state.addresses.length) {
      root.innerHTML = `<p class="location-empty">No saved addresses yet.</p>`;
      return;
    }
    root.innerHTML = state.addresses.map((address) => `
      <label class="saved-address-option">
        <input type="radio" name="saved_address" value="${address.id}" ${String(state.selectedAddressId) === String(address.id) ? "checked" : ""}>
        <span class="saved-address-copy">
          <strong>${address.full_name}</strong>
          <span class="saved-address-meta">${address.label}${address.is_default ? " - Default" : ""}</span>
          <p>${addressFullText(address)}</p>
        </span>
      </label>
    `).join("");
  }

  function profileAddressCards(addresses = []) {
    if (!addresses.length) {
      return `<p class="location-empty">No saved addresses yet.</p>`;
    }
    return addresses.map((address) => `
      <article class="profile-address-card${address.is_default ? " is-default" : ""}">
        <div class="profile-address-top">
          <strong>${address.label}</strong>
          ${address.is_default ? `<span class="profile-address-badge">Primary</span>` : ""}
        </div>
        <p class="profile-address-name">${address.full_name}${address.phone ? ` - ${address.phone}` : ""}</p>
        <p>${addressFullText(address)}</p>
        <div class="profile-address-actions">
          ${address.is_default ? "" : `<button class="btn btn-ghost btn-small" type="button" data-address-primary="${address.id}">Set primary</button>`}
          <button class="btn btn-ghost btn-small" type="button" data-address-edit="${address.id}">Edit</button>
          <button class="btn btn-ghost btn-small profile-address-delete" type="button" data-address-delete="${address.id}">Delete</button>
        </div>
      </article>
    `).join("");
  }

  function checkoutAddressCards(addresses = []) {
    if (!addresses.length) {
      return `
        <div class="checkout-address-empty">
          <p>No saved addresses yet.</p>
          <a class="btn btn-dark btn-small" href="/add-address/?return=/checkout/" data-spa>Add your first address</a>
        </div>`;
    }
    return addresses.map((address) => `
      <article class="checkout-address-card${String(state.selectedAddressId) === String(address.id) ? " is-selected" : ""}${address.is_default ? " is-default" : ""}" data-checkout-address-card="${address.id}">
        <label class="checkout-address-select">
          <input type="radio" name="checkout_address" value="${address.id}" ${String(state.selectedAddressId) === String(address.id) ? "checked" : ""}>
          <span class="checkout-address-radio"></span>
          <span class="checkout-address-copy">
            <span class="checkout-address-topline">
              <strong>${address.full_name}</strong>
              <span class="checkout-address-tag">${address.label}</span>
              ${address.is_default ? `<span class="checkout-address-default">Default</span>` : ""}
            </span>
            <span>${address.phone}</span>
            <p>${addressFullText(address)}</p>
          </span>
        </label>
        <div class="checkout-address-actions">
          ${address.is_default ? "" : `<button class="btn btn-ghost btn-small" type="button" data-checkout-address-default="${address.id}">Set Default</button>`}
          <a class="btn btn-ghost btn-small" href="/addresses/${address.id}/edit/?return=/checkout/" data-spa>Edit</a>
          <button class="btn btn-ghost btn-small checkout-address-delete" type="button" data-checkout-address-delete="${address.id}">Delete</button>
        </div>
      </article>
    `).join("");
  }

  function profileAddressModalHtml() {
    return `
      <div class="modal-shell" data-address-modal aria-hidden="true">
        <div class="modal-card location-modal-card profile-address-modal" role="dialog" aria-modal="true" tabindex="-1">
          <button class="icon-btn modal-close" type="button" data-address-close><i class="fa-solid fa-xmark"></i></button>
          <div class="location-modal-head">
            <h3 data-address-modal-title>Add address</h3>
          </div>
          <form class="location-modal-body profile-address-form" data-address-form data-address-mode="create">
            <div class="form-grid">
              <input class="lux-input" name="label" placeholder="Label (Home, Work)" required>
              <input class="lux-input" name="full_name" placeholder="Full name" required>
            </div>
            <input class="lux-input" name="phone" placeholder="Phone number" required>
            <input class="lux-input" name="line1" placeholder="Address line 1" required>
            <input class="lux-input" name="line2" placeholder="Address line 2">
            <div class="form-grid">
              <input class="lux-input" name="city" placeholder="City" required>
              <input class="lux-input" name="state" placeholder="State" required>
            </div>
            <div class="form-grid">
              <input class="lux-input" name="postal_code" placeholder="Postal code" required>
              <input class="lux-input" name="country" placeholder="Country" value="India" required>
            </div>
            <label class="profile-address-default">
              <input type="checkbox" name="is_default">
              <span>Set as primary address</span>
            </label>
            <p class="form-note" data-address-message></p>
            <button class="btn btn-dark full" type="submit" data-address-submit>Save address</button>
          </form>
        </div>
      </div>`;
  }

  async function bootstrapSession(force = false) {
    if (state.sessionPromise && !force) return state.sessionPromise;
    state.access = state.access || localStorage.getItem("anaacoss_access");
    state.refresh = state.refresh || localStorage.getItem("anaacoss_refresh");
    state.sessionPromise = (async () => {
      try {
        const user = await api("/api/auth/me/", { silent: true });
        state.user = user;
        state.isAuthenticated = true;
        document.body?.setAttribute("data-user-authenticated", "true");
        return user;
      } catch {
        clearTokens();
        return null;
      } finally {
        state.sessionPromise = null;
      }
    })();
    return state.sessionPromise;
  }

  async function ensureUserProfile() {
    if (state.user) return state.user;
    return bootstrapSession();
  }

  async function updateCartBadge(options = {}) {
    try {
      const cart = await api("/api/cart/", { silent: options.silent });
      setCountBadge($$("[data-cart-count], [data-cart-count-mobile]"), Number(cart.count || 0));
      renderCart(cart);
      return cart;
    } catch {
      return null;
    }
  }

  async function updateWishlistBadge(options = {}) {
    const counts = $$("[data-wishlist-count], [data-wishlist-count-mobile]");
    if (!counts.length) return 0;
    if (!state.access && !state.user && !state.isAuthenticated) {
      setCountBadge(counts, 0);
      return 0;
    }
    try {
      const wishlist = await api("/api/wishlist/", { silent: options.silent });
      setCountBadge(counts, wishlist.length || 0);
      return wishlist.length || 0;
    } catch {
      setCountBadge(counts, 0);
      return 0;
    }
  }

  async function updateDeliveryStrip(options = {}) {
    const strip = $("[data-delivery-strip]");
    const name = $("[data-delivery-name]");
    const location = $("[data-delivery-location]");
    if (!strip || !name || !location) return null;
    const user = await ensureUserProfile();
    if (!user) {
      state.addresses = [];
      state.selectedAddressId = null;
      name.textContent = "Guest";
      location.textContent = "";
      location.hidden = true;
      strip.hidden = false;
      renderSavedAddresses();
      return null;
    }
    try {
      const addresses = normalizeAddressList(await api("/api/auth/addresses/", { silent: options.silent }));
      state.addresses = addresses;
      const preferredAddress = addresses.find((item) => item.is_default) || addresses[0] || null;
      state.selectedAddressId = preferredAddress?.id || null;
      name.textContent = fullName(user);
      location.textContent = preferredAddress ? addressLocationText(preferredAddress) : "";
      location.hidden = !preferredAddress;
      strip.hidden = false;
      renderSavedAddresses();
      fillCheckoutForm(user, preferredAddress);
      return { user, addresses };
    } catch {
      name.textContent = fullName(user);
      location.textContent = "";
      location.hidden = true;
      strip.hidden = false;
      state.addresses = [];
      state.selectedAddressId = null;
      renderSavedAddresses();
      return null;
    }
  }

  async function refreshAddresses(options = {}) {
    const user = await ensureUserProfile();
    if (!user) {
      state.addresses = [];
      state.selectedAddressId = null;
      return [];
    }
    const addresses = normalizeAddressList(await api("/api/auth/addresses/", { silent: options.silent }));
    state.addresses = addresses;
    const preferredAddress = state.addresses.find((item) => item.is_default)
      || state.addresses.find((item) => String(item.id) === String(state.selectedAddressId))
      || state.addresses[0]
      || null;
    state.selectedAddressId = preferredAddress?.id || null;
    renderSavedAddresses();
    return state.addresses;
  }

  function fillAddressForm(form, address = null) {
    if (!form) return;
    const values = address || {
      label: "",
      full_name: state.user ? fullName(state.user) : "",
      phone: state.user?.phone || "",
      line1: "",
      line2: "",
      city: "",
      state: "",
      postal_code: "",
      country: "India",
      is_default: false,
    };
    ["label", "full_name", "phone", "line1", "line2", "city", "state", "postal_code", "country"].forEach((name) => {
      const field = form.elements.namedItem(name);
      if (field) field.value = values[name] || "";
    });
    const defaultField = form.elements.namedItem("is_default");
    if (defaultField) defaultField.checked = Boolean(values.is_default);
  }

  async function navigate(url, push = true) {
    const targetUrl = new URL(url, window.location.origin).toString();
    const token = Date.now();
    state.navigationToken = token;
    state.navigationController?.abort();
    state.navigationController = new AbortController();
    await runWithPending(async () => {
      clearAuthMessage();
      const requestHeaders = { "X-Requested-With": "XMLHttpRequest" };
      if (state.access) requestHeaders.Authorization = `Bearer ${state.access}`;
      let response = await fetch(targetUrl, {
        headers: requestHeaders,
        signal: state.navigationController.signal,
        credentials: "same-origin",
      });
      if (response.status === 401 && state.refresh) {
        const refreshed = await refreshTokens(state.navigationController.signal);
        if (refreshed) {
          requestHeaders.Authorization = `Bearer ${state.access}`;
          response = await fetch(targetUrl, {
            headers: requestHeaders,
            signal: state.navigationController.signal,
            credentials: "same-origin",
          });
        }
      }
      if (response.status === 401) {
        openAuthModal(document.activeElement, { returnUrl: new URL(targetUrl).pathname });
        return;
      }
      const html = await response.text();
      if (state.navigationToken !== token) return;
      const doc = new DOMParser().parseFromString(html, "text/html");
      const nextRoot = doc.querySelector("#page-root");
      if (!nextRoot) {
        window.location.href = targetUrl;
        return;
      }
      $("#page-root").innerHTML = nextRoot.innerHTML;
      document.title = doc.title;
      if (push) history.pushState({}, "", targetUrl);
      bindPage();
      syncPageChrome();
      updateMobileNavState();
      const hash = new URL(targetUrl).hash;
      if (hash) {
        const target = document.querySelector(hash);
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          window.scrollTo({ top: 0, behavior: "smooth" });
        }
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    }, false).catch((error) => {
      if (error?.name === "AbortError") return;
      throw error;
    }).finally(() => {
      if (state.navigationToken === token) {
        state.navigationController = null;
      }
    });
  }

  function bindNavigation() {
    if (state.handlersBound.navigation) return;
    state.handlersBound.navigation = true;
    if (!state.handlersBound.mobileNavigation) {
      state.handlersBound.mobileNavigation = true;
      $$(".mobile-bottom-nav a[data-spa]").forEach((link) => {
        link.addEventListener("click", async (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (link.matches("[data-auth-required]")) {
            const user = await ensureUserProfile();
            if (!user) {
              openAuthModal(link, {
                returnUrl: link.dataset.authReturnUrl || link.getAttribute("href") || currentUrl(),
                tab: link.dataset.authTab || "login",
              });
              return;
            }
          }
          if (normalizeNavPath(link.getAttribute("href")) === normalizeNavPath(window.location.pathname)) return;
          navigate(link.href);
        });
      });
    }
    document.addEventListener("click", async (event) => {
      const link = event.target.closest("a[data-spa]");
      if (!link || link.origin !== location.origin) return;
      if (link.closest(".mobile-bottom-nav")) return;
      if (link.matches("[data-auth-required]")) {
        event.preventDefault();
        const user = await ensureUserProfile();
        if (!user) {
          openAuthModal(link, {
            returnUrl: link.dataset.authReturnUrl || link.getAttribute("href") || currentUrl(),
            tab: link.dataset.authTab || "login",
          });
          return;
        }
      }
      event.preventDefault();
      navigate(link.href);
    });
    window.addEventListener("popstate", () => navigate(location.href, false));
  }

  function bindAuth() {
    if (state.handlersBound.auth) return;
    state.handlersBound.auth = true;
    const modal = $("[data-auth-modal]");

    $$("[data-auth-close]").forEach((btn) => btn.addEventListener("click", () => {
      clearAuthMessage();
      closeModal(modal);
    }));
    modal?.addEventListener("click", (event) => {
      if (event.target === modal) {
        clearAuthMessage();
        closeModal(modal);
      }
    });

    $$("[data-auth-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        clearAuthMessage();
        setAuthTab(btn.dataset.authTab);
      });
    });

    document.addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-auth-open]");
      if (!trigger) return;
      event.preventDefault();
      openAuthModal(trigger, {
        returnUrl: trigger.dataset.authReturnUrl || currentUrl(),
        tab: trigger.dataset.authTab || "login",
      });
    });

    document.addEventListener("click", (event) => {
      const toggle = event.target.closest("[data-password-toggle]");
      if (!toggle) return;
      const field = toggle.closest(".password-field")?.querySelector('input[type="password"], input[type="text"]');
      if (!field) return;
      const visible = field.type === "text";
      field.type = visible ? "password" : "text";
      toggle.setAttribute("aria-label", visible ? "Show password" : "Hide password");
      toggle.setAttribute("aria-pressed", String(!visible));
      const icon = $("i", toggle);
      if (icon) {
        icon.className = visible ? "fa-regular fa-eye" : "fa-regular fa-eye-slash";
      }
    });

    $$("[data-auth-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitter = event.submitter || form.querySelector('[type="submit"]');
        const mode = form.dataset.authForm;
        const payload = Object.fromEntries(new FormData(form).entries());
        await withLockedButton(submitter, async () => {
          try {
            const data = await api(`/api/auth/${mode}/`, { method: "POST", body: JSON.stringify(payload) });
            setTokens(data.access, data.refresh);
            state.user = data.user;
            form.reset();
            closeModal(modal);
            toast(mode === "register" ? "Account created" : "Welcome back");
            await Promise.all([
              updateCartBadge(),
              updateWishlistBadge(),
              updateDeliveryStrip(),
            ]);
            fillCheckoutForm(data.user, selectedAddress());
            const nextAction = state.pendingAuthAction;
            const returnUrl = state.authReturnUrl || currentUrl();
            state.pendingAuthAction = null;
            state.authReturnUrl = "";
            if (nextAction) {
              await nextAction();
            } else if (returnUrl && returnUrl !== currentUrl()) {
              await navigate(returnUrl);
            }
          } catch (error) {
            setAuthMessage(flattenError(error), true);
          }
        });
      });
    });

    document.addEventListener("click", async (event) => {
      const trigger = event.target.closest("[data-auth-logout]");
      if (!trigger) return;
      event.preventDefault();
      await withLockedButton(trigger, async () => {
        try {
          if (state.refresh || state.access) {
            await api("/api/auth/logout/", {
              method: "POST",
              body: JSON.stringify({ refresh: state.refresh }),
            });
          }
        } catch {}
        clearTokens();
        await Promise.all([
          updateCartBadge({ silent: true }).catch(() => null),
          updateWishlistBadge({ silent: true }).catch(() => 0),
        ]);
        toast("Logged out");
        if (window.location.pathname.startsWith("/dashboard") || window.location.pathname.startsWith("/checkout") || window.location.pathname.startsWith("/wishlist") || window.location.pathname.startsWith("/cart")) {
          await navigate("/");
        }
      });
    });
  }

  function bindAccountTrigger() {
    if (state.handlersBound.accountTrigger) return;
    state.handlersBound.accountTrigger = true;
    $$("[data-account-open]").forEach((btn) => btn.addEventListener("click", async () => {
      const user = await ensureUserProfile();
      if (user) {
        navigate("/dashboard/");
        return;
      }
      openAuthModal(btn, { returnUrl: currentUrl() });
    }));
  }

  function bindLocationModal() {
    if (state.handlersBound.location) return;
    state.handlersBound.location = true;
    const modal = $("[data-location-modal]");
    const pincodeInput = $("[data-location-pincode]");

    const closeLocationModal = () => closeModal(modal);
    const openLocationModal = async (trigger) => {
      const user = await ensureUserProfile();
      if (!user) {
        openAuthModal(trigger, {
          returnUrl: currentUrl(),
          onSuccess: async () => {
            await updateDeliveryStrip();
            openModal(modal, trigger);
          },
        });
        return;
      }
      await updateDeliveryStrip();
      openModal(modal, trigger);
    };

    $$("[data-location-open]").forEach((btn) => btn.addEventListener("click", () => openLocationModal(btn)));
    $$("[data-location-close]").forEach((btn) => btn.addEventListener("click", closeLocationModal));
    modal?.addEventListener("click", (event) => {
      if (event.target === modal) closeLocationModal();
    });

    $("[data-location-search]")?.addEventListener("click", () => {
      pincodeInput?.focus();
      toast("Search by pincode or area");
    });

    $("[data-location-current]")?.addEventListener("click", () => {
      if (!navigator.geolocation) {
        toast("Location access is not supported on this device");
        return;
      }
      navigator.geolocation.getCurrentPosition(
        () => toast("Current location detected. Add the nearest address from your saved list."),
        () => toast("Unable to access your current location"),
        { enableHighAccuracy: true, timeout: 8000 },
      );
    });

    pincodeInput?.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const value = pincodeInput.value.trim();
      if (!value) return;
      toast(`Checking delivery for ${value}`);
    });

    document.addEventListener("change", (event) => {
      const addressInput = event.target.closest('input[name="saved_address"]');
      if (!addressInput) return;
      const address = state.addresses.find((item) => String(item.id) === String(addressInput.value));
      if (!address) return;
      state.selectedAddressId = address.id;
      const location = $("[data-delivery-location]");
      if (location) {
        location.textContent = addressLocationText(address);
        location.hidden = false;
      }
      fillCheckoutForm(state.user, address);
      renderSavedAddresses();
      closeLocationModal();
      toast(`Delivery location set to ${address.label}`);
    });
  }

  function productCardHtml(product) {
    const image = product.primary_image || "";
    const hasDiscount = Boolean(product.discount_price);
    return `
      <article class="product-card" data-product-id="${product.id}" data-category="${product.category?.slug || ""}">
        <a class="product-media" href="/product/${product.slug}/" data-spa>
          ${image ? `<img src="${image}" alt="${product.name}" loading="lazy">` : `<div class="image-fallback"><i class="fa-solid fa-spa"></i></div>`}
          ${product.badge ? `<span class="badge product-badge-label">${product.badge}</span>` : ""}
          <div class="quick-actions product-overlay-actions">
            <button type="button" data-wishlist="${product.id}" aria-label="Wishlist"><i class="fa-regular fa-heart"></i></button>
            <button type="button" data-share-product data-share-title="${product.name}" data-share-text="Check out ${product.name} on Anaacoss." data-share-url="/product/${product.slug}/" aria-label="Share"><i class="fa-solid fa-share-nodes"></i></button>
          </div>
          ${product.discount_percent ? `<span class="product-discount-badge">${product.discount_percent}% OFF</span>` : ""}
        </a>
        <div class="product-info">
          <p class="product-brand">${product.brand?.name || ""}</p>
          <a href="/product/${product.slug}/" data-spa><h3>${product.name}</h3></a>
          <p class="product-card-copy">${product.short_description || ""}</p>
          <div class="product-card-meta">
            <div class="rating"><i class="fa-solid fa-star"></i> ${product.rating} <span>${product.review_count} Reviews</span></div>
            ${hasDiscount ? `<span class="product-offer-chip">Special price</span>` : ""}
          </div>
          <div class="price-stack">
            <div class="price-row"><strong>Rs. ${product.final_price}</strong>${hasDiscount ? `<del>Rs. ${product.price}</del>` : ""}</div>
            ${hasDiscount ? `<p class="product-savings">Save ${product.discount_percent}% today</p>` : ""}
          </div>
          <div class="product-card-actions">
            <button class="product-action-btn product-action-btn-primary" type="button" data-add-cart="${product.id}" aria-label="Add to cart"><i class="fa-solid fa-bag-shopping"></i><span>Add</span></button>
            <button class="product-action-btn" type="button" data-quick-view="${product.slug}" aria-label="Quick view"><i class="fa-solid fa-eye"></i><span>View</span></button>
          </div>
        </div>
      </article>`;
  }

  function renderSearchSuggestions(items, query = "") {
    const root = $("[data-suggestions]");
    const box = $("[data-search-box]");
    if (!root || !box) return;
    if (!items.length) {
      root.innerHTML = "";
      root.classList.remove("open");
      return;
    }
    root.innerHTML = items.map((item) => {
      if (item.slug) {
        return `
          <a class="suggestion" href="/product/${item.slug}/" data-spa>
            ${item.primary_image ? `<img src="${item.primary_image}" alt="${item.name}">` : `<div class="image-fallback"><i class="fa-solid fa-spa"></i></div>`}
            <span><strong>${item.name}</strong><br>Rs. ${item.final_price}</span>
          </a>`;
      }
      return `
        <a class="suggestion" href="/shop/?q=${encodeURIComponent(item.query)}">
          <div class="image-fallback"><i class="${item.icon}"></i></div>
          <span><strong>${item.label}</strong><span class="suggestion-meta"><i class="fa-solid fa-arrow-trend-up"></i>${query ? `Search for ${item.query}` : "Trending beauty search"}</span></span>
        </a>`;
    }).join("");
    root.classList.add("open");
  }

  function bindProducts() {
    if (state.handlersBound.products) return;
    state.handlersBound.products = true;
    document.addEventListener("click", async (event) => {
      const add = event.target.closest("[data-add-cart]");
      if (add) {
        event.preventDefault();
        const root = add.closest("[data-product-detail]");
        const quantity = root?.querySelector("[data-quantity]")?.value || 1;
        const variant = root?.querySelector("[data-variant-select]")?.value || "";
        await withLockedButton(add, async () => {
          try {
            await api("/api/cart/add/", {
              method: "POST",
              body: JSON.stringify({ product_id: add.dataset.addCart, quantity, variant_id: variant }),
            });
            toast("Added to bag");
            await updateCartBadge();
          } catch {
            openAuthModal(add, { returnUrl: currentUrl() });
          }
        });
      }

      const wish = event.target.closest("[data-wishlist]");
      if (wish) {
        event.preventDefault();
        await withLockedButton(wish, async () => {
          try {
            const data = await api("/api/wishlist/toggle/", { method: "POST", body: JSON.stringify({ product_id: wish.dataset.wishlist }) });
            setCountBadge($$("[data-wishlist-count], [data-wishlist-count-mobile]"), data.count || 0);
            toast(data.wishlisted ? "Saved to wishlist" : "Removed from wishlist");
          } catch {
            openAuthModal(wish, { returnUrl: currentUrl() });
          }
        });
      }

      const share = event.target.closest("[data-share-product]");
      if (share) {
        event.preventDefault();
        await openShare(share);
      }

      const quick = event.target.closest("[data-quick-view]");
      if (quick) {
        event.preventDefault();
        navigate(`/product/${quick.dataset.quickView}/`);
      }

      const buy = event.target.closest("[data-buy-now]");
      if (buy) {
        event.preventDefault();
        await withLockedButton(buy, async () => {
          try {
            await api("/api/cart/add/", { method: "POST", body: JSON.stringify({ product_id: buy.dataset.buyNow, quantity: 1 }) });
            await navigate("/checkout/");
          } catch {
            openAuthModal(buy, { returnUrl: "/checkout/" });
          }
        });
      }
    });
  }

  function bindShareModal() {
    if (document.body.dataset.shareModalBound === "true") return;
    document.body.dataset.shareModalBound = "true";
    const modal = $("[data-share-modal]");
    if (!modal) return;

    const closeShareModal = () => closeModal(modal);
    $$("[data-share-close]").forEach((btn) => btn.addEventListener("click", closeShareModal));
    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeShareModal();
    });

    $("[data-share-native]")?.addEventListener("click", async () => {
      if (!sharePayload) return;
      const shared = await openNativeShare(sharePayload);
      if (shared) closeShareModal();
    });

    $("[data-share-whatsapp]")?.addEventListener("click", () => {
      if (!sharePayload) return;
      const message = encodeURIComponent(`${sharePayload.text} ${sharePayload.url}`);
      window.open(`https://wa.me/?text=${message}`, "_blank", "noopener,noreferrer");
      closeShareModal();
    });

    $("[data-share-instagram]")?.addEventListener("click", async () => {
      if (!sharePayload) return;
      const copied = await copyToClipboard(sharePayload.url);
      if (copied) toast("Link copied. Paste it in Instagram.");
      window.open("https://www.instagram.com/", "_blank", "noopener,noreferrer");
      closeShareModal();
    });

    $("[data-share-copy]")?.addEventListener("click", async () => {
      if (!sharePayload) return;
      const copied = await copyToClipboard(sharePayload.url);
      toast(copied ? "Product link copied" : "Unable to copy link");
      closeShareModal();
    });
  }

  function bindHomeFeed() {
    const root = $("[data-home-feed-root]");
    if (!root) return;
    resetHomeFeedState();
    renderHomeFilterPills();
    syncHomeFilterTriggerState();
    setHomeFeedEnd(false);
    const modal = $("[data-home-filter-modal]");

    if (!state.handlersBound.homeFeed) {
      state.handlersBound.homeFeed = true;

      document.addEventListener("click", async (event) => {
        const trigger = event.target.closest("[data-home-filter-open]");
        if (trigger) {
          event.preventDefault();
          state.homeFeed.currentPanel = trigger.dataset.homeFilterOpen;
          syncHomeFilterModal();
          openModal(modal, trigger);
          return;
        }

        const option = event.target.closest("[data-home-filter-value]");
        if (option) {
          event.preventDefault();
          state.homeFeed.filters[option.dataset.homeFilterValue] = option.dataset.value;
          syncHomeFilterModal();
          renderHomeFilterPills();
          closeModal(modal);
          await refreshHomeFeed();
          return;
        }

        const pill = event.target.closest("[data-home-filter-pill]");
        if (pill) {
          event.preventDefault();
          const key = pill.dataset.homeFilterPill;
          if (key === "price") {
            state.homeFeed.filters.min_price = "";
            state.homeFeed.filters.max_price = "";
          } else {
            state.homeFeed.filters[key] = "";
          }
          renderHomeFilterPills();
          syncHomeFilterModal();
          await refreshHomeFeed();
          return;
        }

        const closeBtn = event.target.closest("[data-home-filter-close]");
        if (closeBtn) {
          event.preventDefault();
          closeModal(modal);
        }

        const categoryReset = event.target.closest("[data-home-category-reset]");
        if (categoryReset) {
          event.preventDefault();
          state.homeFeed.filters.category = "";
          syncHomeFilterModal();
          renderHomeFilterPills();
          closeModal(modal);
          await refreshHomeFeed();
          return;
        }

        const resetBtn = event.target.closest("[data-home-filter-reset]");
        if (resetBtn) {
          event.preventDefault();
          state.homeFeed.filters = {
            sort: "",
            category: "",
            gender: "",
            min_price: "",
            max_price: "",
            brand: "",
            availability: "",
          };
          syncHomeFilterModal();
          renderHomeFilterPills();
          closeModal(modal);
          await refreshHomeFeed();
        }
      });

      modal?.addEventListener("click", (event) => {
        if (event.target === modal) closeModal(modal);
      });

      modal?.addEventListener("change", (event) => {
        const categoryField = event.target.closest('.home-category-filter-form input[name="category"]');
        if (!categoryField) return;
        const categoryForm = categoryField.closest(".home-category-filter-form");
        const clearField = $("[data-home-category-clear]", categoryForm);
        if (categoryField.hasAttribute("data-home-category-clear")) {
          if (categoryField.checked) {
            $$('input[name="category"]', categoryForm).forEach((field) => {
              if (field !== categoryField) field.checked = false;
            });
          }
          return;
        }
        if (clearField) clearField.checked = false;
      });

      document.addEventListener("submit", async (event) => {
        const categoryForm = event.target.closest(".home-category-filter-form");
        if (categoryForm) {
          event.preventDefault();
          const selectedCategories = $$('input[name="category"]:checked', categoryForm)
            .map((field) => field.value)
            .filter(Boolean);
          state.homeFeed.filters.category = selectedCategories.join(",");
          renderHomeFilterPills();
          syncHomeFilterModal();
          closeModal(modal);
          await refreshHomeFeed();
          return;
        }
        const form = event.target.closest(".home-advanced-filter-form");
        if (!form) return;
        event.preventDefault();
        const payload = new FormData(form);
        ["min_price", "max_price", "brand", "availability"].forEach((key) => {
          state.homeFeed.filters[key] = String(payload.get(key) || "").trim();
        });
        renderHomeFilterPills();
        closeModal(modal);
        await refreshHomeFeed();
      });

      window.addEventListener("scroll", async () => {
        const grid = $("[data-home-product-grid]");
        if (!grid || state.homeFeed.loading || !state.homeFeed.hasNext) return;
        const rect = grid.getBoundingClientRect();
        if (rect.bottom - window.innerHeight < 600) {
          await loadHomeFeedPage(state.homeFeed.page + 1);
        }
      }, { passive: true });
    }
  }

  function bindFilters() {
    const form = $("[data-filter-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      await withLockedButton(submitter, async () => {
        const params = new URLSearchParams(new FormData(form));
        for (const [key, value] of [...params.entries()]) {
          if (!value) params.delete(key);
        }
        const data = await api(`/api/products/?${params.toString()}`);
        const products = data.results || data;
        $("[data-product-grid]").innerHTML = products.map(productCardHtml).join("") || `<p>No products found.</p>`;
        $("[data-result-count]").textContent = `${products.length} products`;
      });
    });
  }

  function renderCart(cart) {
    const itemsRoot = $("[data-cart-items]");
    const summary = $("[data-cart-summary]");
    const couponChipRow = $("[data-coupon-chip-row]");
    const bagMeta = $("[data-cart-bag-meta]");
    const savingsBanner = $("[data-cart-savings-banner]");
    const savingsText = $("[data-cart-savings-text]");
    const stickyCount = $("[data-sticky-order-count]");
    const stickyTotal = $("[data-sticky-order-total]");
    state.cart = cart;
    syncCartSelection(cart);
    const totals = cartSelectionTotals(cart);
    if (itemsRoot) {
      itemsRoot.innerHTML = cart.items.length ? cart.items.map((item, index) => {
        const selected = state.cartSelectedIds.has(String(item.id));
        const originalPrice = Number(item.product?.price || item.unit_price || 0) * Number(item.quantity || 0);
        const finalPrice = Number(item.line_total || 0);
        const discountPercent = originalPrice > finalPrice ? Math.round(((originalPrice - finalPrice) / originalPrice) * 100) : 0;
        const qtyOptions = Array.from({ length: 5 }, (_, idx) => idx + 1)
          .map((qty) => `<option value="${qty}" ${qty === Number(item.quantity) ? "selected" : ""}>Qty: ${qty}</option>`)
          .join("");
        return `
        <article class="cart-item${selected ? " is-selected" : ""}" data-cart-item="${item.id}">
          <div class="item-image-wrap">
            <label class="cart-item-check">
              <input type="checkbox" data-cart-select="${item.id}" ${selected ? "checked" : ""}>
              <span></span>
            </label>
            ${item.product.primary_image ? `<img class="item-image" src="${item.product.primary_image}" alt="${item.product.name}">` : `<div class="item-image image-fallback"></div>`}
          </div>
          <div class="item-info">
            <div class="item-title-row">
              <div>
                <h3>${item.product.name}</h3>
                <p>${item.product.short_description || item.product.brand?.name || "Luxury beauty essential"}</p>
              </div>
              <button class="cart-item-remove" type="button" data-cart-remove="${item.id}" aria-label="Remove item"><i class="fa-solid fa-trash"></i></button>
            </div>
            <div class="item-meta-row">
              <label class="item-meta-pill item-qty-pill">
                <select data-cart-qty-select="${item.id}" aria-label="Select quantity">${qtyOptions}</select>
                <i class="fa-solid fa-angle-down"></i>
              </label>
            </div>
            <div class="item-price-row">
              <strong>${currency(finalPrice)}</strong>
              ${originalPrice > finalPrice ? `<del>${currency(originalPrice)}</del><span class="item-discount">${discountPercent}% OFF</span>` : ""}
            </div>
            <div class="item-return-row"><i class="fa-solid fa-rotate-left"></i><span>7 days return & exchange available</span></div>
          </div>
        </article>${index < cart.items.length - 1 ? `<div class="cart-item-separator"></div>` : ""}`;
      }).join("") : `<p class="empty-state">Your bag is waiting for a ritual.</p>`;
    }
    if (summary) {
      summary.innerHTML = `
        <div class="summary-row"><span>Subtotal</span><strong>${currency(totals.originalSubtotal)}</strong></div>
        <div class="summary-row"><span>Discount</span><strong>- ${currency(totals.savings + totals.couponDiscount)}</strong></div>
        <div class="summary-row"><span>Shipping</span><strong>${currency(totals.shipping)}</strong></div>
        <div class="summary-row total"><span>Total</span><strong>${currency(totals.total)}</strong></div>`;
    }
    if (couponChipRow) {
      if (cart.coupon) {
        couponChipRow.hidden = false;
        couponChipRow.innerHTML = `
          <span class="cart-coupon-chip">
            <i class="fa-solid fa-ticket"></i>
            <span>${cart.coupon.code}</span>
            <button type="button" data-remove-coupon aria-label="Remove coupon"><i class="fa-solid fa-xmark"></i></button>
          </span>`;
      } else {
        couponChipRow.hidden = true;
        couponChipRow.innerHTML = "";
      }
    }
    if (bagMeta) bagMeta.textContent = `${totals.count} item${totals.count === 1 ? "" : "s"} selected | ${currency(totals.total)}`;
    if (savingsBanner && savingsText) {
      const savedAmount = totals.savings + totals.couponDiscount;
      savingsBanner.hidden = savedAmount <= 0;
      savingsText.textContent = `You're saving ₹${Math.round(savedAmount)} on this order`;
    }
    if (stickyCount) stickyCount.textContent = `${totals.count} Item${totals.count === 1 ? "" : "s"} selected for order`;
    if (stickyTotal) stickyTotal.textContent = `Total ₹${Math.round(totals.total)}`;
  }

  function bindCart() {
    updateCartBadge({ silent: true });
    updateWishlistBadge({ silent: true });
    updateDeliveryStrip({ silent: true });
    if (state.handlersBound.cart) return;
    state.handlersBound.cart = true;

    const cartTabs = $$("[data-cart-tab]");
    const cartSections = $$("[data-cart-section]");
    const setActiveCartTab = (targetId) => {
      cartTabs.forEach((item) => item.classList.toggle("is-active", item.dataset.target === targetId));
    };

    if (cartTabs.length && cartSections.length && !window.__anaacossCartSectionObserver) {
      const observer = new IntersectionObserver((entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target?.id) setActiveCartTab(visible.target.id);
      }, {
        rootMargin: "-120px 0px -45% 0px",
        threshold: [0.2, 0.35, 0.5, 0.75],
      });
      cartSections.forEach((section) => observer.observe(section));
      window.__anaacossCartSectionObserver = observer;
    }

    document.addEventListener("click", async (event) => {
      const remove = event.target.closest("[data-cart-remove]");
      if (remove) {
        event.preventDefault();
        await withLockedButton(remove, async () => {
          await api(`/api/cart/items/${remove.dataset.cartRemove}/`, { method: "DELETE", silent: true });
          await updateCartBadge({ silent: true });
        });
        return;
      }

      const tab = event.target.closest("[data-cart-tab]");
      if (tab) {
        event.preventDefault();
        const target = document.getElementById(tab.dataset.target || "");
        if (!target) return;
        setActiveCartTab(target.id);
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }

      const select = event.target.closest("[data-cart-select]");
      if (select) {
        const input = select.matches("input") ? select : $("input", select.closest("label"));
        const itemId = input?.dataset.cartSelect;
        if (!itemId) return;
        if (input.checked) state.cartSelectedIds.add(String(itemId));
        else state.cartSelectedIds.delete(String(itemId));
        saveCartSelection();
        renderCart(state.cart);
        return;
      }

      const deleteSelected = event.target.closest("[data-cart-delete-selected]");
      if (deleteSelected) {
        event.preventDefault();
        await withLockedButton(deleteSelected, async () => {
          for (const itemId of [...state.cartSelectedIds]) {
            await api(`/api/cart/items/${itemId}/`, { method: "DELETE", silent: true });
          }
          state.cartSelectedIds.clear();
          saveCartSelection();
          await updateCartBadge({ silent: true });
        });
        return;
      }

      const wishlistSelected = event.target.closest("[data-cart-move-wishlist]");
      if (wishlistSelected) {
        event.preventDefault();
        await withLockedButton(wishlistSelected, async () => {
          const items = selectedCartItems();
          for (const item of items) {
            await api("/api/wishlist/toggle/", { method: "POST", body: JSON.stringify({ product_id: item.product.id }), silent: true });
            await api(`/api/cart/items/${item.id}/`, { method: "DELETE", silent: true });
          }
          state.cartSelectedIds.clear();
          saveCartSelection();
          await Promise.all([updateCartBadge({ silent: true }), updateWishlistBadge({ silent: true })]);
          toast("Moved selected items to wishlist");
        });
        return;
      }

      const shareSelected = event.target.closest("[data-cart-share-selected]");
      if (shareSelected) {
        event.preventDefault();
        const items = selectedCartItems();
        if (!items.length) {
          toast("Select at least one item to share");
          return;
        }
        sharePayload = {
          title: "Anaacoss Cart",
          text: `Check out ${items.map((item) => item.product.name).join(", ")} on Anaacoss.`,
          url: window.location.href,
        };
        const usedNative = await openNativeShare(sharePayload);
        if (!usedNative) {
          updateShareModal();
          openModal($("[data-share-modal]"), shareSelected);
        }
        return;
      }

      const placeOrder = event.target.closest("[data-cart-place-order]");
      if (placeOrder) {
        event.preventDefault();
        const items = selectedCartItems();
        if (!items.length) {
          toast("Please select at least one item.");
          return;
        }
        saveCartSelection();
        const params = new URLSearchParams({ items: items.map((item) => item.id).join(",") });
        await navigate(`/checkout/?${params.toString()}`);
      }
    });

    document.addEventListener("change", async (event) => {
      const qtySelect = event.target.closest("[data-cart-qty-select]");
      if (!qtySelect) return;
      await withLockedButton(qtySelect, async () => {
        await api(`/api/cart/items/${qtySelect.dataset.cartQtySelect}/`, {
          method: "PATCH",
          body: JSON.stringify({ quantity: Number(qtySelect.value.replace(/\D/g, "")) || Number(qtySelect.value) || 1 }),
          silent: true,
        });
        await updateCartBadge({ silent: true });
      });
    });

    const coupon = $("[data-coupon-form]");
    if (coupon) {
      coupon.addEventListener("submit", async (event) => {
        event.preventDefault();
        const submitter = event.submitter || coupon.querySelector('[type="submit"]');
        await withLockedButton(submitter, async () => {
          try {
            const data = await api("/api/cart/coupon/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(coupon).entries())) });
            renderCart(data);
            coupon.reset();
            toast("Coupon applied");
          } catch (error) {
            toast(flattenError(error));
          }
        });
      });
    }

    document.addEventListener("click", async (event) => {
      const removeCoupon = event.target.closest("[data-remove-coupon]");
      if (!removeCoupon) return;
      event.preventDefault();
      await withLockedButton(removeCoupon, async () => {
        const data = await api("/api/cart/coupon/", { method: "DELETE" });
        renderCart(data);
        toast("Coupon removed");
      });
    });
  }

  function bindCheckout() {
    if ($("[data-checkout-address-page]")) return;
    const list = $("[data-checkout-address-list]");
    const form = $("[data-checkout-form]");
    if (!form && !list) return;
    const urlAddressId = new URLSearchParams(window.location.search).get("address");
    const existingAddressId = form?.elements?.namedItem?.("address_id")?.value || urlAddressId;
    if (existingAddressId && !state.selectedAddressId) state.selectedAddressId = existingAddressId;
    fillCheckoutForm(state.user, selectedAddress());
    if (list) {
      refreshAddresses({ silent: true }).then(() => {
        if (urlAddressId) state.selectedAddressId = urlAddressId;
        list.innerHTML = checkoutAddressCards(state.addresses);
        fillCheckoutForm(state.user, selectedAddress());
      }).catch(() => null);
    }
    if (list && list.dataset.bound !== "true") {
      list.dataset.bound = "true";
      list.addEventListener("change", async (event) => {
        const input = event.target.closest('input[name="checkout_address"]');
        if (!input) return;
        const address = state.addresses.find((item) => String(item.id) === String(input.value));
        if (!address) return;
        state.selectedAddressId = address.id;
        list.innerHTML = checkoutAddressCards(state.addresses);
        fillCheckoutForm(state.user, address);
      });

      list.addEventListener("click", async (event) => {
        const defaultBtn = event.target.closest("[data-checkout-address-default]");
        if (defaultBtn) {
          event.preventDefault();
          await withLockedButton(defaultBtn, async () => {
            try {
              const address = await api(`/api/auth/addresses/${defaultBtn.dataset.checkoutAddressDefault}/set_default/`, { method: "POST" });
              state.addresses = state.addresses.map((item) => ({ ...item, is_default: String(item.id) === String(address.id) }));
              state.selectedAddressId = address.id;
              list.innerHTML = checkoutAddressCards(state.addresses);
              fillCheckoutForm(state.user, address);
              await updateDeliveryStrip({ silent: true });
              toast("Default address updated");
            } catch (error) {
              toast(flattenError(error));
            }
          });
          return;
        }

        const deleteBtn = event.target.closest("[data-checkout-address-delete]");
        if (deleteBtn) {
          event.preventDefault();
          await withLockedButton(deleteBtn, async () => {
            try {
              await api(`/api/auth/addresses/${deleteBtn.dataset.checkoutAddressDelete}/`, { method: "DELETE" });
              await refreshAddresses({ silent: true });
              list.innerHTML = checkoutAddressCards(state.addresses);
              fillCheckoutForm(state.user, selectedAddress());
              await updateDeliveryStrip({ silent: true });
              toast("Address deleted");
            } catch (error) {
              toast(flattenError(error));
            }
          });
        }
      });
    }

    if (!form || form.dataset.bound === "true") return;
    form.dataset.bound = "true";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      const user = await ensureUserProfile();
      if (!user) {
        openAuthModal(submitter, {
          returnUrl: currentUrl(),
          onSuccess: async () => form.requestSubmit(),
        });
        toast("Login to place your order");
        return;
      }
      if (!form.elements.namedItem("address_id")?.value) {
        toast("Select a saved address to continue");
        return;
      }
      await withLockedButton(submitter, async () => {
        try {
          const payload = Object.fromEntries(new FormData(form).entries());
          payload.selected_item_ids = selectedItemIdsFromUrl();
          if (!payload.selected_item_ids.length) payload.selected_item_ids = JSON.parse(localStorage.getItem("anaacoss_cart_selected") || "[]");
          if (!payload.selected_item_ids.length && state.cart?.items?.length) payload.selected_item_ids = state.cart.items.map((item) => item.id);
          const data = await api("/api/orders/", { method: "POST", body: JSON.stringify(payload) });
          toast(`Order #${data.id} placed`);
          localStorage.removeItem("anaacoss_cart_selected");
          state.cartSelectedIds = new Set();
          await updateCartBadge();
          await navigate("/orders/");
        } catch (error) {
          toast(flattenError(error));
        }
      });
    });
  }

  function bindCheckoutAddressPage() {
    const page = $("[data-checkout-address-page]");
    if (!page || page.dataset.bound === "true") return;
    page.dataset.bound = "true";
    const list = $("[data-checkout-address-list]", page);
    const toggle = $("[data-checkout-change]", page);
    const continueButton = $("[data-checkout-continue]", page);
    refreshAddresses({ silent: true }).then(() => {
      if (!state.selectedAddressId) {
        const selectedCard = $("[data-checkout-selected-card]", page);
        if (selectedCard?.dataset.addressId) state.selectedAddressId = selectedCard.dataset.addressId;
      }
      syncCheckoutContinueLink(page);
    }).catch(() => null);
    if (toggle && list) {
      toggle.addEventListener("click", () => {
        const hidden = list.hasAttribute("hidden");
        if (hidden) list.removeAttribute("hidden");
        else list.setAttribute("hidden", "");
      });
    }
    if (list) {
      list.addEventListener("change", (event) => {
        const input = event.target.closest('input[name="checkout_address"]');
        if (!input) return;
        const address = state.addresses.find((item) => String(item.id) === String(input.value));
        if (!address) return;
        state.selectedAddressId = address.id;
        $$("label.checkout-address-picker-item", list).forEach((item) => {
          item.classList.toggle("is-selected", String($("input", item)?.value) === String(address.id));
        });
        syncSelectedAddressCard(address);
        syncCheckoutContinueLink(page);
        list.setAttribute("hidden", "");
      });
    }
    if (continueButton) {
      continueButton.addEventListener("click", async (event) => {
        const selectedIds = selectedItemIdsFromUrl();
        if (!selectedIds.length) {
          event.preventDefault();
          toast("Please select at least one item.");
          return;
        }
        const addressId = state.selectedAddressId || $("[data-checkout-selected-card]", page)?.dataset.addressId;
        if (!addressId) {
          event.preventDefault();
          toast("Select a saved address to continue");
          return;
        }
        syncCheckoutContinueLink(page);
      });
    }
  }

  function bindPaymentPage() {
    const page = $("[data-payment-page]");
    if (!page || page.dataset.bound === "true") return;
    page.dataset.bound = "true";
    const stickyPlaceOrder = $("[data-payment-place-order]");
    const syncPaymentState = () => {
      const selected = $('input[name="payment_method"]:checked', page);
      const isCod = !selected || selected.value === "cod";
      if (stickyPlaceOrder) {
        stickyPlaceOrder.hidden = !isCod;
        stickyPlaceOrder.disabled = !isCod;
      }
    };

    $$("[data-payment-toggle]", page).forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const item = toggle.closest(".payment-accordion-item");
        const panel = item ? $(`#${toggle.getAttribute("aria-controls")}`) : null;
        if (!item || !panel) return;
        const shouldOpen = !item.classList.contains("is-open");
        item.classList.toggle("is-open", shouldOpen);
        toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        panel.hidden = !shouldOpen;
      });
    });

    page.addEventListener("change", (event) => {
      if (event.target.matches('input[name="payment_method"]')) {
        syncPaymentState();
      }
    });

    page.addEventListener("click", (event) => {
      const payBtn = event.target.closest("[data-upi-pay]");
      if (!payBtn) return;
      event.preventDefault();
      startUpiPayment(payBtn.dataset.upiPay);
    });

    const summaryToggle = $("[data-payment-summary-toggle]", page.parentElement || document);
    const summaryPanel = $("#payment-summary-panel");
    if (summaryToggle && summaryPanel) {
      summaryToggle.addEventListener("click", () => {
        const expanded = summaryToggle.getAttribute("aria-expanded") === "true";
        summaryToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
        summaryPanel.hidden = expanded;
      });
    }
    syncPaymentState();
  }

  function bindAddressPage() {
    const form = $("[data-address-page-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      const message = $("[data-address-page-message]");
      await withLockedButton(submitter, async () => {
        try {
          const payload = Object.fromEntries(new FormData(form).entries());
          payload.is_default = form.elements.namedItem("is_default")?.checked || false;
          const addressId = form.dataset.addressId;
          const method = form.dataset.addressMode === "edit" && addressId ? "PATCH" : "POST";
          const endpoint = method === "PATCH" ? `/api/auth/addresses/${addressId}/` : "/api/auth/addresses/";
          await api(endpoint, { method, body: JSON.stringify(payload) });
          await refreshAddresses({ silent: true });
          const returnUrl = form.dataset.addressReturn || "/checkout/";
          await navigate(returnUrl);
        } catch (error) {
          if (message) message.textContent = flattenError(error);
        }
      });
    });
  }

  function bindSearch() {
    const box = $("[data-search-box]");
    const input = $("[data-search-input]");
    const root = $("[data-suggestions]");
    const placeholder = $("[data-search-placeholder]");
    const mic = $("[data-search-mic]");
    const camera = $("[data-search-camera]");
    let timer;
    let rotatingIndex = 0;
    let rotatingTimer = null;
    if (!input || !root || !box || !placeholder) return;

    const runSearch = async (query) => {
      if (query.length < 2) {
        root.classList.remove("open");
        root.innerHTML = "";
        return;
      }
      const data = await api(`/api/products/suggestions/?q=${encodeURIComponent(query)}`, { silent: true });
      renderSearchSuggestions(data.length ? data : defaultSearchSuggestions, query);
    };

    const setPlaceholder = (text, entering = false) => {
      placeholder.textContent = text;
      placeholder.classList.remove("exit");
      if (entering) placeholder.classList.add("visible");
    };

    const rotatePlaceholder = () => {
      if (document.activeElement === input || input.value.trim()) return;
      placeholder.classList.add("exit");
      window.setTimeout(() => {
        rotatingIndex = (rotatingIndex + 1) % rotatingSearchTerms.length;
        setPlaceholder(rotatingSearchTerms[rotatingIndex], true);
      }, 220);
    };

    setPlaceholder(rotatingSearchTerms[rotatingIndex], true);
    rotatingTimer = window.setInterval(rotatePlaceholder, 3000);

    input.addEventListener("focus", () => {
      placeholder.classList.remove("visible", "exit");
      root.classList.remove("open");
    });
    input.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (!input.value.trim()) setPlaceholder(rotatingSearchTerms[rotatingIndex], true);
      }, 120);
    });
    input.addEventListener("input", () => {
      if (input.value.trim()) placeholder.classList.remove("visible", "exit");
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        await runSearch(input.value.trim());
      }, 220);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      const query = input.value.trim();
      if (!query) return;
      navigate(`/shop/?q=${encodeURIComponent(query)}`);
      root.classList.remove("open");
    });

    document.addEventListener("click", (event) => {
      if (!event.target.closest("[data-search-box]")) root.classList.remove("open");
    });

    mic?.addEventListener("click", () => {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        toast("Voice search is not supported on this browser");
        return;
      }
      const recognition = new SpeechRecognition();
      recognition.lang = "en-IN";
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = async (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript?.trim();
        if (!transcript) return;
        input.value = transcript;
        placeholder.classList.remove("visible", "exit");
        await runSearch(transcript);
        toast(`Showing results for ${transcript}`);
        navigate(`/shop/?q=${encodeURIComponent(transcript)}`);
      };
      recognition.onerror = () => toast("Voice search could not start");
      recognition.start();
    });

    camera?.addEventListener("change", () => {
      const file = camera.files?.[0];
      if (!file) return;
      const matched = defaultSearchSuggestions.find((item) => file.name.toLowerCase().includes(item.query)) || defaultSearchSuggestions[0];
      input.value = matched.query;
      runSearch(matched.query);
      toast(`Photo selected. Showing results for ${matched.label}`);
      camera.value = "";
    });
  }

  function bindNewsletter() {
    const form = $("[data-newsletter]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      await withLockedButton(submitter, async () => {
        await api("/api/newsletter/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
        form.reset();
        toast("Subscribed");
      });
    });
  }

  function reviewHtml(review) {
    const stars = Array.from({ length: 5 }, (_, index) => `<i class="fa-${index < review.rating ? "solid" : "regular"} fa-star"></i>`).join("");
    const images = (review.images || []).map((image) => `<img src="${image.url}" alt="${image.alt_text || review.title}">`).join("");
    return `
      <article class="review-card">
        <div class="review-head"><strong>${review.user_name || "Customer"}</strong><span>${stars}</span></div>
        <h3>${review.title}</h3>
        <p>${review.body}</p>
        ${images ? `<div class="review-images">${images}</div>` : ""}
      </article>`;
  }

  function setInteractiveStars(root, value, selector, activeClass = "is-active") {
    if (!root) return;
    const rating = Number(value) || 0;
    root.dataset.selectedRating = String(rating);
    $$(selector, root).forEach((button) => {
      const starValue = Number(button.dataset.orderReviewStar || button.dataset.reviewRating || 0);
      const active = starValue <= rating;
      button.classList.toggle(activeClass, active);
      button.setAttribute("aria-pressed", String(active));
      const icon = $("i", button);
      if (icon) icon.className = `${active ? "fa-solid" : "fa-regular"} fa-star`;
    });
  }

  function bindOrderReviewActions() {
    if (document.body.dataset.orderReviewBound === "true") return;
    document.body.dataset.orderReviewBound = "true";
    document.addEventListener("click", (event) => {
      const star = event.target.closest("[data-order-review-star]");
      if (star) {
        event.preventDefault();
        const review = star.closest("[data-order-review]");
        if (!review) return;
        setInteractiveStars(review, Number(star.dataset.orderReviewStar || 0), "[data-order-review-star]");
        return;
      }

      const link = event.target.closest("[data-review-link]");
      if (!link || link.dataset.reviewMode !== "write") return;
      const review = link.closest("[data-order-review]");
      const productUrl = link.getAttribute("href") || review?.dataset.productUrl || "";
      const selectedRating = Number(review?.dataset.selectedRating || 0);
      const target = new URL(productUrl, window.location.origin);
      if (selectedRating > 0) target.searchParams.set("review_rating", String(selectedRating));
      event.preventDefault();
      navigate(target.toString());
    });
  }

  function bindOrderInvoice() {
    const button = $("[data-print-invoice]");
    if (!button || button.dataset.bound === "true") return;
    button.dataset.bound = "true";
    button.addEventListener("click", () => window.print());
  }

  function bindReviewRatingPicker() {
    const form = $("[data-review-form]");
    if (!form) return;
    const picker = $("[data-review-rating-picker]", form);
    const select = $(".review-rating-select", form);
    if (!picker || !select) return;

    const apply = (value) => {
      const rating = Number(value) || 0;
      select.value = rating ? String(rating) : "";
      setInteractiveStars(picker, rating, "[data-review-rating]");
    };

    if (picker.dataset.bound !== "true") {
      picker.dataset.bound = "true";
      picker.addEventListener("click", (event) => {
        const star = event.target.closest("[data-review-rating]");
        if (!star) return;
        event.preventDefault();
        apply(star.dataset.reviewRating);
      });
    }

    const preset = new URLSearchParams(window.location.search).get("review_rating") || select.value;
    apply(preset);
  }

  function bindReviewImagePreview() {
    const form = $("[data-review-form]");
    if (!form) return;
    const input = $("[data-review-image-input]", form);
    const preview = $("[data-review-image-preview]", form);
    if (!input || !preview || input.dataset.bound === "true") return;
    input.dataset.bound = "true";
    let selectedFiles = [];

    const renderPreview = () => {
      (preview._objectUrls || []).forEach((url) => URL.revokeObjectURL(url));
      const files = selectedFiles.filter((file) => file.type.startsWith("image/"));
      if (!files.length) {
        preview._objectUrls = [];
        preview.innerHTML = "";
        preview.hidden = true;
        return;
      }
      const urls = files.map((file) => URL.createObjectURL(file));
      preview._objectUrls = urls;
      preview.hidden = false;
      preview.innerHTML = files.map((file, index) => `
        <div class="review-image-preview-card">
          <img src="${urls[index]}" alt="Selected review image ${index + 1}">
          <button class="review-image-preview-remove" type="button" data-review-remove-image="${index}" aria-label="Remove selected image">
            <i class="fa-solid fa-xmark"></i>
          </button>
          <span class="review-image-preview-badge">New</span>
        </div>
      `).join("");
    };

    const syncInputFiles = () => {
      const transfer = new DataTransfer();
      selectedFiles.forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
    };

    input.addEventListener("change", () => {
      selectedFiles = [...(input.files || [])].filter((file) => file.type.startsWith("image/"));
      syncInputFiles();
      renderPreview();
    });

    preview.addEventListener("click", (event) => {
      const remove = event.target.closest("[data-review-remove-image]");
      if (!remove) return;
      event.preventDefault();
      const index = Number(remove.dataset.reviewRemoveImage);
      if (Number.isNaN(index)) return;
      selectedFiles.splice(index, 1);
      syncInputFiles();
      renderPreview();
    });
  }

  function bindOrderReviewPage() {
    const page = $("[data-order-review-page]");
    const form = $("[data-order-review-form]", page || document);
    if (!page || !form || form.dataset.bound === "true") return;
    form.dataset.bound = "true";

    const ratingInput = $("[data-order-review-rating-input]", form);
    const ratingLabel = $("[data-order-review-rating-label]", form);
    const textInput = $("[data-order-review-text]", form);
    const submit = $("[data-order-review-submit]", form);
    const photoInput = $("[data-order-review-photos]", form);
    const videoInput = $("[data-order-review-video]", form);
    const preview = $("[data-order-review-media-preview]", form);
    const ratingLabels = {
      1: "Poor",
      2: "Okay",
      3: "Good",
      4: "Liked It!",
      5: "Loved It!",
    };
    let photoFiles = [...(photoInput?.files || [])];
    let videoFile = videoInput?.files?.[0] || null;

    const syncFiles = () => {
      if (photoInput) {
        const photoTransfer = new DataTransfer();
        photoFiles.forEach((file) => photoTransfer.items.add(file));
        photoInput.files = photoTransfer.files;
      }
      if (videoInput) {
        const videoTransfer = new DataTransfer();
        if (videoFile) videoTransfer.items.add(videoFile);
        videoInput.files = videoTransfer.files;
      }
    };

    const validateSubmit = () => {
      const enabled = Number(ratingInput?.value || 0) > 0 && Boolean(textInput?.value.trim());
      if (submit) submit.disabled = !enabled;
    };

    const renderMediaPreview = () => {
      if (!preview) return;
      (preview._objectUrls || []).forEach((url) => URL.revokeObjectURL(url));
      const urls = [];
      const cards = [];
      photoFiles.slice(0, 4).forEach((file, index) => {
        const url = URL.createObjectURL(file);
        urls.push(url);
        cards.push(`
          <div class="order-review-media-tile">
            <img src="${url}" alt="Selected photo ${index + 1}">
            <button class="review-image-preview-remove" type="button" data-order-review-remove-photo="${index}" aria-label="Remove selected photo">
              <i class="fa-solid fa-xmark"></i>
            </button>
            <span class="order-review-media-badge">Photo</span>
          </div>
        `);
      });
      if (videoFile) {
        const url = URL.createObjectURL(videoFile);
        urls.push(url);
        cards.push(`
          <div class="order-review-media-tile">
            <video src="${url}" muted playsinline></video>
            <button class="review-image-preview-remove" type="button" data-order-review-remove-video aria-label="Remove selected video">
              <i class="fa-solid fa-xmark"></i>
            </button>
            <span class="order-review-media-badge">Video</span>
          </div>
        `);
      }
      preview._objectUrls = urls;
      preview.hidden = cards.length === 0;
      preview.innerHTML = cards.join("");
    };

    const setRating = (value) => {
      const rating = Number(value) || 0;
      if (ratingInput) ratingInput.value = rating ? String(rating) : "";
      if (ratingLabel) ratingLabel.textContent = ratingLabels[rating] || "";
      $$("[data-review-rating-choice]", form).forEach((button) => {
        const current = Number(button.dataset.reviewRatingChoice || 0);
        const active = current <= rating;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
        const icon = $("i", button);
        if (icon) icon.className = `${active ? "fa-solid" : "fa-regular"} fa-star`;
      });
      validateSubmit();
    };

    $$("[data-review-rating-choice]", form).forEach((button) => {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        setRating(button.dataset.reviewRatingChoice);
      });
    });

    textInput?.addEventListener("input", validateSubmit);

    photoInput?.addEventListener("change", () => {
      photoFiles = [...(photoInput.files || [])].filter((file) => file.type.startsWith("image/")).slice(0, 4);
      syncFiles();
      renderMediaPreview();
    });

    videoInput?.addEventListener("change", () => {
      const candidate = videoInput.files?.[0] || null;
      if (candidate && candidate.size > 200 * 1024 * 1024) {
        toast("Video size must be 200 MB or less");
        videoFile = null;
      } else {
        videoFile = candidate;
      }
      syncFiles();
      renderMediaPreview();
    });

    preview?.addEventListener("click", (event) => {
      const removePhoto = event.target.closest("[data-order-review-remove-photo]");
      if (removePhoto) {
        event.preventDefault();
        const index = Number(removePhoto.dataset.orderReviewRemovePhoto);
        if (!Number.isNaN(index)) {
          photoFiles.splice(index, 1);
          syncFiles();
          renderMediaPreview();
        }
        return;
      }
      const removeVideo = event.target.closest("[data-order-review-remove-video]");
      if (removeVideo) {
        event.preventDefault();
        videoFile = null;
        syncFiles();
        renderMediaPreview();
      }
    });

    setRating(ratingInput?.value || 0);
    validateSubmit();
    renderMediaPreview();
  }

  function bindReviews() {
    const form = $("[data-review-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      const user = await ensureUserProfile();
      if (!user) {
        openAuthModal(submitter, { returnUrl: currentUrl() });
        toast("Login as a customer to review this product");
        return;
      }
      const payload = new FormData(form);
      payload.set("product", form.dataset.productId);
      const reviewId = form.dataset.reviewId;
      await withLockedButton(submitter, async () => {
        try {
          const review = await api(reviewId ? `/api/reviews/${reviewId}/` : "/api/reviews/", {
            method: reviewId ? "PATCH" : "POST",
            body: payload,
          });
          form.dataset.reviewId = String(review.id);
          const message = $("[data-review-message]");
          if (message) message.textContent = reviewId ? "Review updated." : "Review submitted.";
          const submitButton = form.querySelector('[type="submit"]');
          if (submitButton) submitButton.textContent = "Update Review";
          toast(reviewId ? "Review updated" : "Review submitted");
        } catch (error) {
          $("[data-review-message]").textContent = flattenError(error);
        }
      });
    });
  }

  function bindGallery() {
    $$("[data-thumb]").forEach((btn) => btn.addEventListener("click", () => {
      const viewer = $("[data-tilt-viewer]");
      if (!viewer) return;
      const badge = viewer.querySelector(".viewer-badge");
      const mediaType = btn.dataset.mediaType;
      const media = mediaType === "video"
        ? `<video src="${btn.dataset.thumb}" poster="${btn.dataset.poster || ""}" controls autoplay muted playsinline data-main-video></video>`
        : `<img src="${btn.dataset.thumb}" alt="Product media" data-main-image>`;
      viewer.innerHTML = media;
      if (badge) viewer.appendChild(badge);
      bindGalleryTilt();
    }));
    bindGalleryTilt();
    $("[data-qty-minus]")?.addEventListener("click", () => {
      const input = $("[data-quantity]");
      input.value = Math.max(1, Number(input.value) - 1);
    });
    $("[data-qty-plus]")?.addEventListener("click", () => {
      const input = $("[data-quantity]");
      input.value = Number(input.value) + 1;
    });
  }

  function bindGalleryTilt() {
    const viewer = $("[data-tilt-viewer]");
    const image = $("[data-main-image]");
    if (viewer && image) {
      viewer.addEventListener("mousemove", (event) => {
        const rect = viewer.getBoundingClientRect();
        const x = ((event.clientX - rect.left) / rect.width - 0.5) * 18;
        const y = ((event.clientY - rect.top) / rect.height - 0.5) * -18;
        image.style.transform = `scale(1.08) rotateY(${x}deg) rotateX(${y}deg)`;
      });
      viewer.addEventListener("mouseleave", () => {
        image.style.transform = "";
      });
    }
  }

  async function bindDashboard() {
    const root = $("[data-dashboard-root]");
    if (!root || window.location.pathname !== "/dashboard/") return;
    const user = await ensureUserProfile();
    if (!user) return;
    try {
      const addresses = await api("/api/auth/addresses/", { silent: true });
      state.addresses = normalizeAddressList(addresses);
      state.selectedAddressId = (state.addresses.find((item) => item.is_default) || state.addresses[0] || {}).id || null;
      const list = $("[data-profile-address-list]");
      if (list) list.innerHTML = profileAddressCards(state.addresses);
    } catch {
      state.addresses = [];
      state.selectedAddressId = null;
      const list = $("[data-profile-address-list]");
      if (list) list.innerHTML = `<p class="profile-card-note">No saved addresses yet.</p>`;
    }
    bindDashboardAddressManager();
    bindDashboardAddressModal();
  }

  function bindDashboardAddressManager() {
    if (document.body.dataset.dashboardAddressManagerBound === "true") return;
    document.body.dataset.dashboardAddressManagerBound = "true";
    document.addEventListener("click", (event) => {
      const toggle = event.target.closest("[data-address-manager-toggle], [data-section-toggle]");
      if (!toggle) return;
      event.preventDefault();
      const target = $(`#${toggle.getAttribute("aria-controls")}`);
      if (!target) return;
      const shouldShow = target.hidden;
      target.hidden = !shouldShow;
      $$(`[aria-controls="${toggle.getAttribute("aria-controls")}"]`).forEach((item) => {
        item.setAttribute("aria-expanded", String(shouldShow));
      });
      if (shouldShow) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    $$("[data-section-toggle], [data-address-manager-toggle]").forEach((item) => {
      const target = $(`#${item.getAttribute("aria-controls")}`);
      if (!target) return;
      item.setAttribute("aria-expanded", String(!target.hidden));
    });
  }

  function bindDashboardAddressModal() {
    const modal = $("[data-address-modal]");
    const form = $("[data-address-form]");
    if (!modal || !form) return;

    const message = $("[data-address-message]", modal);
    const title = $("[data-address-modal-title]", modal);
    const submitButton = $("[data-address-submit]", modal);
    const closeAddressModal = () => {
      if (message) message.textContent = "";
      form.reset();
      form.dataset.addressId = "";
      form.dataset.addressMode = "create";
      if (title) title.textContent = "Add address";
      if (submitButton) submitButton.textContent = "Save address";
      const country = form.elements.namedItem("country");
      if (country && !country.value) country.value = "India";
      closeModal(modal);
    };

    if (!state.handlersBound.dashboardAddress) {
      state.handlersBound.dashboardAddress = true;
      document.addEventListener("click", (event) => {
        const openBtn = event.target.closest("[data-address-open]");
        if (openBtn) {
          event.preventDefault();
          const currentModal = $("[data-address-modal]");
          const currentForm = $("[data-address-form]");
          const currentMessage = currentModal ? $("[data-address-message]", currentModal) : null;
          const currentTitle = currentModal ? $("[data-address-modal-title]", currentModal) : null;
          const currentSubmit = currentModal ? $("[data-address-submit]", currentModal) : null;
          if (currentMessage) currentMessage.textContent = "";
          if (currentForm) {
            currentForm.dataset.addressId = "";
            currentForm.dataset.addressMode = "create";
            fillAddressForm(currentForm);
          }
          if (currentTitle) currentTitle.textContent = "Add address";
          if (currentSubmit) currentSubmit.textContent = "Save address";
          openModal(currentModal, openBtn);
        }
        const editBtn = event.target.closest("[data-address-edit]");
        if (editBtn) {
          event.preventDefault();
          const address = state.addresses.find((item) => String(item.id) === String(editBtn.dataset.addressEdit));
          const currentModal = $("[data-address-modal]");
          const currentForm = $("[data-address-form]");
          const currentMessage = currentModal ? $("[data-address-message]", currentModal) : null;
          const currentTitle = currentModal ? $("[data-address-modal-title]", currentModal) : null;
          const currentSubmit = currentModal ? $("[data-address-submit]", currentModal) : null;
          if (!address || !currentForm) return;
          if (currentMessage) currentMessage.textContent = "";
          currentForm.dataset.addressId = String(address.id);
          currentForm.dataset.addressMode = "edit";
          fillAddressForm(currentForm, address);
          if (currentTitle) currentTitle.textContent = "Edit address";
          if (currentSubmit) currentSubmit.textContent = "Update address";
          openModal(currentModal, editBtn);
        }
        const primaryBtn = event.target.closest("[data-address-primary]");
        if (primaryBtn) {
          event.preventDefault();
          withLockedButton(primaryBtn, async () => {
            const address = state.addresses.find((item) => String(item.id) === String(primaryBtn.dataset.addressPrimary));
            if (!address) return;
            const payload = {
              label: address.label,
              full_name: address.full_name,
              phone: address.phone,
              line1: address.line1,
              line2: address.line2,
              city: address.city,
              state: address.state,
              postal_code: address.postal_code,
              country: address.country,
              is_default: true,
            };
            await api(`/api/auth/addresses/${address.id}/`, {
              method: "PATCH",
              body: JSON.stringify(payload),
            });
            await refreshAddresses({ silent: true });
            const list = $("[data-profile-address-list]");
            if (list) list.innerHTML = profileAddressCards(state.addresses);
            await updateDeliveryStrip({ silent: true });
            toast("Primary address updated");
          });
        }
        const deleteBtn = event.target.closest("[data-address-delete]");
        if (deleteBtn) {
          event.preventDefault();
          withLockedButton(deleteBtn, async () => {
            await api(`/api/auth/addresses/${deleteBtn.dataset.addressDelete}/`, { method: "DELETE" });
            await refreshAddresses({ silent: true });
            const list = $("[data-profile-address-list]");
            if (list) list.innerHTML = profileAddressCards(state.addresses);
            await updateDeliveryStrip({ silent: true });
            toast("Address deleted");
          });
        }
        const closeBtn = event.target.closest("[data-address-close]");
        if (closeBtn) {
          event.preventDefault();
          const currentModal = $("[data-address-modal]");
          const currentForm = $("[data-address-form]");
          const currentMessage = currentModal ? $("[data-address-message]", currentModal) : null;
          if (currentMessage) currentMessage.textContent = "";
          currentForm?.reset();
          const country = currentForm?.elements?.namedItem?.("country");
          if (country && !country.value) country.value = "India";
          closeModal(currentModal);
        }
      });
    }

    modal.addEventListener("click", (event) => {
      if (event.target === modal) closeAddressModal();
    });

    if (form.dataset.bound === "true") return;
    form.dataset.bound = "true";
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const submitter = event.submitter || form.querySelector('[type="submit"]');
      await withLockedButton(submitter, async () => {
        try {
          const payload = Object.fromEntries(new FormData(form).entries());
          delete payload.csrfmiddlewaretoken;
          payload.is_default = form.elements.namedItem("is_default")?.checked || false;
          const addressId = form.dataset.addressId;
          const method = form.dataset.addressMode === "edit" && addressId ? "PATCH" : "POST";
          const endpoint = method === "PATCH" ? `/api/auth/addresses/${addressId}/` : "/api/auth/addresses/";
          await api(endpoint, {
            method,
            body: JSON.stringify(payload),
          });
          await refreshAddresses({ silent: true });
          const list = $("[data-profile-address-list]");
          if (list) list.innerHTML = profileAddressCards(state.addresses);
          await updateDeliveryStrip({ silent: true });
          closeAddressModal();
          toast("Address saved");
        } catch (error) {
          if (message) message.textContent = flattenError(error);
        }
      });
    });
  }

  function bindHomeHero() {
    window.clearInterval(state.heroTimer);
    state.heroTimer = null;
    const root = $("[data-home-carousel]");
    if (!root) return;
    const slides = $$("[data-home-slide]", root);
    const dots = $$("[data-home-dot]", root);
    const prev = $("[data-home-prev]", root);
    const next = $("[data-home-next]", root);
    if (!slides.length) return;
    let index = Math.max(slides.findIndex((slide) => slide.classList.contains("is-active")), 0);

    const activate = (nextIndex) => {
      index = (nextIndex + slides.length) % slides.length;
      slides.forEach((slide, slideIndex) => {
        slide.classList.toggle("is-active", slideIndex === index);
      });
      dots.forEach((dot, dotIndex) => dot.classList.toggle("is-active", dotIndex === index));
    };

    dots.forEach((dot, dotIndex) => {
      dot.addEventListener("click", () => activate(dotIndex));
    });
    prev?.addEventListener("click", () => activate(index - 1));
    next?.addEventListener("click", () => activate(index + 1));

    activate(index);
    if (slides.length > 1) {
      state.heroTimer = window.setInterval(() => activate(index + 1), 4500);
    }
    root.addEventListener("mouseenter", () => {
      window.clearInterval(state.heroTimer);
      state.heroTimer = null;
    });
    root.addEventListener("mouseleave", () => {
      if (slides.length > 1 && !state.heroTimer) {
        state.heroTimer = window.setInterval(() => activate(index + 1), 4500);
      }
    });
  }

  function bindCategoryMarquee() {
    if (state.categoryMarqueeRaf) {
      window.cancelAnimationFrame(state.categoryMarqueeRaf);
      state.categoryMarqueeRaf = null;
    }
    const shell = $("[data-home-carousel]") ? $(".home-category-marquee-shell") : null;
    const track = shell ? $(".home-category-marquee-track", shell) : null;
    if (!shell || !track) return;
    const items = $$(".home-category-item", track);
    if (items.length < 2) return;
    const loopWidth = track.scrollWidth / 2;
    let paused = false;
    let lastTick = 0;
    const speed = window.innerWidth <= 760 ? 0.45 : 0.6;

    const setPaused = (value) => {
      paused = value;
      shell.classList.toggle("is-paused", value);
    };

    if (shell.scrollLeft >= loopWidth || shell.scrollLeft === 0) {
      shell.scrollLeft = 0;
    }

    const step = (time) => {
      if (!lastTick) lastTick = time;
      const delta = time - lastTick;
      lastTick = time;
      if (!paused) {
        shell.scrollLeft += (delta * speed) / 16;
        if (shell.scrollLeft >= loopWidth) {
          shell.scrollLeft -= loopWidth;
        }
      }
      state.categoryMarqueeRaf = window.requestAnimationFrame(step);
    };

    if (!shell.dataset.marqueeBound) {
      shell.dataset.marqueeBound = "true";
      shell.addEventListener("mouseenter", () => setPaused(true));
      shell.addEventListener("mouseleave", () => setPaused(false));
      shell.addEventListener("touchstart", () => setPaused(true), { passive: true });
      shell.addEventListener("touchend", () => setPaused(false), { passive: true });
      shell.addEventListener("touchcancel", () => setPaused(false), { passive: true });
      shell.addEventListener("pointerdown", () => setPaused(true));
      shell.addEventListener("pointerup", () => setPaused(false));
    }

    state.categoryMarqueeRaf = window.requestAnimationFrame(step);
  }

  function reveal() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) entry.target.classList.add("visible");
      });
    }, { threshold: 0.12 });
    $$(".reveal").forEach((el) => observer.observe(el));
  }

  function bindPage() {
    bindFilters();
    bindCart();
    bindCheckoutAddressPage();
    bindCheckout();
    bindPaymentPage();
    bindNewsletter();
    bindReviews();
    bindReviewRatingPicker();
    bindReviewImagePreview();
    bindOrderReviewPage();
    bindOrderReviewActions();
    bindOrderInvoice();
    bindGallery();
    bindLocationModal();
    bindShareModal();
    bindHomeFeed();
    bindAddressPage();
    bindHomeHero();
    bindCategoryMarquee();
    bindDashboard();
    syncPageChrome();
    updateMobileNavState();
    reveal();
  }

  function init() {
    document.documentElement.classList.add("reveal-ready");
    toggleGlobalLoader(false);
    bindNavigation();
    bindAuth();
    bindAccountTrigger();
    bindProducts();
    bindSearch();
    bootstrapSession().then(() => {
      updateDeliveryStrip({ silent: true });
      updateWishlistBadge({ silent: true });
      updateCartBadge({ silent: true });
    });
    bindPage();
    state.bootstrapped = true;
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", Storefront.init);

