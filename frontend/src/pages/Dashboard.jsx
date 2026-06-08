import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { apps } from "../api";
import StatusBadge from "../components/StatusBadge";

export default function Dashboard() {
  const [appList, setAppList] = useState([]);
  const [summary, setSummary] = useState({ info: 0, warning: 0, critical: 0 });
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);

  async function load() {
    try {
      const [list, sum] = await Promise.all([apps.list(), apps.alertsSummary()]);
      setAppList(list);
      setSummary(sum);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e) {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      await apps.create(name, repoUrl);
      setName("");
      setRepoUrl("");
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  if (loading) return <div className="page"><span className="spinner" /></div>;

  return (
    <div className="page">
      {/* Sumário de alertas */}
      {(summary.critical > 0 || summary.warning > 0) && (
        <div style={{ marginBottom: 24, display: "flex", gap: 12 }}>
          {summary.critical > 0 && (
            <div className="alert-bar critical" style={{ flex: 1 }}>
              🚨 {summary.critical} alerta{summary.critical > 1 ? "s" : ""} crítico{summary.critical > 1 ? "s" : ""}
            </div>
          )}
          {summary.warning > 0 && (
            <div className="alert-bar warning" style={{ flex: 1 }}>
              ⚠️ {summary.warning} aviso{summary.warning > 1 ? "s" : ""}
            </div>
          )}
        </div>
      )}

      <div className="grid-2" style={{ alignItems: "start" }}>
        {/* Lista de aplicações */}
        <div>
          <h2 className="section-title">Minhas Aplicações</h2>
          {appList.length === 0 ? (
            <div className="card" style={{ color: "var(--muted)", textAlign: "center", padding: 40 }}>
              Nenhuma aplicação cadastrada ainda.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {appList.map(app => (
                <Link key={app.id} to={`/apps/${app.id}`} style={{ textDecoration: "none" }}>
                  <div className="card app-card" style={{ cursor: "pointer" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 600, marginBottom: 2 }}>{app.name}</div>
                        <div style={{ color: "var(--muted)", fontSize: 12, wordBreak: "break-all" }}>
                          {app.repo_url}
                        </div>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
                        <StatusBadge status={app.status} />
                        {app.status === "scan_passed" || app.status === "deployed" ? (
                          <span className="sec-badge secure">✅ Seguro</span>
                        ) : app.status === "scan_failed" ? (
                          <span className="sec-badge vulnerable">❌ Vulnerável</span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Formulário de nova aplicação */}
        <div>
          <h2 className="section-title">Nova Aplicação</h2>
          <div className="card">
            <form onSubmit={handleCreate}>
              <div className="form-group">
                <label>Nome</label>
                <input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="Minha API"
                  required
                  maxLength={120}
                />
              </div>
              <div className="form-group">
                <label>URL do Repositório Git</label>
                <input
                  value={repoUrl}
                  onChange={e => setRepoUrl(e.target.value)}
                  placeholder="https://github.com/usuario/repo"
                  required
                  maxLength={500}
                />
              </div>
              {error && <p className="error-msg">{error}</p>}
              <button className="btn-primary" type="submit" disabled={creating}>
                {creating ? <span className="spinner" /> : "Cadastrar"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
