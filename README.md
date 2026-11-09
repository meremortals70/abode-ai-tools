# Abode AI Tools
v0.6.1

![Abode AI Tools](custom_components/abode_ai_tools/brand/icon.png)

Requires Home Assistant 2026.10 or newer. On Home Assistant 2026.11 and newer,
install and update it through **Settings -> Marketplace**; HACS is only used on
2026.10 and older. Since v0.5.0 every LLM tool returns `llm.ToolResult` and
declares the integration that provides it, the two changes Home Assistant
2026.10 introduced and will enforce in 2027.10/2027.11. See the changes below.

Gives your voice assistant a small, fixed set of things it can do in the
house — and nothing else.

## What it does

- **Find things** — "which lights are on in the lounge" — searches your
  devices by name, room, type or whether they are on or off, and returns the
  names, up to 20 at a time. If there are more than 20 it says so and gives
  the real total, rather than quietly stopping at 20.
- **Understands room names** — "lounge" and "lounge room" both find the same
  room, and any nicknames you have set for a room work too. If it does not
  recognise a room name, it says which rooms it does know about instead of
  guessing.
- **Check one thing** — "is the garage door shut" — reads a single device and
  a small, safe set of its details.
- **Do one thing** — "turn the deck light on" — acts on a single device.
- **Tell the time** — the assistant only checks the clock when you actually
  ask about the date, day or time.

Optionally, if a Paperless endpoint is configured, it can also look things up
in your household documents.

## Why it's deliberately limited

- It can only touch everyday household things: lights, switches, fans,
  blinds, heating and cooling, speakers, locks, the vacuum, scenes, scripts,
  humidifiers, hot water, valves, toggles and buttons. It can read sensors,
  presence, weather, the calendar and sunrise/sunset.
- It can only call a fixed allowlist of entity services. It has no direct
  access to automations, backups, history or the recorder. Exposed scripts and
  scenes can still do whatever those scripts and scenes do — exposing one
  grants that power.
- It only sees entities exposed to the active assistant. Home Assistant may
  expose new entities in common domains by default, so review the exposure
  list rather than assuming a new device is private.
- Counts, string lengths and attribute values are capped, and document text is
  truncated, so the assistant stays fast and never floods itself with data.
- One device per action. The prompt asks it to use an `entity_id` it found
  with `search_entities`; the code cannot prove that it did.

## Security model

- **Exposure is the boundary.** Only entities exposed to the assistant making
  the request are visible or controllable. Check
  Settings -> Voice assistants -> Expose after adding devices. Locks, covers,
  valves, scenes and scripts deserve particular care: a cover may be a garage
  door, and a scene or script can contain any action you put in it.
- **Sensitive domains.** `cover`, `lock` and `valve` are treated as sensitive
  in the system prompt: the model is told not to act on them, or run a script,
  unless the request explicitly asked for it. That is guidance, not a hard
  guarantee. If you do not want voice control of a domain, remove it from
  `CONTROLLABLE_DOMAINS` and `ALLOWED_SERVICES` in `policy.py`.
- **Paperless is read-only.** The integration exposes only `query_documents`,
  `get_document` and `get_document_content`. Issue the Paperless token to a
  view-only user and restrict the MCP endpoint; the component cannot protect an
  endpoint that is open to other clients. Use HTTPS when a token is configured.
- **Document text is untrusted.** Paperless content, entity names and tool
  results can contain instructions. The system prompt tells the model to treat
  them as data and never follow instructions inside them. The model is still
  the last line of defence, so keep sensitive actions out of reach if that
  matters.
- **Cloud providers.** This component is provider-agnostic. If you select a
  cloud conversation agent, entity names, states, attributes and Paperless
  text are sent to that provider.

## A note for the household

Home Assistant may expose new entities in common domains (lights, covers,
scenes and similar) automatically. When you add something and the assistant
says it does not exist, expose it under
Settings -> Voice assistants -> Expose, and give it a name someone would
actually say out loud. Check that new covers, locks and scenes are exposed only
if you want the assistant to control them.

Expose only what is needed. If a room has four temperature sensors, expose
one — otherwise the assistant has to guess which one you meant.

## Install

Home Assistant 2026.11 and newer ships the Marketplace, the built-in successor
to HACS. Install from **Settings -> Marketplace**:

- Search for **Abode AI Tools** in the catalog.
- If it is not listed, select **Add from link**, enter
  `https://github.com/meremortals70/abode-ai-tools`, and install it. Custom
  repositories need a GitHub connection; the Marketplace walks you through the
  device sign-in.
- Updates appear under **Settings -> Updates**. Restart Home Assistant after
  updating an integration.

HACS cannot be installed on Home Assistant 2026.11 or newer. On Home Assistant
2026.10, use HACS with this repository as a custom integration repository. The
repository keeps `hacs.json` because the Marketplace reads the same file.

## Setup

Configured through the UI: Settings -> Devices & Services -> Add Integration
-> Abode AI Tools. Both fields are optional; an empty form gives the four
device-control tools and no network calls.

[![Open your Home Assistant instance and start setting up Abode AI Tools.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=abode_ai_tools)

After adding, tick **Abode AI Tools** under the conversation agent's Tool
Providers.

## Changes in v0.6.1

- `call_service` now has a 15-second timeout, so a blocked service cannot hang
  the voice turn. Failures return a bounded reason instead of only “failed”.
- Search now matches entity aliases as well as names and `entity_id`s, and
  reports an explicit error for a domain that is not searchable.
- Area matching uses word boundaries: “den” no longer matches “Garden” and
  “room” no longer matches “Bedroom”.
- Reconfiguring the Paperless endpoint keeps the existing token when the token
  field is left blank. Clearing the URL clears the token.
- Paperless has a 60-second fail-fast breaker after a connection-level failure,
  so a down server does not cost 20 seconds on every document turn.
- `call_service` is now annotated as destructive because it can unlock locks
  or open covers; MCP clients may use that to require approval.
- Test coverage expanded to 74 dependency-free tests covering the tools,
  Paperless RPC parsing, config-flow merge logic, policy and bounds. CI now
  runs those tests, hassfest and Marketplace validation (the HACS action).
- Installation and release docs now use **Settings -> Marketplace** on Home
  Assistant 2026.11 and newer. The repository keeps `hacs.json` because the
  Marketplace reads it, and the manifest now declares the
  `ai_voice.voice_assistants` category.
- Refreshed stale docstrings and internal references.

## Changes in v0.6.0

- Exposure now follows `LLMContext.assistant`, so an AI Task or another
  assistant sees its own exposure set instead of the conversation assistant's.
- `call_service` now uses an explicit `(domain, service)` allowlist. It blocks
  `homeassistant.reload_config_entry`, `homeassistant.save_persistent_states`
  and other services outside the intended surface. The target entity's domain
  must be controllable, and a non-`homeassistant` service must match that
  domain.
- Result strings, attribute values, document metadata, tags and custom fields
  are now length-capped. `get_entity_state` returns a per-domain safe attribute
  set, so GPS coordinates, calendar descriptions and large lists such as
  weather forecasts or media source lists are no longer returned.
- Paperless responses have a byte cap, are type-checked before use, no longer
  follow redirects, and the configured URL is redacted from logs.
- The system prompt now tells the model that tool results, entity names and
  document text are untrusted data, and treats `cover`, `lock` and `valve` as
  sensitive domains.
- Added dependency-free unit tests for the policy allowlists and the bounding
  helpers.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Changes in v0.5.1

- Removed the legacy `custom_components/abode_tools/` integration (v0.2.0).
  The repository now contains exactly one integration, `abode_ai_tools`.
  If that folder still exists on your Home Assistant instance, delete it and
  remove any `abode_tools:` line from `configuration.yaml`.
- Corrected the manifest documentation and issue-tracker links.

## Changes in v0.5.0

- Every LLM tool now declares `integration = "abode_ai_tools"`, clearing
  Home Assistant's "provides the LLM tool ... without an integration" warning.
  Home Assistant stops accepting untagged tools in 2027.10.
- Every tool now returns `llm.ToolResult` instead of a plain JSON object, with
  `error=True` on failures. The plain-dict form stops working in 2027.11.
- Tools now carry a human-readable `title` and `ToolAnnotations`, so Home
  Assistant and MCP clients can tell read-only tools from the one that acts.
- No change to tool names, schemas, results or the Paperless endpoint format.

## Credits

Designed and directed by Jason Wienert (Mere Mortals Consulting).
Implementation, research and code written in collaboration with
OpenCode.
