import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { auth } from "../api";

export default function Register() {
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
      await auth.register(email, password);
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
        <h2 style={{ marginBottom: 24, fontSize: 20 }}>Criar conta</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>E-mail</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Senha <span style={{ color: "var(--muted)" }}>(mínimo 8 caracteres)</span></label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} minLength={8} required />
          </div>
          {error && <p className="error-msg">{error}</p>}
          <button className="btn-primary" type="submit" disabled={loading} style={{ width: "100%", marginTop: 8 }}>
            {loading ? <span className="spinner" /> : "Criar conta"}
          </button>
        </form>
        <p style={{ marginTop: 16, color: "var(--muted)", textAlign: "center" }}>
          Já tem conta? <Link to="/login">Entrar</Link>
        </p>
      </div>
    </div>
  );
}
