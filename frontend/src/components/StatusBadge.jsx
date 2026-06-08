const STATUS_MAP = {
  registered:    ["muted",   "Registrada"],
  queued:        ["info",    "Na fila"],
  building:      ["info",    "Construindo"],
  build_success: ["success", "Build OK"],
  build_failed:  ["danger",  "Build falhou"],
  scanning:      ["info",    "Escaneando"],
  scan_passed:   ["success", "Scan OK"],
  scan_failed:   ["warning", "Scan falhou"],
  deploying:     ["info",    "Deployando"],
  deployed:      ["success", "Deployada"],
  deploy_failed: ["danger",  "Deploy falhou"],
};

export default function StatusBadge({ status }) {
  const [variant, label] = STATUS_MAP[status] ?? ["muted", status];
  return <span className={`badge badge-${variant}`}>{label}</span>;
}
