(() => {
  const btn = document.getElementById("landing-menu-toggle");
  const menu = document.getElementById("landing-menu");
  if (!btn || !menu) return;

  const close = () => menu.classList.remove("open");
  btn.addEventListener("click", () => menu.classList.toggle("open"));

  menu.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", close);
  });

  document.addEventListener("click", (e) => {
    if (!menu.classList.contains("open")) return;
    if (menu.contains(e.target) || btn.contains(e.target)) return;
    close();
  });
})();

