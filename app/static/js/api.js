const routes = Object.freeze({
  register: "/api/v1/auth/register",
  login: "/api/v1/auth/token",
  me: "/api/v1/users/me",
  user: "/api/v1/users/{id}",
  search: "/api/v1/users/search",
  friends: "/api/v1/friends",
  friend: "/api/v1/friends/{id}",
  mutual: "/api/v1/users/{id}/mutual",
  path: "/api/v1/path/{a}/{b}",
  mySuggestions: "/api/v1/suggestions/me",
  suggestions: "/api/v1/users/{id}/suggestions",
});

let token = sessionStorage.getItem("access_token");
let expiresAt = Number(sessionStorage.getItem("access_token_expires_at") || 0);
let expiryTimer;

function scheduleExpiry() {
  clearTimeout(expiryTimer);
  if (!token || !expiresAt) return;
  const delay = expiresAt - Date.now();
  if (delay <= 0) clearSession();
  else expiryTimer = setTimeout(clearSession, delay);
}

function clearSession() {
  token = null;
  expiresAt = 0;
  sessionStorage.removeItem("access_token");
  sessionStorage.removeItem("access_token_expires_at");
  clearTimeout(expiryTimer);
  window.dispatchEvent(new Event("session-expired"));
}

function ensureFreshToken() {
  if (token && expiresAt && Date.now() >= expiresAt) clearSession();
  return token;
}

async function request(path, { method = "GET", body, form, authenticated = true } = {}) {
  const headers = { Accept: "application/json" };
  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (authenticated) {
    const currentToken = ensureFreshToken();
    if (currentToken) headers.Authorization = `Bearer ${currentToken}`;
  }
  let response;
  try {
    response = await fetch(path, { method, headers, body: payload, credentials: "same-origin" });
  } catch {
    throw new Error("Could not reach the service. Check that it is running and try again.");
  }
  let data = null;
  if (response.status !== 204) {
    try { data = await response.json(); } catch { data = null; }
  }
  if (response.status === 401 && authenticated) clearSession();
  if (!response.ok) {
    const envelope = data?.error;
    const message = envelope?.message || "The request could not be completed.";
    const error = new Error(message);
    error.code = envelope?.code || "HTTP_ERROR";
    error.status = response.status;
    error.retryAfter = response.headers.get("Retry-After");
    throw error;
  }
  return data;
}

function putId(template, id) { return template.replace("{id}", encodeURIComponent(id)); }
function query(values) { return `?${new URLSearchParams(values)}`; }

export const api = {
  routes,
  isSignedIn: () => Boolean(ensureFreshToken()),
  setToken(result) {
    token = result.access_token;
    expiresAt = Date.now() + (result.expires_in * 1000);
    sessionStorage.setItem("access_token", token);
    sessionStorage.setItem("access_token_expires_at", String(expiresAt));
    scheduleExpiry();
  },
  signOut: clearSession,
  register: (payload) => request(routes.register, { method: "POST", body: payload, authenticated: false }),
  login: (email, password) => request(routes.login, { method: "POST", form: { username: email, password }, authenticated: false }),
  me: () => request(routes.me),
  user: (id) => request(putId(routes.user, id)),
  updateMe: (payload) => request(routes.me, { method: "PUT", body: payload }),
  search: (q, offset = 0) => request(routes.search + query({ q, limit: 20, offset })),
  friends: (offset = 0, limit = 20) => request(routes.friends + query({ limit, offset })),
  addFriend: (id) => request(putId(routes.friend, id), { method: "POST" }),
  removeFriend: (id) => request(putId(routes.friend, id), { method: "DELETE" }),
  mutual: (id) => request(putId(routes.mutual, id) + query({ limit: 100, offset: 0 })),
  path: (a, b) => request(routes.path.replace("{a}", encodeURIComponent(a)).replace("{b}", encodeURIComponent(b))),
  mySuggestions: (offset = 0) => request(routes.mySuggestions + query({ limit: 20, offset })),
  suggestionsFor: (id, offset = 0) => request(putId(routes.suggestions, id) + query({ limit: 20, offset })),
};

scheduleExpiry();
