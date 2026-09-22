# Room Brain · final submission

*Battle of the Personal Brains · Bright Data office, San Francisco · September 21, 2026*

| Field | |
|---|---|
| **Name** | Room Brain |
| **Team** | William Wang (USC MD student; CSO, Cosmora Health) |
| **GitHub** | https://github.com/willwangfr/room-brain |
| **Strands / Cognee / Bright Data** | All three, see below |
| **Screenshots** | `docs/room.png`, `docs/updates.png`, `docs/agent.png` (names, links and employers hidden in all three) |

## Description (paste into the form)

Room Brain is a personal AI agent over my own exports: Instagram, LinkedIn, iMessage, WhatsApp,
Gmail, Google Calendar, Contacts, Luma and Partiful, fused into one identity graph of 50,135
people and about 173,000 evidence records. Its brain keeps every snapshot instead of
overwriting, so it notices change: it re-scrapes the public bios of everyone I follow on
Instagram and diffs them over time (159 bio changes and 905 LinkedIn job or title changes found
in my own snapshots), ranked by how much I actually talk to each person. Tonight it resolved
this hackathon's Luma guest list against that graph: 25 people I already know and 75 strangers
with bios worth meeting, drawn as a live map of the room. Built on Strands Agents (the agent),
Cognee (the memory) and Bright Data (the web). It drafts outreach and writes notes back into my
CRM; it never sends anything.

## How each sponsor technology is used

### AWS Strands Agents: the agent harness

- `agent.py` builds `Agent(model=..., tools=[...8 tools...], system_prompt=..., memory_manager=MemoryManager(stores=[RoomBrainMemory()], search_tool_config=True, add_tool_config=True))`.
- The eight `@tool` functions are thin wrappers over the brain: `list_events`, `who_do_i_know_at`,
  `strangers_at`, `find_person`, `dossier`, `life_updates`, `enrich_url`, `remember_note`.
- Strands' `MemoryManager` injects Cognee recall into every turn and gives the model
  `memory_search` and `memory_add` tools, so what the agent learns tonight is remembered.
- Strands model providers are swapped at runtime: `AnthropicModel`, `OpenAIModel` (OpenAI direct
  or OpenRouter via `base_url`) and `OllamaModel` for a fully local run. Hosted credits ran out
  mid-event; the demo you see ran on `gpt-5-mini` through Strands' OpenAI provider.

### Cognee: the brain's memory

- `brain/memory.py` defines `RoomBrainMemory`, an implementation of Strands' `MemoryStore`
  protocol (`name`, `description`, `search`, `add`) whose backend is Cognee.
- Local graph: `cognee.remember(lines, dataset_name="room_brain")` built the graph tonight from
  99 fact lines: 25 known guests (how we know each other, employer, message count, last contact),
  53 stranger bios, and 20 recent job or bio changes. `cognee.recall(query, datasets=["room_brain"])`
  serves search.
- Cognee Cloud: a REST client for the tenant's `/api/v1/add_text`, `/api/v1/cognify` and
  `/api/v1/search` endpoints with `X-Api-Key` and `X-Tenant-Id`, selected by setting
  `COGNEE_API_KEY`.
- A plain keyword fallback is the third backend, so a demo never waits on a graph that is still
  building. `ROOM_BRAIN_MEMORY=cloud|local|plain` picks explicitly.

### Bright Data: the web

- `brain/web.py` `enrich_url()` posts to the Web Unlocker API (`https://api.brightdata.com/request`,
  zone, `format: raw`), strips the HTML, and returns the page title, `og:description` and text.
  `public_profile_summary()` picks a stranger's first non-Instagram link and enriches it.
- The agent's `enrich_url` tool uses it to learn about strangers on the guest list before
  recommending whom to meet. A Web Unlocker zone (`web_unlocker1`) is live on the account and
  fetches return `via: brightdata`; a direct fetch remains as the fallback if the zone or key is
  missing, and every result reports which path it took.
- Bright Data is also the intended path for the bio re-scrape at scale, replacing my own
  slow scraper for the 9,243 accounts in my export.

Docker sandboxes were not used.

## Judging criteria

**Technical execution (25%).** It ran end to end tonight on the judges' own guest list: Luma
import, identity resolution on strong identifiers only (a display-name match never counts), a
Strands agent with eight tools, memory through Cognee, web enrichment through Bright Data, and a
model fallback chain that survived two credit outages.

**Use of the brain (25%).** The brain is not a folder of documents. It is 50,135 people from
eight exports, fused with a five-layer model (immutable evidence, identities, people, derived,
notes) and with time: snapshots accumulate, and the agent reasons over diffs. Every answer is
ranked by relationship strength, measured as messages exchanged and independent sources.

**Agentic capability (25%).** The agent chooses tools, reads results, ranks the room, picks
strangers by bio, enriches them from the web, drafts a message, and writes a note back into the
CRM's human-judgment layer. It never sends, never invents a name or date, and reports missing
fields as missing.

**Creativity (15%).** Per-account Instagram bio trackers and bulk follower exporters exist, and
Dex sells LinkedIn job-change alerts. We did not find one memory that re-scrapes an entire
following list over time, diffs it, and fuses the changes with LinkedIn and message history so
they are ranked by real relationships. The room map is drawn from the judges' own guest list.

**Real-world value (10%).** I already run this CRM. Anyone who goes to events wants "who do I
know here"; anyone with a network wants "who changed jobs or moved" without checking 9,000
profiles. It runs on a laptop over the person's own exports.

## Measured tonight

| | |
|---|---|
| people in the identity graph | 50,135 |
| Instagram accounts with a scraped bio | 9,243 |
| re-scraped at least once so far | 425 |
| Instagram bio changes detected | 159 |
| LinkedIn job or title changes detected | 905 |
| registered for tonight | 291 |
| already known to me | 25 |
| strangers who wrote a bio | 75 |

## Screenshots

- `docs/room.png`: the room map. Me in the center, people I know on the inner ring (edge color is
  how we know each other, bubble size is message volume, pink ring is a recent job or bio
  change), strangers with bios on the outer ring. Draggable, hover for details.
- `docs/updates.png`: life updates with word-level before/after diffs, anonymized for sharing.
- `docs/agent.png`: the agent answering "Who do I know at tonight's hackathon, and who should I
  go meet?"

## Run it

```bash
uv venv .venv && uv pip install --python .venv/bin/python "strands-agents[anthropic]" openai ollama cognee requests rich -e ../personal-crm
cp .env.example .env
./run.sh -m brain.memory ingest
./run.sh -m brain.graph && ./run.sh -m brain.report all 40
./run.sh agent.py "Who do I know at tonight's hackathon, and who should I go meet?"
```
