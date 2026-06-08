import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { auth } from "../api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await auth.login(email, password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: "flex", justifyContent: "center", paddingTop: 80 }}>
      <div className="card" style={{ width: "100%", maxWidth: 400 }}>
        <h2 style={{ marginBottom: 24, fontSize: 20 }}>Entrar no FoolGuard</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>E-mail</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Senha</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required />
          </div>
          {error && <p className="error-msg">{error}</p>}
          <button className="btn-primary" type="submit" disabled={loading} style={{ width: "100%", marginTop: 8 }}>
            {loading ? <span className="spinner" /> : "Entrar"}
          </button>
        </form>
        <p style={{ marginTop: 16, color: "var(--muted)", textAlign: "center" }}>
          Não tem conta? <Link to="/register">Cadastre-se</Link>
        </p>
      </div>
    </div>
  );
}
