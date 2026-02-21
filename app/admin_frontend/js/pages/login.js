document.addEventListener("DOMContentLoaded", () => {
  if (getToken()) {
    window.location.replace("/admin/dashboard.html");
    return;
  }

  q("submit").addEventListener("click", async (e) => {
    q("error").textContent = "";
    await withButtonLoading(e.currentTarget, async () => {
      const data = await api("/admin-api/auth/login", {
        method: "POST",
        body: JSON.stringify({
          login: q("login").value.trim(),
          password: q("password").value,
        }),
      });
      setToken(data.access_token);
      window.location.replace("/admin/dashboard.html");
    }).catch((err) => {
      q("error").textContent = err.message || "Ошибка входа";
    });
  });
});
