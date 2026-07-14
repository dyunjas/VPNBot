function normalizeLoginError(err) {
  const raw = String(err?.message || err || "").toLowerCase();
  if (!raw) return "Не удалось выполнить вход";
  if (raw.includes("неверный логин или пароль")) return "Неверный логин или пароль";
  if (raw.includes("unauthorized") || raw.includes("invalid credentials") || raw.includes("wrong password") || raw.includes("wrong login")) {
    return "Неверный логин или пароль";
  }
  if (raw.includes("networkerror") || raw.includes("failed to fetch") || raw.includes("load failed")) {
    return "Не удалось подключиться к серверу";
  }
  if (raw.includes("forbidden") || raw.includes("access denied")) return "Доступ запрещён";
  if (raw.includes("http 500")) return "Ошибка сервера";
  if (raw.includes("http 503")) return "Сервис временно недоступен";
  return String(err?.message || err || "Не удалось выполнить вход");
}

function setInlineError(message, kind = "error") {
  const el = q("error");
  if (!el) return;
  el.classList.remove("is-success", "is-error");
  if (message) {
    el.textContent = message;
    el.classList.add(kind === "success" ? "is-success" : "is-error");
  } else {
    el.textContent = "";
  }
}

function setFieldState(field, isInvalid) {
  if (!field) return;
  field.classList.toggle("is-invalid", Boolean(isInvalid));
}

document.addEventListener("DOMContentLoaded", async () => {
  if (await hasAdminSession()) {
    window.location.replace("/admin/dashboard");
    return;
  }

  const loginInput = q("login");
  const passwordInput = q("password");
  const submitBtn = q("submit");
  const toggleBtn = q("toggle_password");

  const clearErrorOnInput = () => {
    if (q("error")?.textContent) setInlineError("");
    setFieldState(loginInput?.closest(".login-field"), false);
    setFieldState(passwordInput?.closest(".login-field"), false);
  };

  loginInput?.addEventListener("input", clearErrorOnInput);
  passwordInput?.addEventListener("input", clearErrorOnInput);

  toggleBtn?.addEventListener("click", () => {
    const isHidden = passwordInput?.type === "password";
    if (passwordInput) passwordInput.type = isHidden ? "text" : "password";
    toggleBtn.setAttribute("aria-label", isHidden ? "Скрыть пароль" : "Показать пароль");
    toggleBtn.classList.toggle("is-visible", isHidden);
  });

  async function submitLogin() {
    const login = (loginInput?.value || "").trim();
    const password = passwordInput?.value || "";

    if (!login || !password) {
      setInlineError("Введите логин и пароль.");
      setFieldState(loginInput?.closest(".login-field"), !login);
      setFieldState(passwordInput?.closest(".login-field"), !password);
      return;
    }

    setInlineError("");
    setFieldState(loginInput?.closest(".login-field"), false);
    setFieldState(passwordInput?.closest(".login-field"), false);

    await withButtonLoading(submitBtn, async () => {
      await api("/api/admin/auth/login", {
        method: "POST",
        body: JSON.stringify({ login, password }),
      });
      setInlineError("Вход выполнен", "success");
      window.location.replace("/admin/dashboard");
    }).catch((err) => {
      const message = normalizeLoginError(err);
      setInlineError(message, "error");
      const raw = String(err?.message || err || "").toLowerCase();
      const invalid = raw.includes("login") || raw.includes("password") || raw.includes("credentials") || raw.includes("unauthorized") || raw.includes("логин") || raw.includes("пароль");
      setFieldState(loginInput?.closest(".login-field"), invalid);
      setFieldState(passwordInput?.closest(".login-field"), invalid);
    });
  }

  submitBtn?.addEventListener("click", submitLogin);
  [loginInput, passwordInput].forEach((el) => {
    el?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitLogin();
      }
    });
  });
});
