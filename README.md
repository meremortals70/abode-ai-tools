# Abode AI Tools
v0.3.1

Gives your voice assistant a small, fixed set of things it can do in the
house — and nothing else.

## What it does

- **Find things** — "which lights are on upstairs" — searches your devices by
  name, room or type, and returns up to 20 matches with their room and
  current state.
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

## Credits

Designed and directed by Jason Wienert (Mere Mortals Consulting).
Implementation, research and code written in collaboration with
Claude (Anthropic).
