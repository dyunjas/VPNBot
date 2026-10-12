export const tokenKey = "cabinet_access_token";
let refreshing = null;

export function friendlyError(value, status = 0) {
  const message = typeof value === "string" ? value.trim() : "";
  if (status === 403 && message === "Request origin is not allowed") return "Адрес сайта не разрешён в настройках сервера. Обратитесь в поддержку.";
  if (status === 403 && message === "HTTPS is required") return "Для входа нужен HTTPS. Если сайт уже открыт по HTTPS, обратитесь в поддержку: сервер неверно определяет защищённое соединение.";
  if (status >= 500) return "Сервис временно недоступен. Попробуйте ещё раз через несколько минут.";
  if (status === 401) return "Сессия истекла. Войдите в кабинет ещё раз.";
  if (status === 403) return "Доступ к этому действию запрещён. Обратитесь в поддержку.";
  if (status === 422) return "Проверьте введённые данные и попробуйте ещё раз.";
  if (status === 429) return /code|код/i.test(message) ? "Код уже отправлен. Подождите немного перед повторной попыткой." : "Слишком много запросов. Подождите немного и попробуйте ещё раз.";
  if (/not found|user with this email/i.test(message)) return "Пользователь с такими данными не найден.";
  if (/invalid or expired|неверный или просроченный/i.test(message)) return "Код неверный или срок его действия истёк.";
  if (/failed to fetch|networkerror|load failed/i.test(message)) return "Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.";
  if (/renewed within|продление доступно/i.test(message)) return "Продление пока недоступно. Проверьте дату окончания текущей подписки.";
  if (status === 409 && !/[а-яё]/i.test(message)) return "Операция сейчас недоступна. Обновите данные и проверьте условия подписки.";
  if (!message || /^HTTP\s+\d+$/i.test(message) || !/[а-яё]/i.test(message)) return "Не удалось выполнить запрос. Попробуйте ещё раз.";
  return message;
}

export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  const token = localStorage.getItem(tokenKey);
  if (token) headers.Authorization = `Bearer ${token}`;
  const method = (options.method || "POST").toUpperCase();
  const request = () => fetch(path, { credentials:"include", ...options, method, headers, body:["GET","HEAD"].includes(method) ? undefined : options.body === undefined ? "{}" : options.body });
  const protectedRequest = !path.startsWith("/api/auth/") || path === "/api/auth/me";
  let response;
  try {
    response = await request();
    if (response.status === 401 && protectedRequest) {
      if (!refreshing) refreshing = fetch("/api/auth/refresh", {method:"POST",credentials:"include"}).then(async response=>{
        const data = await response.json().catch(()=>({}));
        if (!response.ok || !data.access_token) throw new Error("refresh");
        localStorage.setItem(tokenKey,data.access_token);
        return data.access_token;
      }).finally(()=>{refreshing=null;});
      try {headers.Authorization=`Bearer ${await refreshing}`;response=await request();} catch {}
    }
  } catch (error) { throw new Error(friendlyError(error.message)); }
  const data = await response.json().catch(()=>({}));
  if (!response.ok) {
    const error = new Error(friendlyError(data.detail || data.error, response.status));
    error.status=response.status;
    if(response.status===401&&protectedRequest){localStorage.removeItem(tokenKey);location.replace("/cabinet/login");}
    throw error;
  }
  return data;
}
