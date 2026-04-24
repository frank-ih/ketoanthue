# Ketoanthue - AI Accountant for Vietnamese Businesses

Strategic product separate from AgentClan platform. Joins AgentClan Docker network for shared services.

## Architecture

```
ketoanthue/
├── agent/ketoanthue/    # AgentClan agent pipeline (YAML)
├── backend/ketoanthue-api/  # Lightweight Hono API
├── web/              # Next.js chat interface
├── landing/          # Marketing landing page
└── docker-compose.yml  # Production with AgentClan network
```

## Quick Start

```bash
# Development
cp .env.example .env
# Fill in AGENTCLAN_API_KEY and other values

docker-compose -f docker-compose.dev.yml up

# Production
docker-compose up -d
```

## Agent Registration

The `agent/ketoanthue/pipeline.yaml` registers the ketoanthue agent on AgentClan platform. Once deployed, the agent handles:
- Tax consultation (TNCN, TNDN, GTGT)
- Invoice processing
- Compliance checking

## Key Files

| File | Purpose |
|------|---------|
| `agent/ketoanthue/pipeline.yaml` | Agent pipeline definition |
| `agent/ketoanthue/prompts/system.txt` | Vietnamese accounting system prompt |
| `agent/ketoanthue/eval/golden_set.json` | 20 Q&A test cases |
| `web/src/lib/agentclan.ts` | AgentClan API client |
| `docker-compose.yml` | Production with AgentClan network join |