/**
 * Cliente da API FoolGuard.
 *
 * Todas as chamadas passam por aqui, garantindo que o token JWT seja
 * sempre enviado e que erros de autenticação redirecionem para o login.
 */

const BASE = "/api";

function getToken() {
  return localStorage.getItem("sf_token");
}

export function saveToken(token) {
  localStorage.setItem("sf_token", token);
}

export function clearToken() {
  localStorage.removeItem("sf_token");
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    return;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Erro desconhecido");
  }

  if (res.status === 204) return null;
  return res.json();
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const auth = {
  register: (email, password) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),

  login: async (email, password) => {
    const data = await request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (data?.access_token) saveToken(data.access_token);
    return data;
  },

  logout: () => clearToken(),
  me: () => request("/auth/me"),
};

// ── Applications ──────────────────────────────────────────────────────────────

export const apps = {
  list: () => request("/applications"),
  get: (id) => request(`/applications/${id}`),
  create: (name, repo_url) =>
    request("/applications", { method: "POST", body: JSON.stringify({ name, repo_url }) }),
  delete: (id) => request(`/applications/${id}`, { method: "DELETE" }),

  triggerBuild: (id) => request(`/applications/${id}/builds`, { method: "POST" }),
  listBuilds: (id) => request(`/applications/${id}/builds`),

  getScans: (id) => request(`/applications/${id}/scans`),

  triggerDeploy: (id) => request(`/applications/${id}/deployments`, { method: "POST" }),
  listDeployments: (id) => request(`/applications/${id}/deployments`),

  listAlerts: (id, onlyActive = true) =>
    request(`/applications/${id}/alerts?only_active=${onlyActive}`),
  acknowledgeAlert: (appId, alertId) =>
    request(`/applications/${appId}/alerts/${alertId}`, {
      method: "PATCH",
      body: JSON.stringify({ acknowledged: true }),
    }),

  alertsSummary: () => request("/applications/alerts/summary"),
};
