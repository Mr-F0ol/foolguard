/**
 * Gera demo.gif do FoolGuard para o README.
 * Uso: node scripts/record-demo.mjs
 * Requer: app rodando em localhost:3000 e ffmpeg no PATH.
 */

import puppeteer from "puppeteer";
import { execSync } from "child_process";
import { mkdirSync, rmSync, existsSync } from "fs";
import { join } from "path";

const BASE    = "http://localhost:3000";
const API     = "http://localhost:8000/api";
const FRAMES  = "docs/demo-frames";
const OUT_GIF = "docs/demo.gif";
const FPS     = 8;

const EMAIL = `demo_gif_${Date.now()}@foolguard.dev`;
const PASS  = "FoolGuard2024!";
const REPO  = "https://github.com/Mr-F0ol/hello-secureflow";

let frameIdx = 0;

async function api(path, opts = {}) {
  const { headers: extra = {}, ...rest } = opts;
  const r = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...extra },
    ...rest,
  });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  if (r.status === 204) return null;
  return r.json();
}

async function frames(page, seconds) {
  const total = Math.round(seconds * FPS);
  for (let i = 0; i < total; i++) {
    const num = String(frameIdx++).padStart(5, "0");
    await page.screenshot({ path: join(FRAMES, `frame_${num}.png`) });
    await new Promise(r => setTimeout(r, 1000 / FPS));
  }
}

async function main() {
  if (existsSync(FRAMES)) rmSync(FRAMES, { recursive: true });
  mkdirSync(FRAMES, { recursive: true });
  mkdirSync("docs", { recursive: true });

  // ── Setup: criar usuário e app via API ──────────────────────────────────────
  console.log("Preparando dados demo...");
  await api("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email: EMAIL, password: PASS }),
  });
  const { access_token } = await api("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: EMAIL, password: PASS }),
  });
  const auth = { Authorization: `Bearer ${access_token}` };

  const browser = await puppeteer.launch({
    headless: true,
    defaultViewport: { width: 1280, height: 720 },
    args: ["--no-sandbox"],
  });

  const page = await browser.newPage();

  // ── 1. Tela de login ────────────────────────────────────────────────────────
  console.log("Gravando: tela de login...");
  await page.goto(`${BASE}/login`, { waitUntil: "networkidle2" });
  await frames(page, 1.5);

  // ── 2. Digitar credenciais ──────────────────────────────────────────────────
  console.log("Gravando: preenchendo login...");
  await page.click('input[type="email"]');
  await page.type('input[type="email"]', EMAIL, { delay: 60 });
  await frames(page, 0.5);
  await page.click('input[type="password"]');
  await page.type('input[type="password"]', PASS, { delay: 60 });
  await frames(page, 0.5);

  // Salvar token antes de submeter (para não depender do redirect)
  await page.evaluate((token) => localStorage.setItem("sf_token", token), access_token);
  await frames(page, 0.3);

  // ── 3. Dashboard ────────────────────────────────────────────────────────────
  console.log("Gravando: dashboard...");
  await page.goto(`${BASE}/`, { waitUntil: "networkidle2" });
  await frames(page, 2);

  // ── 4. Cadastrar nova aplicação ─────────────────────────────────────────────
  console.log("Gravando: cadastrando app...");
  await page.click('input[placeholder="Minha API"]');
  await page.type('input[placeholder="Minha API"]', "hello-secureflow", { delay: 55 });
  await frames(page, 0.4);
  await page.click('input[placeholder="https://github.com/usuario/repo"]');
  await page.type('input[placeholder="https://github.com/usuario/repo"]', REPO, { delay: 30 });
  await frames(page, 0.5);
  await page.click('button.btn-primary');
  await page.waitForSelector(".app-card", { timeout: 5000 });
  await frames(page, 1.5);

  // ── 5. Abrir detalhe do app ─────────────────────────────────────────────────
  console.log("Gravando: detalhe do app...");
  const appData = await api("/applications", { headers: auth });
  const appId = appData[0]?.id;
  await page.goto(`${BASE}/apps/${appId}`, { waitUntil: "networkidle2" });
  await frames(page, 1.5);

  // ── 6. Disparar build ───────────────────────────────────────────────────────
  console.log("Gravando: disparando build...");
  await page.click('button.btn-primary');   // "Disparar Build"
  await frames(page, 1);

  // Aguarda build terminar via API
  console.log("Aguardando build + scan...");
  for (let i = 0; i < 36; i++) {
    await new Promise(r => setTimeout(r, 5000));
    const app = await api(`/applications/${appId}`, { headers: auth });
    console.log(`  status: ${app.status}`);
    if (["scan_passed", "scan_failed", "build_failed"].includes(app.status)) break;
  }

  // Recarregar página para mostrar resultado
  await page.goto(`${BASE}/apps/${appId}`, { waitUntil: "networkidle2" });
  await frames(page, 2);

  // ── 7. Aba Segurança ────────────────────────────────────────────────────────
  console.log("Gravando: aba segurança...");
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll("button")].find(b => b.textContent.trim() === "Segurança");
    if (btn) btn.click();
  });
  await new Promise(r => setTimeout(r, 800));
  await frames(page, 2.5);

  // ── 8. Expandir finding do Semgrep ─────────────────────────────────────────
  console.log("Gravando: expandindo finding...");
  await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".scan-card")];
    const semgrep = cards.find(c => c.textContent.includes("semgrep"));
    if (semgrep) semgrep.click();
  });
  await new Promise(r => setTimeout(r, 600));
  await frames(page, 3);

  await browser.close();

  // ── Encoder: frames → GIF ───────────────────────────────────────────────────
  console.log(`\nGerando GIF (${frameIdx} frames a ${FPS}fps)...`);
  execSync(
    `ffmpeg -y -framerate ${FPS} -i "${FRAMES}/frame_%05d.png" ` +
    `-vf "fps=${FPS},scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer" ` +
    `"${OUT_GIF}"`,
    { stdio: "inherit" }
  );

  rmSync(FRAMES, { recursive: true });
  console.log(`\n✅ GIF salvo em ${OUT_GIF}`);
}

main().catch(err => { console.error(err.message); process.exit(1); });
