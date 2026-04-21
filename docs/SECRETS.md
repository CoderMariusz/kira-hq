# Secrets — Kira-HQ

Source of truth: PRD §6.5. Implementation: `src/kira_hq/secrets_schema.py`.

## Layout

```
~/.kira-hq/.env              # global, chmod 600, gitignored
~/Projects/<name>/.env       # per-project override, chmod 600, gitignored
```

Per-project values **override** global values on the same key. Missing
per-project file is fine — global values are used.

Loader: `kira_hq.secrets_schema.load_secrets(project_name=None)` returns a
merged `dict[str, str]`. Does NOT mutate `os.environ`.

## Schema (PRD §6.5)

| Key                     | Purpose                                           |
|-------------------------|---------------------------------------------------|
| TELEGRAM_BOT_TOKEN      | Hermes Telegram gateway bot token                 |
| TELEGRAM_ALLOWED_CHATS  | Comma-separated chat IDs allowed to command bot   |
| OPENROUTER_API_KEY      | Fallback LLM when Claude OAuth rate-limits        |
| MINIMAX_API_KEY         | Fallback LLM (MiniMax / Kimi)                     |
| GITHUB_TOKEN            | Pages auto-commit + future PR automation          |
| KIRA_HQ_USER            | FastAPI HTTP Basic username (when exposed)        |
| KIRA_HQ_PASS            | FastAPI HTTP Basic password (when exposed)        |

Templates live at `templates/env.kira-hq.example` and
`templates/env.project.example`. Copy the global one with:

```sh
cp ~/.kira-hq/.env.example ~/.kira-hq/.env
chmod 600 ~/.kira-hq/.env
```

## File-permission policy

Every load path checks the file mode. If group- or world-readable bits are
set, `InsecurePermissionsWarning` is emitted. The runtime does not refuse
to load — it only warns — so CI and test fixtures still work, but the
operator is nudged. Fix with:

```sh
chmod 600 ~/.kira-hq/.env ~/Projects/<name>/.env
```

## Gitignore

The project root `.gitignore` already contains `.env`. Per-project repos
must also ignore `.env` (kira-hq-init / add-project ensures this).

## Rotation procedure (manual in v2 — no automation)

No rotation automation in v2 (per PRD §6.5). Document dates below after
each rotation.

### Per-provider steps

**TELEGRAM_BOT_TOKEN**
1. Open chat with @BotFather → `/revoke` → pick bot.
2. `/token` → pick bot → copy new token.
3. Update `~/.kira-hq/.env`. Restart Hermes (`hermes restart`).

**OPENROUTER_API_KEY**
1. https://openrouter.ai/keys → delete old key → "Create Key".
2. Update `.env`. No restart needed (reloaded per run).

**MINIMAX_API_KEY**
1. MiniMax console → API Keys → regenerate.
2. Update `.env`.

**GITHUB_TOKEN**
1. https://github.com/settings/tokens → Revoke old PAT.
2. Generate new fine-grained PAT with `repo` + `workflow` scopes
   on kira-hq Pages repo (+ any other project repos using the token).
3. Update `.env`.

**KIRA_HQ_USER / KIRA_HQ_PASS**
1. Regenerate pass: `openssl rand -base64 24`.
2. Update `.env`.
3. Update any Vercel / Tailscale deployments that reference it.
4. Restart uvicorn.

> **Rotation rule (T-17):** When Kira-HQ is exposed beyond localhost
> (`KIRA_HQ_EXPOSED=true`), rotate `KIRA_HQ_PASS` **immediately** after
> any of: laptop loss/theft, shared Tailscale node compromise, a former
> collaborator losing access, or every 90 days minimum. The HTTPBasic
> gate has no revocation list — rotating the password is the only way
> to invalidate a leaked credential. Bump the "Last rotated" row below
> each time.

### Last-rotated table

| Key                    | Last rotated | By       | Notes       |
|------------------------|--------------|----------|-------------|
| TELEGRAM_BOT_TOKEN     |              |          |             |
| TELEGRAM_ALLOWED_CHATS |              |          | not secret  |
| OPENROUTER_API_KEY     |              |          |             |
| MINIMAX_API_KEY        |              |          |             |
| GITHUB_TOKEN           |              |          |             |
| KIRA_HQ_USER           |              |          | rarely      |
| KIRA_HQ_PASS           |              |          |             |
