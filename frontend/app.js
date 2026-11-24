(() => {
  const API_BASE = String(window.THINDI_API_BASE || "").replace(/\/+$/, "");

  const form = document.getElementById("prefs-form");
  const locationSelect = document.getElementById("location");
  const cuisineSelect = document.getElementById("cuisine");
  const submitBtn = document.getElementById("submit-btn");
  const formStatus = document.getElementById("form-status");
  const results = document.getElementById("results");
  const resultsBanner = document.getElementById("results-banner");
  const summaryEl = document.getElementById("summary");
  const cardsEl = document.getElementById("cards");
  const budgetLowLabel = document.getElementById("budget-low-label");
  const budgetMediumLabel = document.getElementById("budget-medium-label");
  const budgetHighLabel = document.getElementById("budget-high-label");

  let requestSeq = 0;

  function apiUrl(path) {
    return `${API_BASE}${path}`;
  }

  function setStatus(message, isError = false) {
    formStatus.textContent = message || "";
    formStatus.classList.toggle("is-error", Boolean(isError && message));
  }

  function fillSelect(select, values, placeholder) {
    select.innerHTML = "";
    const first = document.createElement("option");
    first.value = "";
    first.textContent = placeholder;
    select.appendChild(first);
    for (const value of values) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      select.appendChild(option);
    }
    select.disabled = false;
  }

  function applyBudgetLabels(lowMax, mediumMax) {
    const low = Number(lowMax);
    const medium = Number(mediumMax);
    if (!Number.isFinite(low) || !Number.isFinite(medium)) {
      return;
    }
    if (budgetLowLabel) {
      budgetLowLabel.textContent = `Low (≤ ₹${low})`;
    }
    if (budgetMediumLabel) {
      budgetMediumLabel.textContent = `Medium (₹${low + 1}–₹${medium})`;
    }
    if (budgetHighLabel) {
      budgetHighLabel.textContent = `High (> ₹${medium})`;
    }
  }

  function showBanner(message, kind) {
    if (!message) {
      resultsBanner.hidden = true;
      resultsBanner.textContent = "";
      resultsBanner.className = "results-banner";
      return;
    }
    resultsBanner.hidden = false;
    resultsBanner.textContent = message;
    resultsBanner.className = `results-banner${kind ? ` is-${kind}` : ""}`;
  }

  function formatCost(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    return `₹${Number(value).toLocaleString("en-IN")} for two`;
  }

  function formatRating(value) {
    if (value === null || value === undefined || value === "") {
      return "—";
    }
    return String(value);
  }

  function formatBudgetBand(value) {
    if (!value) {
      return "";
    }
    const label = String(value).charAt(0).toUpperCase() + String(value).slice(1);
    return `(${label})`;
  }

  function formatVegBadge(value) {
    if (value === "pure_veg") {
      return "Pure Veg";
    }
    if (value === "veg_and_non_veg") {
      return "Veg & Non-veg";
    }
    return "";
  }

  function padIndex(index) {
    return String(index).padStart(2, "0");
  }

  function renderCards(items) {
    cardsEl.innerHTML = "";
    const limited = (items || []).slice(0, 5);
    limited.forEach((item, index) => {
      const card = document.createElement("article");
      card.className = "card";

      const vegBadge = formatVegBadge(item.veg_type);
      const budgetBand = formatBudgetBand(item.budget_band);
      const cuisine = item.cuisines || "—";
      const location = item.location || "—";

      card.innerHTML = `
        <div class="card-top">
          <div class="card-title-wrap">
            <span class="card-index"></span>
            <h2 class="card-title"></h2>
          </div>
          <div class="card-aside">
            <span class="card-rating">
              <span class="material-symbols-outlined filled">star</span>
              <span class="card-rating-value"></span>
            </span>
            ${vegBadge ? '<span class="card-badge"></span>' : ""}
          </div>
        </div>
        <div class="card-meta">
          <span class="card-location"></span>
          <span class="dot">•</span>
          <span class="card-cuisine"></span>
          <span class="dot">•</span>
          <span class="cost"></span>
          ${budgetBand ? '<span class="band"></span>' : ""}
        </div>
        <p class="card-copy"></p>
      `;

      card.querySelector(".card-index").textContent = padIndex(index + 1);
      card.querySelector(".card-title").textContent = item.name || "Restaurant";
      card.querySelector(".card-rating-value").textContent = formatRating(item.rating);
      if (vegBadge) {
        card.querySelector(".card-badge").textContent = vegBadge;
      }
      card.querySelector(".card-location").textContent = location;
      card.querySelector(".card-cuisine").textContent = cuisine;
      card.querySelector(".cost").textContent = formatCost(item.cost_for_two);
      if (budgetBand) {
        card.querySelector(".band").textContent = budgetBand;
      }
      card.querySelector(".card-copy").textContent = item.explanation || "";
      cardsEl.appendChild(card);
    });
  }

  async function loadMeta() {
    setStatus("Loading catalog options…");
    submitBtn.disabled = true;
    try {
      const response = await fetch(apiUrl("/api/meta"));
      if (response.status === 503) {
        setStatus("Catalog is unavailable right now. Try again later.", true);
        showResultsError("Catalog is unavailable (503).");
        return;
      }
      if (!response.ok) {
        setStatus("Could not load form options.", true);
        return;
      }
      const meta = await response.json();
      applyBudgetLabels(meta.budget_low_max, meta.budget_medium_max);
      fillSelect(locationSelect, meta.locations || [], "Choose a location");
      fillSelect(cuisineSelect, meta.cuisines || [], "Choose a cuisine");
      submitBtn.disabled = false;
      setStatus("");
    } catch (_error) {
      setStatus("Could not load form options.", true);
    }
  }

  function showResultsError(message) {
    results.hidden = false;
    summaryEl.textContent = "";
    cardsEl.innerHTML = "";
    showBanner(message, "error");
  }

  function renderResponse(data) {
    results.hidden = false;
    summaryEl.textContent = data.summary || "";
    const meta = data.meta || {};
    if ((data.recommendations || []).length === 0) {
      showBanner(meta.empty_reason || "No restaurants matched these filters.", "empty");
      cardsEl.innerHTML = "";
      return;
    }
    if (meta.used_fallback) {
      showBanner("List ordered by rating and votes because a written recommendation was unavailable.");
    } else {
      showBanner("");
    }
    renderCards(data.recommendations);
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (submitBtn.disabled) {
      return;
    }

    const minRating = Number(form.min_rating.value);
    if (Number.isNaN(minRating) || minRating < 0 || minRating > 5) {
      setStatus("Minimum rating must be between 0 and 5.", true);
      return;
    }

    const payload = {
      location: form.location.value,
      cuisine: form.cuisine.value,
      budget: form.budget.value,
      min_rating: minRating,
      veg_type: form.veg_type.value || "any",
    };
    const prefs = form.additional_preferences.value.trim();
    if (prefs) {
      payload.additional_preferences = prefs;
    }

    const seq = ++requestSeq;
    submitBtn.disabled = true;
    setStatus("Finding restaurants…");

    try {
      const response = await fetch(apiUrl("/api/recommendations"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (seq !== requestSeq) {
        return;
      }

      if (response.status === 400 || response.status === 503) {
        let detail = response.status === 503
          ? "Catalog is unavailable right now."
          : "Please check the form values and try again.";
        try {
          const errorBody = await response.json();
          if (errorBody && errorBody.detail) {
            detail = typeof errorBody.detail === "string"
              ? errorBody.detail
              : detail;
          }
        } catch (_ignore) {
          // keep default detail
        }
        setStatus(detail, true);
        showResultsError(detail);
        return;
      }

      if (!response.ok) {
        setStatus("Something went wrong while fetching recommendations.", true);
        showResultsError("Something went wrong while fetching recommendations.");
        return;
      }

      const data = await response.json();
      if (seq !== requestSeq) {
        return;
      }
      setStatus("");
      renderResponse(data);
    } catch (_error) {
      if (seq !== requestSeq) {
        return;
      }
      setStatus("Network error while fetching recommendations.", true);
      showResultsError("Network error while fetching recommendations.");
    } finally {
      if (seq === requestSeq) {
        submitBtn.disabled = false;
      }
    }
  });

  loadMeta();
})();
