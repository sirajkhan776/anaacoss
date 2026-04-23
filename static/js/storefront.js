const Storefront = (() => {
  const state = {
    access: localStorage.getItem("anaacoss_access"),
    refresh: localStorage.getItem("anaacoss_refresh"),
    isAuthenticated: Boolean(localStorage.getItem("anaacoss_access")) || document.body?.dataset.userAuthenticated === "true",
    sessionPromise: null,
    user: null,
    addresses: [],
    selectedAddressId: null,
    handlersBound: {
      navigation: false,
      products: false,
      cart: false,
      location: false,
      accountTrigger: false,
      accountPanel: false,
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

  function csrf() {
    const token = document.cookie.split("; ").find((row) => row.startsWith("csrftoken="));
    return token ? decodeURIComponent(token.split("=")[1]) : "";
  }

  async function api(url, options = {}) {
    const isFormData = options.body instanceof FormData;
    const headers = {
      "X-CSRFToken": csrf(),
      "X-Requested-With": "XMLHttpRequest",
      ...(options.headers || {}),
    };
    if (!isFormData) headers["Content-Type"] = "application/json";
    if (state.access) headers.Authorization = `Bearer ${state.access}`;
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401 && state.refresh) {
      const refreshed = await fetch("/api/auth/token/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
        body: JSON.stringify({ refresh: state.refresh }),
      });
      if (refreshed.ok) {
        const data = await refreshed.json();
        setTokens(data.access, data.refresh || state.refresh);
        return api(url, options);
      } else {
        clearTokens();
      }
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw data;
    return data;
  }

  function setTokens(access, refresh) {
    state.access = access;
    state.refresh = refresh;
    state.isAuthenticated = true;
    document.body?.setAttribute("data-user-authenticated", "true");
    localStorage.setItem("anaacoss_access", access);
    localStorage.setItem("anaacoss_refresh", refresh);
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

  function toast(message) {
    const el = $("[data-toast]");
    if (!el) return;
    el.textContent = message;
    el.classList.add("show");
    setTimeout(() => el.classList.remove("show"), 2600);
  }

  function addressLocationText(address) {
    if (!address) return "Add your delivery address";
    return [address.label, address.city, address.postal_code].filter(Boolean).join(", ");
  }

  function addressFullText(address) {
    return [address.line1, address.line2, address.city, address.state, address.postal_code].filter(Boolean).join(", ");
  }

  function renderSavedAddresses() {
    const root = $("[data-saved-addresses]");
    if (!root) return;
    if (!state.addresses.length) {
      root.innerHTML = `<p class="location-empty">No saved addresses yet.</p>`;
      return;
    }
    root.innerHTML = state.addresses.map((address) => `
      <label class="saved-address-option">
        <input type="radio" name="saved_address" value="${address.id}" ${String(state.selectedAddressId) === String(address.id) ? "checked" : ""}>
        <span class="saved-address-copy">
          <strong>${address.full_name}</strong>
          <span class="saved-address-meta">${address.label}${address.is_default ? " • Default" : ""}</span>
          <p>${addressFullText(address)}</p>
        </span>
      </label>
    `).join("");
  }

  async function navigate(url, push = true) {
    const response = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
    const html = await response.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const nextRoot = doc.querySelector("#page-root");
    if (!nextRoot) {
      window.location.href = url;
      return;
    }
    $("#page-root").innerHTML = nextRoot.innerHTML;
    document.title = doc.title;
    if (push) history.pushState({}, "", url);
    window.scrollTo({ top: 0, behavior: "smooth" });
    bindPage();
  }

  function bindNavigation() {
    if (state.handlersBound.navigation) return;
    state.handlersBound.navigation = true;
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[data-spa]");
      if (!link || link.origin !== location.origin) return;
      event.preventDefault();
      navigate(link.href);
    });
    window.addEventListener("popstate", () => navigate(location.href, false));
  }

  function openModal(modal, trigger) {
    if (!modal) return;
    modal.dataset.returnFocus = trigger ? "true" : "";
    if (trigger?.id) modal.dataset.returnFocusId = trigger.id;
    else delete modal.dataset.returnFocusId;
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
    if (modal.contains(document.activeElement)) {
      document.activeElement.blur?.();
    }
    modal.classList.remove("open");
    modal.setAttribute("aria-hidden", "true");
    if (!$$(".modal-shell.open").length) {
      document.body.classList.remove("modal-open");
    }
    if (returnFocusEl && document.contains(returnFocusEl)) {
      returnFocusEl.focus?.();
    }
  }

  function bindAuth() {
    const modal = $("[data-auth-modal]");
    $$("[data-auth-close]").forEach((btn) => btn.addEventListener("click", () => closeModal(modal)));
    modal?.addEventListener("click", (event) => {
      if (event.target === modal) closeModal(modal);
    });
    $$("[data-auth-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        $$("[data-auth-tab]").forEach((tab) => tab.classList.toggle("active", tab === btn));
        $$("[data-auth-form]").forEach((form) => form.classList.toggle("active", form.dataset.authForm === btn.dataset.authTab));
      });
    });
    $$("[data-auth-form]").forEach((form) => {
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const mode = form.dataset.authForm;
        const payload = Object.fromEntries(new FormData(form).entries());
        try {
          const data = await api(`/api/auth/${mode}/`, { method: "POST", body: JSON.stringify(payload) });
          setTokens(data.access, data.refresh);
          state.user = data.user;
          $("[data-auth-message]").textContent = `Signed in as ${data.user.first_name || data.user.username}`;
          closeModal(modal);
          toast("Account ready");
          updateCartBadge();
          updateWishlistBadge();
          updateDeliveryStrip();
        } catch (error) {
          $("[data-auth-message]").textContent = flattenError(error);
        }
      });
    });
  }

  async function bootstrapSession(force = false) {
    if (state.sessionPromise && !force) return state.sessionPromise;
    state.access = state.access || localStorage.getItem("anaacoss_access");
    state.refresh = state.refresh || localStorage.getItem("anaacoss_refresh");
    state.sessionPromise = (async () => {
      try {
        const user = await api("/api/auth/me/");
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
    try {
      return await bootstrapSession();
    } catch {
      return null;
    } 
  }

  function bindAccountTrigger() {
    if (state.handlersBound.accountTrigger) return;
    state.handlersBound.accountTrigger = true;
    $$("[data-account-open]").forEach((btn) => btn.addEventListener("click", async () => {
      const user = await bootstrapSession();
      if (user) {
        navigate("/dashboard/");
        return;
      }
      openModal($("[data-auth-modal]"), btn);
    }));
  }

  function flattenError(error) {
    if (typeof error === "string") return error;
    return Object.entries(error || {}).map(([key, value]) => {
      const text = Array.isArray(value) ? value.join(", ") : value;
      if (key === "non_field_errors" || key === "detail") return text;
      return `${key}: ${text}`;
    }).join(" ");
  }

  async function updateCartBadge() {
    try {
      const cart = await api("/api/cart/");
      $$("[data-cart-count], [data-cart-count-mobile]").forEach((count) => {
        count.textContent = cart.count || 0;
      });
      renderCart(cart);
    } catch {
      return null;
    }
  }

  async function updateWishlistBadge() {
    const counts = $$("[data-wishlist-count], [data-wishlist-count-mobile]");
    if (!counts.length) return null;
    if (!state.access) {
      counts.forEach((count) => { count.textContent = 0; });
      return 0;
    }
    try {
      const wishlist = await api("/api/wishlist/");
      counts.forEach((count) => { count.textContent = wishlist.length || 0; });
      return wishlist.length || 0;
    } catch {
      clearTokens();
      counts.forEach((count) => { count.textContent = 0; });
      return null;
    }
  }

  async function updateDeliveryStrip() {
    const strip = $("[data-delivery-strip]");
    const name = $("[data-delivery-name]");
    const location = $("[data-delivery-location]");
    if (!strip || !name || !location) return null;
    const user = await bootstrapSession();
    if (!user) {
      state.user = null;
      state.addresses = [];
      state.selectedAddressId = null;
      name.textContent = "User";
      location.textContent = "";
      location.hidden = true;
      strip.hidden = true;
      renderSavedAddresses();
      return null;
    }
    try {
      const [, addresses] = await Promise.all([
        Promise.resolve(user),
        api("/api/auth/addresses/"),
      ]);
      state.addresses = addresses;
      const preferredAddress = addresses.find((item) => item.is_default) || addresses[0];
      state.selectedAddressId = preferredAddress?.id || null;
      name.textContent = user.username || user.first_name || "User";
      const locationText = preferredAddress ? addressLocationText(preferredAddress) : "";
      location.textContent = locationText;
      location.hidden = !locationText;
      renderSavedAddresses();
      strip.hidden = false;
      return { user, addresses };
    } catch {
      clearTokens();
      state.addresses = [];
      state.selectedAddressId = null;
      location.textContent = "";
      location.hidden = true;
      strip.hidden = true;
      renderSavedAddresses();
      return null;
    }
  }

  function bindLocationModal() {
    if (state.handlersBound.location) return;
    state.handlersBound.location = true;
    const modal = $("[data-location-modal]");
    const pincodeInput = $("[data-location-pincode]");
    const openLocationModal = async (trigger) => {
      if (!state.access) {
        openModal($("[data-auth-modal]"), trigger);
        return;
      }
      await updateDeliveryStrip();
      openModal(modal, trigger);
    };
    const closeLocationModal = () => closeModal(modal);

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
      renderSavedAddresses();
      closeLocationModal();
      toast(`Delivery location set to ${address.label}`);
    });
  }

  function productCardHtml(product) {
    const image = product.primary_image || "";
    return `
      <article class="product-card" data-product-id="${product.id}">
        <a class="product-media" href="/product/${product.slug}/" data-spa>
          ${image ? `<img src="${image}" alt="${product.name}" loading="lazy">` : `<div class="image-fallback"><i class="fa-solid fa-spa"></i></div>`}
          ${product.badge ? `<span class="badge">${product.badge}</span>` : ""}
          <div class="quick-actions">
            <button type="button" data-add-cart="${product.id}"><i class="fa-solid fa-bag-shopping"></i></button>
            <button type="button" data-wishlist="${product.id}"><i class="fa-regular fa-heart"></i></button>
            <button type="button" data-quick-view="${product.slug}"><i class="fa-solid fa-eye"></i></button>
          </div>
        </a>
        <div class="product-info">
          <p class="product-brand">${product.brand?.name || ""}</p>
          <a href="/product/${product.slug}/" data-spa><h3>${product.name}</h3></a>
          <p>${product.short_description || ""}</p>
          <div class="rating"><i class="fa-solid fa-star"></i> ${product.rating} <span>(${product.review_count})</span></div>
          <div class="price-row"><strong>Rs. ${product.final_price}</strong>${product.discount_price ? `<del>Rs. ${product.price}</del>` : ""}</div>
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
        await api("/api/cart/add/", {
          method: "POST",
          body: JSON.stringify({ product_id: add.dataset.addCart, quantity, variant_id: variant }),
        });
        toast("Added to bag");
        updateCartBadge();
      }
      const wish = event.target.closest("[data-wishlist]");
      if (wish) {
        event.preventDefault();
        try {
          const data = await api("/api/wishlist/toggle/", { method: "POST", body: JSON.stringify({ product_id: wish.dataset.wishlist }) });
          $$("[data-wishlist-count], [data-wishlist-count-mobile]").forEach((count) => {
            count.textContent = data.count || 0;
          });
          toast(data.wishlisted ? "Saved to wishlist" : "Removed from wishlist");
        } catch {
          openModal($("[data-auth-modal]"), wish);
        }
      }
      const quick = event.target.closest("[data-quick-view]");
      if (quick) {
        event.preventDefault();
        navigate(`/product/${quick.dataset.quickView}/`);
      }
      const buy = event.target.closest("[data-buy-now]");
      if (buy) {
        event.preventDefault();
        await api("/api/cart/add/", { method: "POST", body: JSON.stringify({ product_id: buy.dataset.buyNow, quantity: 1 }) });
        navigate("/checkout/");
      }
    });
  }

  function bindFilters() {
    const form = $("[data-filter-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const params = new URLSearchParams(new FormData(form));
      for (const [key, value] of [...params.entries()]) if (!value) params.delete(key);
      const data = await api(`/api/products/?${params.toString()}`);
      const products = data.results || data;
      $("[data-product-grid]").innerHTML = products.map(productCardHtml).join("") || `<p>No products found.</p>`;
      $("[data-result-count]").textContent = `${products.length} products`;
    });
  }

  function renderCart(cart) {
    const itemsRoot = $("[data-cart-items]");
    const summary = $("[data-cart-summary]");
    if (itemsRoot) {
      itemsRoot.innerHTML = cart.items.length ? cart.items.map((item) => `
        <article class="cart-line">
          ${item.product.primary_image ? `<img src="${item.product.primary_image}" alt="${item.product.name}">` : `<div class="image-fallback"></div>`}
          <div><h3>${item.product.name}</h3><p>Rs. ${item.unit_price}</p><div class="cart-qty"><button data-cart-dec="${item.id}">-</button><span>${item.quantity}</span><button data-cart-inc="${item.id}">+</button></div></div>
          <div><strong>Rs. ${item.line_total}</strong><button class="icon-btn" data-cart-remove="${item.id}"><i class="fa-solid fa-trash"></i></button></div>
        </article>`).join("") : `<p class="empty-state">Your bag is waiting for a ritual.</p>`;
    }
    if (summary) {
      summary.innerHTML = `
        <div class="summary-row"><span>Subtotal</span><strong>Rs. ${cart.subtotal}</strong></div>
        <div class="summary-row"><span>Discount</span><strong>- Rs. ${cart.discount}</strong></div>
        <div class="summary-row"><span>Shipping</span><strong>Rs. ${cart.shipping}</strong></div>
        <div class="summary-row total"><span>Total</span><strong>Rs. ${cart.total}</strong></div>
        ${cart.coupon ? `<p class="coupon-highlight">${cart.coupon.code} applied</p>` : ""}`;
    }
  }

  function bindCart() {
    updateCartBadge();
    updateWishlistBadge();
    updateDeliveryStrip();
    if (state.handlersBound.cart) return;
    state.handlersBound.cart = true;
    document.addEventListener("click", async (event) => {
      const inc = event.target.closest("[data-cart-inc]");
      const dec = event.target.closest("[data-cart-dec]");
      const remove = event.target.closest("[data-cart-remove]");
      if (!inc && !dec && !remove) return;
      event.preventDefault();
      const cart = await api("/api/cart/");
      const id = (inc || dec || remove).dataset.cartInc || (inc || dec || remove).dataset.cartDec || (inc || dec || remove).dataset.cartRemove;
      if (remove) await api(`/api/cart/items/${id}/`, { method: "DELETE" });
      else {
        const item = cart.items.find((row) => String(row.id) === String(id));
        const quantity = Math.max(1, item.quantity + (inc ? 1 : -1));
        await api(`/api/cart/items/${id}/`, { method: "PATCH", body: JSON.stringify({ quantity }) });
      }
      updateCartBadge();
    });
    const coupon = $("[data-coupon-form]");
    if (coupon) {
      coupon.addEventListener("submit", async (event) => {
        event.preventDefault();
        try {
          const data = await api("/api/cart/coupon/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(coupon).entries())) });
          renderCart(data);
          toast("Coupon applied");
        } catch (error) {
          toast(flattenError(error));
        }
      });
    }
    $("[data-remove-coupon]")?.addEventListener("click", async () => {
      const data = await api("/api/cart/coupon/", { method: "DELETE" });
      renderCart(data);
      toast("Coupon removed");
    });
  }

  function bindCheckout() {
    const form = $("[data-checkout-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.access) {
        openModal($("[data-auth-modal]"), form.querySelector('[type="submit"]'));
        toast("Login to place your order");
        return;
      }
      try {
        const data = await api("/api/orders/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
        toast(`Order #${data.id} placed`);
        navigate("/dashboard/");
      } catch (error) {
        toast(flattenError(error));
      }
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
      const data = await api(`/api/products/suggestions/?q=${encodeURIComponent(query)}`);
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
    input?.addEventListener("input", () => {
      if (input.value.trim()) placeholder.classList.remove("visible", "exit");
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const query = input.value.trim();
        await runSearch(query);
      }, 220);
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const query = input.value.trim();
        if (!query) return;
        navigate(`/shop/?q=${encodeURIComponent(query)}`);
        root.classList.remove("open");
      }
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
      await api("/api/newsletter/", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(form).entries())) });
      form.reset();
      toast("Subscribed");
    });
  }

  function reviewHtml(review) {
    const stars = "★".repeat(review.rating) + "☆".repeat(5 - review.rating);
    const images = (review.images || []).map((image) => `<img src="${image.url}" alt="${image.alt_text || review.title}">`).join("");
    return `
      <article class="review-card">
        <div class="review-head"><strong>${review.user_name || "Customer"}</strong><span>${stars}</span></div>
        <h3>${review.title}</h3>
        <p>${review.body}</p>
        ${images ? `<div class="review-images">${images}</div>` : ""}
      </article>`;
  }

  function bindReviews() {
    const form = $("[data-review-form]");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!state.access) {
        openModal($("[data-auth-modal]"), form.querySelector('[type="submit"]'));
        toast("Login as a customer to review this product");
        return;
      }
      const payload = new FormData(form);
      payload.set("product", form.dataset.productId);
      try {
        const review = await api("/api/reviews/", { method: "POST", body: payload });
        const list = $("[data-review-list]");
        if (list) list.insertAdjacentHTML("afterbegin", reviewHtml(review));
        form.reset();
        $("[data-review-message]").textContent = "Review submitted.";
        toast("Review submitted");
      } catch (error) {
        $("[data-review-message]").textContent = flattenError(error);
      }
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
        const x = ((event.clientX - rect.left) / rect.width - .5) * 18;
        const y = ((event.clientY - rect.top) / rect.height - .5) * -18;
        image.style.transform = `scale(1.08) rotateY(${x}deg) rotateX(${y}deg)`;
      });
      viewer.addEventListener("mouseleave", () => { image.style.transform = ""; });
    }
  }

  function reveal() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => entry.isIntersecting && entry.target.classList.add("visible"));
    }, { threshold: .12 });
    $$(".reveal").forEach((el) => observer.observe(el));
  }

  function bindPage() {
    bindFilters();
    bindCart();
    bindCheckout();
    bindNewsletter();
    bindReviews();
    bindGallery();
    bindLocationModal();
    reveal();
  }

  function init() {
    document.documentElement.classList.add("reveal-ready");
    bindNavigation();
    bindAuth();
    bindAccountTrigger();
    bindProducts();
    bindSearch();
    bootstrapSession().then(() => {
      updateDeliveryStrip();
      updateWishlistBadge();
      updateCartBadge();
    });
    bindPage();
  }

  return { init };
})();

document.addEventListener("DOMContentLoaded", Storefront.init);
