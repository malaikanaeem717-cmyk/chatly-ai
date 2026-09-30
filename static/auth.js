// Auth — the ONLY place that reads/writes tokens or talks to /api/auth/*.
// Every other module imports authHeader() / ensureFreshToken() from here.
const TOKEN_KEY = "chatly_access_token";
const REFRESH_KEY = "chatly_refresh_token";
const EMAIL_KEY = "chatly_email";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken() {
  return localStorage.getItem(REFRESH_KEY);
}

export function getEmail() {
  return localStorage.getItem(EMAIL_KEY);
}

export function setSession(token, refreshToken, email) {
  localStorage.setItem(TOKEN_KEY, token);
  if (refreshToken) localStorage.setItem(REFRESH_KEY, refreshToken);
  if (email) localStorage.setItem(EMAIL_KEY, email);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(EMAIL_KEY);
}

export function isLoggedIn() {
  return !!getToken();
}

export function authHeader() {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function requireLogin() {
  if (!isLoggedIn()) {
    window.location.href = "/login";
  }
}

export async function signUp(email, password) {
  const res = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json();
}

export async function signIn(email, password) {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json();
}

// Called automatically by api.js whenever a request comes back 401 — swaps
// the (expired) access token for a fresh one using the long-lived refresh
// token, completely silently. The user only gets logged out if THIS also
// fails (meaning the refresh token itself is no longer valid).
let _refreshInFlight = null;
export async function refreshAccessToken() {
  if (_refreshInFlight) return _refreshInFlight; // avoid parallel duplicate refreshes

  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;

  _refreshInFlight = (async () => {
    try {
      const res = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      const result = await res.json();
      if (result.success) {
        setSession(result.access_token, result.refresh_token, result.email);
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      _refreshInFlight = null;
    }
  })();

  return _refreshInFlight;
}

export function logout() {
  clearSession();
  window.location.href = "/login";
}