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
