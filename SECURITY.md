# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub Security Advisories:

<https://github.com/meremortals70/abode-ai-tools/security/advisories/new>

Do not open a public issue for a vulnerability. Include the version, the
Home Assistant version, what an attacker can do, and the smallest reproduction
you can share.

## Security model

Abode AI Tools is a bridge between a conversation agent and your Home
Assistant instance. Treat the conversation agent, its model, and any Paperless
content as part of the attack surface.

- **Exposure is the boundary.** Only entities exposed to the assistant making
  the request are visible or controllable. Review
  **Settings → Voice assistants → Expose** after adding devices. Home Assistant
  may expose new entities in common domains automatically.
- **Service calls are allowlisted.** `call_service` only accepts an explicit
  set of entity services and a target in a controllable domain. It cannot call
  automations, backups, the recorder, or arbitrary admin services.
- **Sensitive domains need an explicit request.** `cover`, `lock` and `valve`
  are treated as sensitive in the system prompt. This is guidance, not a hard
  guarantee; do not expose a domain you do not want controlled by voice.
- **Paperless is read-only.** Only `query_documents`, `get_document` and
  `get_document_content` are proxied. Use a view-only Paperless token and
  restrict the MCP endpoint.
- **Documents are untrusted.** Paperless text, entity names and tool results can
  contain instructions. The prompt tells the model to treat them as data and
  never follow instructions inside them. Keep sensitive actions out of reach if
  that matters.
- **Transport.** Use HTTPS when a Paperless token is configured. A plain HTTP
  endpoint sends the bearer token unencrypted; the integration logs a warning
  when it detects this.
- **Cloud providers.** If you select a cloud conversation agent, entity names,
  states, attributes and Paperless text are sent to that provider.

## Supported versions

Security fixes are published for the latest release. Upgrade through
**Settings → Marketplace** on Home Assistant 2026.11 and newer, or HACS on
2026.10.
