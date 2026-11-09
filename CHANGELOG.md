# Changelog

All notable changes to Abode AI Tools are recorded here. Release notes are
also published on the [GitHub releases page](https://github.com/meremortals70/abode-ai-tools/releases).

## 0.6.1

- `call_service` has a 15-second timeout, so a blocked service cannot hang the
  voice turn. Failures return a bounded reason instead of only “failed”.
- Search matches entity aliases as well as names and `entity_id`s, and reports
  an explicit error for a domain that is not searchable.
- Area matching uses word boundaries: “den” no longer matches “Garden” and
  “room” no longer matches “Bedroom”.
- Reconfiguring the Paperless endpoint keeps the existing token when the token
  field is left blank. Clearing the URL clears the token.
- Paperless has a 60-second fail-fast breaker after a connection-level failure,
  so a down server does not cost 20 seconds on every document turn.
- `call_service` is annotated destructive because it can unlock locks or open
  covers; MCP clients may use that to require approval.
- Test coverage is 75 dependency-free tests covering the tools, Paperless RPC
  parsing, config-flow merge logic, policy and bounds.
- CI runs the tests, hassfest and Marketplace validation.
- Installation and release docs use **Settings → Marketplace** on Home
  Assistant 2026.11 and newer. The repository keeps `hacs.json` because the
  Marketplace reads it, and the manifest declares the
  `ai_voice.voice_assistants` category.
- Refreshed stale docstrings and internal references.

## 0.6.0

- Exposure follows `LLMContext.assistant`, so an AI Task or another assistant
  sees its own exposure set instead of the conversation assistant's.
- `call_service` uses an explicit `(domain, service)` allowlist. It blocks
  `homeassistant.reload_config_entry`, `homeassistant.save_persistent_states`
  and other services outside the intended surface. The target entity's domain
  must be controllable, and a non-`homeassistant` service must match that
  domain.
- Result strings, attribute values, document metadata, tags and custom fields
  are length-capped. `get_entity_state` returns a per-domain safe attribute
  set, so GPS coordinates, calendar descriptions and large lists such as
  weather forecasts or media source lists are no longer returned.
- Paperless responses have a byte cap, are type-checked before use, no longer
  follow redirects, and the configured URL is redacted from logs.
- The system prompt tells the model that tool results, entity names and
  document text are untrusted data, and treats `cover`, `lock` and `valve` as
  sensitive domains.
- Added dependency-free unit tests for the policy allowlists and bounding
  helpers.

## 0.5.1

- Removed the legacy `custom_components/abode_tools/` integration (v0.2.0).
  The repository contains exactly one integration, `abode_ai_tools`.
- Corrected the manifest documentation and issue-tracker links.
- Added a `.gitignore` for Python cache files.

## 0.5.0

- Every LLM tool declares `integration = "abode_ai_tools"`, clearing Home
  Assistant's “provides the LLM tool ... without an integration” warning.
  Home Assistant stops accepting untagged tools in 2027.10.
- Every tool returns `llm.ToolResult` instead of a plain JSON object, with
  `error=True` on failures. The plain-dict form stops working in 2027.11.
- Tools carry a human-readable `title` and `ToolAnnotations`, so Home Assistant
  and MCP clients can tell read-only tools from the one that acts.
- No change to tool names, schemas, results or the Paperless endpoint format.

## Earlier releases

See the [GitHub releases page](https://github.com/meremortals70/abode-ai-tools/releases)
for 0.4.0 and earlier.
