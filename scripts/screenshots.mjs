/**
 * Gera screenshots automáticas do FoolGuard para o README.
 * Uso: node scripts/screenshots.mjs
 * Requer que o app esteja rodando em http://localhost:3000
 */

import puppeteer from "puppeteer";

const BASE = "http://localhost:3000";
const API  = "http://localhost:8000/api";

const DEMO_EMAIL = `demo_${Date.now()}@foolguard.dev`;
const DEMO_PASS  = "FoolGuard2024!";
const DEMO_REPO  = "https://github.com/Mr-F0ol/hello-secureflow";

async function api(path, opts = {}) {
  const { headers: extraHeaders = {}, ...restOpts } = opts;
  const r = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...extraHeaders },
    ...restOpts,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`API ${path} → ${r.status}: ${t}`);
  }
  if (r.status === 204) return null;
  return r.json();
}

async function main() {
  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: { width: 1280, height: 800 },
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  try {
    // ── 1. Registrar usuário demo ──────────────────────────────────────────
    console.log("Registrando usuário demo...");
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASS }),
    });

    const { access_token } = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASS }),
    });

    const authHeader = { Authorization: `Bearer ${access_token}` };

    // ── 2. Criar app demo ──────────────────────────────────────────────────
    console.log("Criando aplicação demo...");
    const app = await api("/applications", {
      method: "POST",
      headers: authHeader,
      body: JSON.stringify({ name: "hello-secureflow", repo_url: DEMO_REPO }),
    });

    // ── 3. Login na UI ─────────────────────────────────────────────────────
    const page = await browser.newPage();

    // Salvar token no localStorage antes de navegar
    await page.goto(BASE, { waitUntil: "networkidle2" });
    await page.evaluate((token) => {
      localStorage.setItem("sf_token", token);
    }, access_token);

    // ── 3. Disparar build e aguardar ──────────────────────────────────────
    console.log("Disparando build...");
    await api(`/applications/${app.id}/builds`, {
      method: "POST",
      headers: authHeader,
    });

    // Aguarda o build terminar verificando o status da aplicação (máx 3 min)
    let buildDone = false;
    for (let i = 0; i < 36; i++) {
      await new Promise(r => setTimeout(r, 5000));
      const appState = await api(`/applications/${app.id}`, { headers: authHeader });
      console.log(`  App status: ${appState?.status ?? "?"}`);
      if (["scan_passed", "scan_failed", "build_failed"].includes(appState?.status)) {
        buildDone = true;
        break;
      }
    }
    if (!buildDone) console.log("  Build ainda em andamento — prosseguindo com screenshots");

    // ── Screenshot: Login page ─────────────────────────────────────────────
    console.log("Screenshot: login...");
    const loginPage = await browser.newPage();
    await loginPage.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
    await loginPage.screenshot({ path: "docs/screenshots/login.png", fullPage: false });
    await loginPage.close();

    // ── Screenshot: Dashboard ──────────────────────────────────────────────
    console.log("Screenshot: dashboard...");
    await page.goto(`${BASE}/`, { waitUntil: "networkidle2" });
    await page.waitForSelector(".app-card", { timeout: 5000 }).catch(() => {});
    await page.screenshot({ path: "docs/screenshots/dashboard.png", fullPage: false });

    // ── Screenshot: App Detail ─────────────────────────────────────────────
    console.log("Screenshot: app detail...");
    await page.goto(`${BASE}/apps/${app.id}`, { waitUntil: "networkidle2" });
    await new Promise(r => setTimeout(r, 1500));
    await page.screenshot({ path: "docs/screenshots/app-detail.png", fullPage: true });

    // ── Screenshot: Scans tab ──────────────────────────────────────────────
    console.log("Screenshot: scans tab...");
    await page.goto(`${BASE}/apps/${app.id}`, { waitUntil: "networkidle2" });
    await new Promise(r => setTimeout(r, 1000));

    // Clica na aba "Segurança"
    await page.evaluate(() => {
      const btns = [...document.querySelectorAll("button")];
      const seg = btns.find(b => b.textContent.trim() === "Segurança");
      if (seg) seg.click();
    });
    await new Promise(r => setTimeout(r, 1200));
    await page.screenshot({ path: "docs/screenshots/scans.png", fullPage: true });

    console.log("\n✅ Screenshots salvas em docs/screenshots/");
    console.log("  - docs/screenshots/login.png");
    console.log("  - docs/screenshots/dashboard.png");
    console.log("  - docs/screenshots/app-detail.png");
    console.log("  - docs/screenshots/scans.png");

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error("Erro:", err.message);
  process.exit(1);
});
