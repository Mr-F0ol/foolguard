import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apps } from "../api";
import StatusBadge from "../components/StatusBadge";

function Section({ title, children }) {
  return (
    <section style={{ marginBottom: 32 }}>
      <h3 className="section-title">{title}</h3>
      {children}
    </section>
  );
}

// ── Build history mini-chart ──────────────────────────────────────────────────
function BuildHistoryChart({ builds }) {
  if (builds.length === 0) return null;
  const recent = [...builds].slice(0, 20).reverse();
  const total = recent.length;
  const passed = recent.filter(b => b.success).length;

  return (
    <div className="build-chart">
      <div className="build-chart-label">
        Histórico de builds — {passed}/{total} passaram
      </div>
      <div className="build-chart-bars">
        {recent.map(b => (
          <div
            key={b.id}
            className={`build-bar ${b.success ? "success" : "fail"}`}
            title={`Build #${b.id} — ${b.success ? "Sucesso" : "Falhou"} — ${new Date(b.created_at).toLocaleString("pt-BR")}`}
          />
        ))}
      </div>
    </div>
  );
}

function BuildsTab({ appId }) {
  const [builds, setBuilds] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apps.listBuilds(appId).then(setBuilds).finally(() => setLoading(false));
  }, [appId]);

  async function handleTrigger() {
    setError("");
    setTriggering(true);
    try {
      await apps.triggerBuild(appId);
      const updated = await apps.listBuilds(appId);
      setBuilds(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setTriggering(false);
    }
  }

  if (loading) return <span className="spinner" />;

  return (
    <>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
        <button className="btn-primary" onClick={handleTrigger} disabled={triggering}>
          {triggering ? <span className="spinner" /> : "Disparar Build"}
        </button>
        {error && <span className="error-msg">{error}</span>}
      </div>

      <BuildHistoryChart builds={builds} />

      {builds.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>Nenhum build ainda.</p>
      ) : (
        <table>
          <thead>
            <tr><th>#</th><th>Resultado</th><th>Data</th><th></th></tr>
          </thead>
          <tbody>
            {builds.map(b => (
              <tr key={b.id}>
                <td>{b.id}</td>
                <td><span className={`badge badge-${b.success ? "success" : "danger"}`}>{b.success ? "Sucesso" : "Falhou"}</span></td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{new Date(b.created_at).toLocaleString("pt-BR")}</td>
                <td>
                  <button className="btn-ghost" style={{ padding: "4px 10px" }} onClick={() => setSelected(b.id === selected ? null : b.id)}>
                    {b.id === selected ? "Ocultar" : "Ver log"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {selected && (
        <div className="log-output" style={{ marginTop: 16 }}>
          {builds.find(b => b.id === selected)?.output || "(sem saída)"}
        </div>
      )}
    </>
  );
}

// ── Findings detail tables ────────────────────────────────────────────────────
function FindingsDetail({ tool, rawOutput }) {
  let data;
  try { data = JSON.parse(rawOutput); } catch { return <p style={{ color: "var(--muted)" }}>Saída inválida.</p>; }

  if (data.error) {
    return <p style={{ color: "var(--danger)", fontSize: 12 }}>{data.error}</p>;
  }

  if (tool === "semgrep") {
    const results = data.results || [];
    if (results.length === 0) return <p style={{ color: "var(--muted)", fontSize: 12 }}>Nenhum finding.</p>;
    return (
      <table style={{ marginTop: 12, fontSize: 12 }}>
        <thead><tr><th>Regra</th><th>Arquivo</th><th>Linha</th><th>Severidade</th><th>Mensagem</th></tr></thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i}>
              <td style={{ color: "var(--primary)", fontFamily: "monospace" }}>{r.check_id?.split(".").pop()}</td>
              <td style={{ fontFamily: "monospace", color: "var(--muted)" }}>{r.path}</td>
              <td>{r.start?.line}</td>
              <td>
                <span className={`badge badge-${r.extra?.severity === "ERROR" ? "danger" : "warning"}`}>
                  {r.extra?.severity}
                </span>
              </td>
              <td style={{ color: "var(--text)", maxWidth: 300 }}>{r.extra?.message}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (tool === "gitleaks") {
    const findings = Array.isArray(data) ? data : [];
    if (findings.length === 0) return <p style={{ color: "var(--muted)", fontSize: 12 }}>Nenhum finding.</p>;
    return (
      <table style={{ marginTop: 12, fontSize: 12 }}>
        <thead><tr><th>Regra</th><th>Arquivo</th><th>Linha</th><th>Secret (mascarado)</th></tr></thead>
        <tbody>
          {findings.map((f, i) => (
            <tr key={i}>
              <td style={{ color: "var(--primary)" }}>{f.RuleID}</td>
              <td style={{ fontFamily: "monospace", color: "var(--muted)" }}>{f.File}</td>
              <td>{f.StartLine}</td>
              <td style={{ fontFamily: "monospace", color: "var(--warning)" }}>
                {f.Secret ? f.Secret.slice(0, 4) + "****" + f.Secret.slice(-2) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  if (tool === "trivy") {
    const vulns = (data.Results || []).flatMap(r => (r.Vulnerabilities || []).map(v => ({ ...v, target: r.Target })));
    if (vulns.length === 0) return <p style={{ color: "var(--muted)", fontSize: 12 }}>Nenhuma vulnerabilidade encontrada.</p>;
    return (
      <table style={{ marginTop: 12, fontSize: 12 }}>
        <thead><tr><th>CVE</th><th>Pacote</th><th>Severidade</th><th>Versão instalada</th><th>Versão corrigida</th></tr></thead>
        <tbody>
          {vulns.map((v, i) => (
            <tr key={i}>
              <td style={{ color: "var(--primary)", fontFamily: "monospace" }}>{v.VulnerabilityID}</td>
              <td>{v.PkgName}</td>
              <td>
                <span className={`badge badge-${v.Severity === "CRITICAL" ? "danger" : "warning"}`}>
                  {v.Severity}
                </span>
              </td>
              <td style={{ fontFamily: "monospace", color: "var(--muted)" }}>{v.InstalledVersion}</td>
              <td style={{ fontFamily: "monospace", color: "var(--success)" }}>{v.FixedVersion || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    );
  }

  return <pre style={{ fontSize: 11, color: "var(--muted)", marginTop: 8, whiteSpace: "pre-wrap" }}>{rawOutput}</pre>;
}

function ScansTab({ appId }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(null);

  useEffect(() => {
    apps.getScans(appId).then(setSummary).finally(() => setLoading(false));
  }, [appId]);

  if (loading) return <span className="spinner" />;
  if (!summary || summary.results.length === 0) return <p style={{ color: "var(--muted)" }}>Nenhum scan realizado ainda.</p>;

  const toolIcon = { trivy: "🐳", semgrep: "🔍", gitleaks: "🔑" };

  // Group by tool, keep only latest per tool
  const latestByTool = {};
  for (const r of summary.results) {
    if (!latestByTool[r.tool]) latestByTool[r.tool] = r;
  }
  const latestResults = Object.values(latestByTool);

  return (
    <>
      <div style={{ marginBottom: 16 }}>
        <span className={`badge badge-${summary.all_passed ? "success" : "danger"}`} style={{ fontSize: 13, padding: "4px 12px" }}>
          {summary.all_passed ? "✓ Todos os scans passaram" : "✗ Scan com findings"}
        </span>
      </div>
      <div className="grid-3">
        {latestResults.map(r => (
          <div
            key={r.id}
            className={`card scan-card ${expanded === r.id ? "expanded" : ""}`}
            style={{ borderColor: r.passed ? "var(--border)" : "var(--danger)", cursor: "pointer" }}
            onClick={() => setExpanded(expanded === r.id ? null : r.id)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <div style={{ fontSize: 20 }}>{toolIcon[r.tool] ?? "🔒"} <strong>{r.tool}</strong></div>
              <span style={{ fontSize: 11, color: "var(--muted)" }}>{expanded === r.id ? "▲" : "▼"}</span>
            </div>
            <div style={{ marginBottom: 4 }}>
              <span className={`badge badge-${r.passed ? "success" : "danger"}`}>
                {r.passed ? "Passou" : "Falhou"}
              </span>
            </div>
            <div style={{ color: "var(--muted)", fontSize: 12 }}>
              {r.findings_count} finding{r.findings_count !== 1 ? "s" : ""}
            </div>
            <div style={{ color: "var(--muted)", fontSize: 11, marginTop: 4 }}>
              {new Date(r.created_at).toLocaleString("pt-BR")}
            </div>
          </div>
        ))}
      </div>

      {expanded && (() => {
        const r = summary.results.find(x => x.id === expanded);
        if (!r) return null;
        return (
          <div className="findings-panel">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h4 style={{ fontWeight: 600 }}>{toolIcon[r.tool]} {r.tool} — detalhes dos findings</h4>
              <button className="btn-ghost" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => setExpanded(null)}>
                Fechar
              </button>
            </div>
            <FindingsDetail tool={r.tool} rawOutput={r.raw_output} />
          </div>
        );
      })()}

      {summary.results.length > latestResults.length && (
        <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 12 }}>
          {summary.results.length} scans no histórico total — exibindo apenas o mais recente por ferramenta.
        </p>
      )}
    </>
  );
}

function DeploymentsTab({ appId }) {
  const [deploys, setDeploys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    apps.listDeployments(appId).then(setDeploys).finally(() => setLoading(false));
  }, [appId]);

  async function handleDeploy() {
    setError("");
    setTriggering(true);
    try {
      await apps.triggerDeploy(appId);
      const updated = await apps.listDeployments(appId);
      setDeploys(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setTriggering(false);
    }
  }

  if (loading) return <span className="spinner" />;

  return (
    <>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
        <button className="btn-primary" onClick={handleDeploy} disabled={triggering}>
          {triggering ? <span className="spinner" /> : "Fazer Deploy"}
        </button>
        {error && <span className="error-msg">{error}</span>}
      </div>
      {deploys.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>Nenhum deploy ainda.</p>
      ) : (
        <table>
          <thead>
            <tr><th>#</th><th>Status</th><th>Endpoint</th><th>Data</th><th></th></tr>
          </thead>
          <tbody>
            {deploys.map(d => (
              <tr key={d.id}>
                <td>{d.id}</td>
                <td><StatusBadge status={d.status} /></td>
                <td>
                  {d.endpoint_url
                    ? <a href={d.endpoint_url} target="_blank" rel="noreferrer">{d.endpoint_url}</a>
                    : <span style={{ color: "var(--muted)" }}>—</span>
                  }
                </td>
                <td style={{ color: "var(--muted)", fontSize: 12 }}>{new Date(d.created_at).toLocaleString("pt-BR")}</td>
                <td>
                  <button className="btn-ghost" style={{ padding: "4px 10px" }} onClick={() => setSelected(d.id === selected ? null : d.id)}>
                    {d.id === selected ? "Ocultar" : "Log"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {selected && (
        <div className="log-output" style={{ marginTop: 16 }}>
          {deploys.find(d => d.id === selected)?.deploy_log || "(sem saída)"}
        </div>
      )}
    </>
  );
}

function AlertsTab({ appId }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);

  const load = useCallback(() => {
    apps.listAlerts(appId, !showAll).then(setAlerts).finally(() => setLoading(false));
  }, [appId, showAll]);

  useEffect(() => { load(); }, [load]);

  async function acknowledge(alertId) {
    await apps.acknowledgeAlert(appId, alertId);
    load();
  }

  if (loading) return <span className="spinner" />;

  return (
    <>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
        <button className="btn-ghost" onClick={() => setShowAll(v => !v)}>
          {showAll ? "Mostrar apenas ativos" : "Ver histórico completo"}
        </button>
      </div>
      {alerts.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>{showAll ? "Nenhum alerta registrado." : "Nenhum alerta ativo."}</p>
      ) : (
        alerts.map(a => (
          <div key={a.id} className={`alert-bar ${a.level}`} style={{ justifyContent: "space-between" }}>
            <span>
              <strong style={{ textTransform: "capitalize" }}>{a.level}:</strong> {a.message}
              <span style={{ marginLeft: 8, fontSize: 11, opacity: 0.7 }}>{new Date(a.created_at).toLocaleString("pt-BR")}</span>
            </span>
            {!a.acknowledged && (
              <button
                onClick={() => acknowledge(a.id)}
                style={{ background: "transparent", border: "1px solid currentColor", color: "inherit", padding: "2px 8px", borderRadius: 4, fontSize: 11, cursor: "pointer" }}
              >
                Reconhecer
              </button>
            )}
          </div>
        ))
      )}
    </>
  );
}

const TABS = ["Builds", "Segurança", "Deploys", "Alertas"];

export default function AppDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [app, setApp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    apps.get(id).then(setApp).catch(() => navigate("/")).finally(() => setLoading(false));
  }, [id, navigate]);

  async function handleDelete() {
    if (!confirm(`Deletar "${app.name}"? Esta ação não pode ser desfeita.`)) return;
    setDeleting(true);
    try {
      await apps.delete(id);
      navigate("/");
    } finally {
      setDeleting(false);
    }
  }

  if (loading) return <div className="page"><span className="spinner" /></div>;
  if (!app) return null;

  return (
    <div className="page">
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 32 }}>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700 }}>{app.name}</h1>
          <a href={app.repo_url} target="_blank" rel="noreferrer" style={{ color: "var(--muted)", fontSize: 13 }}>
            {app.repo_url}
          </a>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <StatusBadge status={app.status} />
          <button className="btn-danger" onClick={handleDelete} disabled={deleting} style={{ padding: "6px 12px" }}>
            {deleting ? <span className="spinner" /> : "Deletar"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: "1px solid var(--border)", marginBottom: 24 }}>
        {TABS.map((t, i) => (
          <button
            key={t}
            onClick={() => setTab(i)}
            style={{
              background: "transparent",
              border: "none",
              borderBottom: tab === i ? "2px solid var(--primary)" : "2px solid transparent",
              borderRadius: 0,
              color: tab === i ? "var(--text)" : "var(--muted)",
              padding: "8px 16px",
              fontWeight: tab === i ? 600 : 400,
              cursor: "pointer",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="card">
        {tab === 0 && <BuildsTab appId={id} />}
        {tab === 1 && <ScansTab appId={id} />}
        {tab === 2 && <DeploymentsTab appId={id} />}
        {tab === 3 && <AlertsTab appId={id} />}
      </div>
    </div>
  );
}
