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

const actionPresetData = document.querySelector("#action-preset-data");
const actionPreset = document.querySelector("[data-action-preset]");
const actionConfig = document.querySelector("[data-action-config]");
const actionMode = document.querySelector("[data-action-mode]");
const actionUpload = document.querySelector("[data-action-upload]");
const actionSnippet = document.querySelector("#action-workflow-snippet code");

const actionPresets = (() => {
  if (!actionPresetData?.textContent) return [];
  try {
    return JSON.parse(actionPresetData.textContent);
  } catch {
    return [];
  }
})();

const renderActionWorkflow = () => {
  if (!actionPreset || !actionConfig || !actionMode || !actionUpload || !actionSnippet) {
    return;
  }
  const presetName = actionPreset.value || "minimal";
  const preset = actionPresets.find((item) => item.name === presetName);
  const defaultMode = preset?.required_mode || "adoption";
  const configPath = actionConfig.value.trim();
  const requiredMode = actionMode.value.trim() || defaultMode;
  const upload = actionUpload.checked;
  const lines = [
    "name: VibeBench",
    "",
    "on:",
    "  pull_request:",
    "  push:",
    "    branches:",
    "      - main",
    "",
    "permissions:",
    "  contents: read",
    "",
    "jobs:",
    "  vibebench:",
    "    runs-on: ubuntu-latest",
    "",
    "    steps:",
    "      - name: Check out repository",
    "        uses: actions/checkout@v5",
    "",
    "      - name: Set up Python",
    "        uses: actions/setup-python@v6",
    "        with:",
    '          python-version: "3.11"',
    "",
    "      - name: Run VibeBench",
    "        uses: wemby-1/vibebench-arena@main",
    "        with:",
    `          preset: ${presetName}`,
  ];
  if (configPath) {
    lines.push(`          config: ${configPath}`);
  }
  if (requiredMode) {
    lines.push(`          required-mode: ${requiredMode}`);
  }
  lines.push(`          upload-artifacts: ${String(upload)}`);
  lines.push("          artifact-name: vibebench-evidence");
  actionSnippet.textContent = `${lines.join("\n")}\n`;
};

if (actionPreset && actionConfig && actionMode && actionUpload) {
  actionPreset.addEventListener("change", () => {
    const preset = actionPresets.find((item) => item.name === actionPreset.value);
    actionMode.value = preset?.required_mode || actionMode.value;
    actionUpload.checked = Boolean(preset?.uploads_by_default);
    renderActionWorkflow();
  });
  actionConfig.addEventListener("input", renderActionWorkflow);
  actionMode.addEventListener("input", renderActionWorkflow);
  actionUpload.addEventListener("change", renderActionWorkflow);
  renderActionWorkflow();
}

document.querySelectorAll("[data-copy-target]").forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.getAttribute("data-copy-target");
    const target = targetId ? document.getElementById(targetId) : null;
    const text = target?.textContent?.trim();
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      const originalText = button.dataset.copyLabel || button.textContent || "Copy";
      button.dataset.copyLabel = originalText;
      button.textContent = "Copied";
      button.dataset.copied = "true";
      if (copyFeedback) {
        copyFeedback.textContent = "Content copied. The text remains visible and selectable.";
      }
      window.setTimeout(() => {
        button.textContent = button.dataset.copyLabel || "Copy";
        button.dataset.copied = "false";
      }, 2200);
    } catch {
      if (copyFeedback) {
        copyFeedback.textContent = "Copy unavailable. Select the visible command text instead.";
      }
    }
  });
});
