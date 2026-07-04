(() => {
  const btn = document.getElementById("landing-menu-toggle");
  const menu = document.getElementById("landing-menu");
  const backdrop = document.getElementById("landing-menu-backdrop");
  if (!btn || !menu || !backdrop) return;

  const close = () => {
    menu.classList.remove("open");
    document.body.classList.remove("landing-menu-open");
  };
  const open = () => {
    menu.classList.add("open");
    document.body.classList.add("landing-menu-open");
  };

  btn.addEventListener("click", () => {
    if (menu.classList.contains("open")) {
      close();
      return;
    }
    open();
  });

  menu.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", close);
  });

  backdrop.addEventListener("click", close);

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });

  document.addEventListener("click", (e) => {
    if (!menu.classList.contains("open")) return;
    if (menu.contains(e.target) || btn.contains(e.target)) return;
    close();
  });
})();
