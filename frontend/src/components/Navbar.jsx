import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { auth } from "../api";

export default function Navbar() {
  const navigate = useNavigate();
  const token = localStorage.getItem("sf_token");
  const [email, setEmail] = useState(null);

  useEffect(() => {
    if (token) {
      auth.me().then(u => setEmail(u?.email)).catch(() => {});
    }
  }, [token]);

  function handleLogout() {
    auth.logout();
    navigate("/login");
  }

  return (
    <nav style={{
      background: "var(--surface)",
      borderBottom: "1px solid var(--border)",
      padding: "0 24px",
      display: "flex",
      alignItems: "center",
      height: 56,
      gap: 24,
    }}>
      <Link to="/" style={{ fontWeight: 700, fontSize: 18, color: "var(--primary)", textDecoration: "none" }}>
        🛡 FoolGuard
      </Link>
      <div style={{ flex: 1 }} />
      {token ? (
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {email && (
            <div
              title={`Logado como ${email}`}
              style={{
                width: 32, height: 32,
                borderRadius: "50%",
                background: "var(--primary)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 14, fontWeight: 700, color: "var(--on-primary)",
                userSelect: "none",
              }}
            >
              {email[0].toUpperCase()}
            </div>
          )}
          <button className="btn-ghost" onClick={handleLogout}>Sair</button>
        </div>
      ) : (
        <>
          <Link to="/login">Login</Link>
          <Link to="/register">Cadastrar</Link>
        </>
      )}
    </nav>
  );
}
