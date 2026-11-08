# Abode AI Tools
v0.5.1

Requires Home Assistant 2026.10 or newer. Since v0.5.0 every LLM tool
returns `llm.ToolResult` and declares the integration that provides it, the
two changes Home Assistant 2026.10 introduced and will enforce in
2027.10/2027.11. See the changes below.

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
  a handful of its details.
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
- It cannot edit your automations, run backups, delete history, or reach
  anything else in Home Assistant. Those doors are closed in the code, not by
  asking the AI nicely.
- It only ever sees devices you have chosen to expose to the assistant.
- Every answer is capped in size, so the assistant stays fast and never
  floods itself with data.
- One device per action, and it must use an exact device it has just looked
  up — it cannot guess.

## A note for the household

New devices are **not** exposed to the assistant automatically. When you add
something and the assistant says it does not exist, expose it under
Settings -> Voice assistants -> Expose, and give it a name someone would
actually say out loud.

Expose only what is needed. If a room has four temperature sensors, expose
one — otherwise the assistant has to guess which one you meant.

## Setup

Configured through the UI: Settings -> Devices & Services -> Add Integration
-> Abode AI Tools. Both fields are optional; an empty form gives the four
device-control tools and no network calls.

After adding, tick **Abode AI Tools** under the conversation agent's Tool
Providers.

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
Claude (Anthropic).
