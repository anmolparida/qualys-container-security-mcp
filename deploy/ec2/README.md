# Quick team hosting on one EC2 instance

The fastest way to let teammates use Sheldon for a while: one EC2 instance running
Docker, with Caddy in front for HTTPS. For a production setup use the ECS stack in
[DEPLOYMENT.md](../../DEPLOYMENT.md).

## How credentials work (nothing secret is shared)

| What | Where it comes from | You share |
|---|---|---|
| Qualys access | Each teammate signs in with **their own** Qualys URL + API token in the browser | Nothing |
| AWS / Bedrock | The instance's **IAM role** — no AWS keys on the box | Nothing |
| AI tokens | `LLM_BILLING=host`: your Bedrock (via the role) pays. `LLM_BILLING=user`: each teammate enters their own Anthropic or Bedrock API key | Nothing |

Teammates only need **the URL**.

## Steps (about 15 minutes)

### 1. Create the IAM role (skip if `LLM_BILLING=user`)

IAM console → Roles → **Create role** → AWS service → **EC2**:

- Attach `AmazonSSMManagedInstanceCore` (lets you open a shell without SSH keys).
- Add an inline policy from [`instance-role-policy.json`](instance-role-policy.json)
  (lets the app call Claude on Bedrock).
- Name it `sheldon-ec2`.

In the Bedrock console (same region), enable **model access** for Claude Haiku 5.5.

### 2. Launch the instance

EC2 console → **Launch instance**:

| Setting | Value |
|---|---|
| AMI | Amazon Linux 2023 |
| Type | `t3.medium` (2 vCPU / 4 GB — the image build needs the memory) |
| Storage | 20 GB gp3 |
| IAM instance profile | `sheldon-ec2` |
| Security group inbound | TCP 443 (and 80) from **your team's IP range or VPN only** — not `0.0.0.0/0` |
| Key pair | Optional (you can use Session Manager instead) |

### 3. Get the code onto it and run setup

Connect: EC2 console → instance → **Connect** → *Session Manager*. Then:

```bash
sudo dnf install -y git
git clone https://github.com/anmolparida/qualys-container-security-mcp.git
cd qualys-container-security-mcp
git checkout aws-deploy-per-user-auth          # or main once merged

sudo LLM_BILLING=host bash deploy/ec2/setup.sh
```

Options for `setup.sh`:

| Variable | Default | Meaning |
|---|---|---|
| `DOMAIN` | unset | A DNS name pointing at the instance → trusted HTTPS certificate (port 80 must be reachable for Let's Encrypt). Unset → self-signed certificate on the IP |
| `LLM_BILLING` | `host` | `host` = you pay via the role; `user` = each teammate brings their own AI key |
| `QUALYS_AUTH_MODE` | `user` | Keep `user` so everyone sees only their own Qualys data |
| `AWS_REGION` | instance region | Bedrock region |
| `BEDROCK_MODEL_ID` | `global.anthropic.claude-haiku-5-5` | Claude model |

The script prints the URL when it finishes.

### 4. Send teammates the link

Share `https://<instance-ip>` (or your `DOMAIN`). Each person:

1. Opens the link (with a self-signed certificate: *Advanced → Proceed*).
2. Picks their Qualys platform and pastes **their own** Qualys API token.
3. If `LLM_BILLING=user`: also adds their Anthropic or Bedrock API key.

MCP users point Cursor / Claude Code at `https://<host>/mcp` with their own
`X-Qualys-Url` + `X-Qualys-Token` headers. MCP clients reject self-signed
certificates, so use a `DOMAIN` if your team will use MCP.

## Day-to-day

```bash
cd qualys-container-security-mcp
C="docker compose -f docker-compose.yml -f deploy/ec2/docker-compose.ec2.yml"
$C logs -f web                       # logs
git pull && $C up -d --build         # update to latest code
$C down                              # stop
```

## Keep it safe and cheap while it's temporary

- **Restrict the security group** to your office/VPN range. The web app has no login of
  its own; without a valid Qualys token people see nothing, but with
  `LLM_BILLING=host` anyone who can reach it can use your Bedrock for doc questions.
- **Set an AWS Budget alert** on Bedrock spend if `LLM_BILLING=host`.
- **Stop the instance** when the trial is over (EC2 → *Instance state → Stop*), and
  terminate it plus the role when you're done.
- Tokens are never stored on the server; each browser keeps its own (cleared on
  sign-out or when the tab closes).
