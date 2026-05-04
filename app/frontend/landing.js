function randomToken(size = 18) {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < size; i += 1) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

document.addEventListener("DOMContentLoaded", () => {
  const keyEl = document.getElementById("sub-key");
  if (keyEl) {
    keyEl.textContent = `https://lunetpn.ru/sub/${randomToken(18)}`;
  }
});
