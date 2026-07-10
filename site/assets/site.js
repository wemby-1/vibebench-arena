const toggle = document.querySelector(".nav-toggle");
const links = document.querySelector("#nav-links");

if (toggle && links) {
  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    links.dataset.open = String(!isOpen);
  });

  links.addEventListener("click", (event) => {
    if (event.target instanceof HTMLAnchorElement) {
      toggle.setAttribute("aria-expanded", "false");
      links.dataset.open = "false";
    }
  });
}

const filterForm = document.querySelector("[data-artifact-filters]");
const searchInput = document.querySelector("[data-filter-search]");
const categorySelect = document.querySelector("[data-filter-category]");
const availabilitySelect = document.querySelector("[data-filter-availability]");
const artifactCards = Array.from(document.querySelectorAll("[data-artifact-card]"));
const filterStatus = document.querySelector("#artifact-filter-status");
const emptyState = document.querySelector("[data-empty-state]");

const updateArtifactFilters = () => {
  const query = (searchInput?.value || "").trim().toLowerCase();
  const category = categorySelect?.value || "all";
  const availability = availabilitySelect?.value || "all";
  let visible = 0;

  artifactCards.forEach((card) => {
    const matchesQuery = !query || (card.dataset.search || "").includes(query);
    const matchesCategory = category === "all" || card.dataset.category === category;
    const matchesAvailability =
      availability === "all" || card.dataset.availability === availability;
    const show = matchesQuery && matchesCategory && matchesAvailability;
    card.hidden = !show;
    if (show) {
      visible += 1;
    }
  });

  if (filterStatus) {
    filterStatus.textContent = `Showing ${visible} of ${artifactCards.length} known reference artifacts.`;
  }
  if (emptyState) {
    emptyState.hidden = visible !== 0;
  }

  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (category !== "all") params.set("category", category);
  if (availability !== "all") params.set("availability", availability);
  const suffix = params.toString() ? `?${params.toString()}#artifacts` : "#artifacts";
  history.replaceState(null, "", suffix);
};

if (filterForm && searchInput && categorySelect && availabilitySelect) {
  const params = new URLSearchParams(window.location.search);
  if (params.has("q")) searchInput.value = params.get("q") || "";
  if (params.has("category")) categorySelect.value = params.get("category") || "all";
  if (params.has("availability")) {
    availabilitySelect.value = params.get("availability") || "all";
  }

  filterForm.addEventListener("input", updateArtifactFilters);
  filterForm.addEventListener("change", updateArtifactFilters);
  filterForm.addEventListener("reset", () => {
    window.setTimeout(updateArtifactFilters, 0);
  });
  updateArtifactFilters();
}

const copyFeedback = document.querySelector("[data-copy-feedback]");

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    const target = targetId ? document.getElementById(targetId) : null;
    const text = target?.textContent?.trim();
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      button.dataset.copied = "true";
      if (copyFeedback) {
        copyFeedback.textContent = "Command copied. The command remains visible and selectable.";
      }
      window.setTimeout(() => {
        button.textContent = "Copy command";
        button.dataset.copied = "false";
      }, 2200);
    } catch {
      if (copyFeedback) {
        copyFeedback.textContent = "Copy unavailable. Select the visible command text instead.";
      }
    }
  });
});
