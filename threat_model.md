# Threat Model — FoolGuard

**Data:** 2026-06-07  
**Metodologia:** STRIDE  
**Escopo:** A plataforma FoolGuard em si (não as aplicações que ela hospeda)

---

## 1. Visão Geral

O FoolGuard é uma plataforma de deploy seguro. Por sua natureza — recebe código de terceiros, o executa em containers, e o publica na nuvem — é um alvo de alto valor. Um atacante que comprometer a plataforma pode:

- Roubar código-fonte e segredos dos usuários
- Usar o ambiente de build para minerar criptomoeda (cryptojacking)
- Injetar código malicioso nas imagens Docker publicadas
- Escalar para o ambiente AWS da plataforma

---

## 2. Ativos a Proteger

| Ativo | Sensibilidade | Impacto se comprometido |
|---|---|---|
| Tokens JWT dos usuários | Alta | Acesso total à conta do usuário |
| Credenciais AWS (ECR, ECS) | Crítica | Acesso irrestrito à infraestrutura |
| Código-fonte das aplicações | Alta | Roubo de IP, exposição de segredos |
| Banco PostgreSQL | Alta | Dump de todos os dados e hashes de senha |
| Docker socket do worker | Crítica | Container escape para o host |
| Secret key do JWT | Crítica | Forja de tokens para qualquer usuário |

---

## 3. Superfícies de Ataque

```
Internet → API (FastAPI) → Worker (Build/Scanner/Deploy) → AWS
              ↕                    ↕
           Redis (fila)       Docker daemon
              ↕
          PostgreSQL
```

---

## 4. Análise STRIDE

### 4.1 Spoofing (Falsificação de Identidade)

**Ameaça:** Atacante forja token JWT para impersonar outro usuário.  
**Vetor:** Brute-force da SECRET_KEY, ou vazamento da SECRET_KEY.  
**Mitigações implementadas:**
- SECRET_KEY carregada via variável de ambiente (nunca hard-coded)
- Tokens têm expiração (`exp` claim)
- Algoritmo HS256 com chave de 256 bits

**Mitigações recomendadas:**
- Rotação periódica da SECRET_KEY
- Implementar refresh tokens para reduzir lifetime do access token

---

### 4.2 Tampering (Adulteração)

**Ameaça A:** Usuário envia repo_url apontando para repositório malicioso.  
**Vetor:** O worker clona qualquer URL sem validação.  
**Mitigação implementada:** O código roda dentro de um container isolado.  
**Mitigação recomendada:** Validar que a URL é um repositório Git público conhecido (GitHub, GitLab); bloquear IPs internos (SSRF via git clone).

**Ameaça B:** Adulteração da imagem Docker no ECR antes do deploy.  
**Mitigação implementada:** ECR com `scan_on_push = true` no Terraform.  
**Mitigação recomendada:** Usar Docker Content Trust (assinatura de imagens).

---

### 4.3 Repudiation (Repúdio)

**Ameaça:** Usuário nega ter disparado um build ou deploy malicioso.  
**Mitigações implementadas:**
- BuildLog e Deployment registram o `application_id` (vinculado ao usuário)
- Timestamps com timezone UTC em todos os eventos

**Mitigação recomendada:** Adicionar campo `triggered_by` (user_id) em BuildLog e Deployment.

---

### 4.4 Information Disclosure (Divulgação de Informações)

**Ameaça A:** Enumeração de usuários via endpoint de registro.  
**Mitigação implementada:** `/api/auth/login` retorna mensagem genérica ("E-mail ou senha inválidos") independente do erro.

**Ameaça B:** Exposição de dados de outro usuário (IDOR).  
**Mitigação implementada:** Toda query filtra por `owner_id == current_user.id`.  
Isso endereça o **OWASP A01:2021 - Broken Access Control**.

**Ameaça C:** Hash de senha vaza pela API.  
**Mitigação implementada:** Nenhum schema de saída (`UserRead`) contém `hashed_password`. Separação explícita de modelos e schemas.

**Ameaça D:** Segredos no código do usuário acessíveis ao operador da plataforma.  
**Mitigação recomendada:** Deletar o diretório temporário imediatamente após o build/scan (já implementado via `TemporaryDirectory()`).

---

### 4.5 Denial of Service (Negação de Serviço)

**Ameaça A:** Usuário envia um repositório enormemente grande ou um Dockerfile com loop infinito.  
**Mitigações implementadas:**
- `timeout=300` no subprocess de `docker build`
- `timeout=120` no subprocess de `git clone`

**Mitigação recomendada:** Limite de tamanho do repositório; `ulimit` de CPU/memória no container de build.

**Ameaça B:** Flood de requisições na API.  
**Mitigação recomendada:** Rate limiting por IP (ex: `slowapi` para FastAPI).

---

### 4.6 Elevation of Privilege (Escalada de Privilégios)

**Ameaça A (crítica):** Container escape via Docker socket.  
**Vetor:** O worker monta `/var/run/docker.sock`, o que dá acesso root ao host.  
**Mitigação parcial:** O worker roda em container separado da API.  
**Mitigação recomendada:**  
- Usar Docker-in-Docker (DinD) em vez de socket binding  
- Ou usar Kaniko (build sem daemon) para builds sem acesso ao host  
- Ou rootless Docker

**Ameaça B:** Escalada via SSRF no git clone.  
**Vetor:** `repo_url = "http://169.254.169.254/..."` acessa o metadata do EC2.  
**Mitigação recomendada:** Validar URLs antes de clonar; usar rede isolada sem acesso ao metadata.

**Ameaça C:** Injeção de SQL via parâmetros de rota.  
**Mitigação implementada:** Uso de SQLAlchemy com queries parametrizadas — nenhuma string SQL concatenada manualmente.

---

## 5. Modelo de Confiança

```
Nível 0 (não autenticado): acesso apenas a /api/auth/register e /api/auth/login
Nível 1 (usuário autenticado): acesso apenas aos próprios recursos
Nível 2 (worker interno): acesso direto ao banco (sem JWT, via rede interna)
Nível 3 (admin/operador): acesso ao host Docker e AWS (fora do escopo da app)
```

Não existe Nível 3 exposto pela API — operações de infraestrutura são feitas pelo worker de forma assíncrona, nunca por chamada direta do usuário.

---

## 6. Decisões de Design Orientadas a Segurança

| Decisão | Justificativa de Segurança |
|---|---|
| Builds em containers isolados | Isola código não confiável do processo principal |
| Senhas com bcrypt | Resistente a brute-force mesmo com dump do banco |
| JWT com expiração | Limita janela de uso de token vazado |
| Schemas separados dos modelos | Evita vazamento acidental de campos sensíveis |
| Query sempre filtra por owner_id | Previne IDOR (OWASP A01) estruturalmente |
| TemporaryDirectory para repos | Garante limpeza automática do código clonado |
| Semgrep + Gitleaks + Trivy | Defesa em profundidade: SAST + secrets + OS/deps |
| Terraform com IAM mínimo | Princípio do menor privilégio na AWS |
| Alertas de monitor com deduplicação | Evita flood de alertas mascarando o sinal real |

---

## 7. Riscos Residuais Conhecidos

| Risco | Probabilidade | Impacto | Plano de mitigação |
|---|---|---|---|
| Docker socket binding | Médio | Crítico | Migrar para Kaniko ou DinD rootless |
| Sem rate limiting | Alto | Alto | Adicionar `slowapi` na API |
| Sem refresh token | Baixo | Médio | Implementar no Mês 6+ |
| SSRF via repo_url | Médio | Alto | Validar URLs e isolar rede do worker |
| Logs de build contêm secrets | Médio | Alto | Implementar redação de segredos nos logs |
