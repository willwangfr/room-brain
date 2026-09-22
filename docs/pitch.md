# Room Brain · pitch against the judging criteria

**One line.** A personal brain that re-scrapes the Instagram bios of everyone I follow, notices
when the people I know change, and tells me who in this room I already know.

## Technical execution (25%)

It ran end to end tonight. The hackathon's own Luma guest list (291 registered) was imported
into my CRM, every guest resolved against an identity graph on strong identifiers only, and a
Strands agent with eight tools answered "who do I know here" with links and drafted outreach.
Integrations: Strands for the agent loop, tools and memory manager; Cognee as the memory store
behind Strands' `MemoryStore` protocol, with the local graph built from tonight's facts and a
Cognee Cloud REST client ready; Bright Data Web Unlocker as the enrichment path for strangers.
Hosted model credits ran out mid-event, so the agent selects Anthropic, OpenRouter, OpenAI or a
local Ollama model from whatever keys exist, and the demo still ran.

## Use of the brain (25%)

The brain is not a folder of documents. It is 50,135 people and about 173,000 evidence records
fused from eight exports (Instagram, LinkedIn, iMessage, WhatsApp, Gmail, Calendar, Contacts,
Luma and Partiful) into one identity graph with time: raw evidence is immutable, snapshots
accumulate, and the agent reasons over diffs (905 job or title changes, 159 bio changes in my
own snapshots). Every answer is ranked by relationship strength, measured as messages
exchanged and the number of independent sources that know a person.

## Agentic capability (25%)

The agent decides which tools to call, reads their results, and acts: it ranks the room,
picks strangers worth meeting from their bios, enriches them from the public web, drafts a
message, and writes a note back into the CRM's human-judgment layer so the brain remembers
what I decided. It never sends anything, never invents a name or a date, and reports missing
fields as missing.

## Creativity (15%)

Per-account Instagram bio trackers and bulk follower exporters exist, and Dex sells LinkedIn
job-change alerts. What we did not find is one memory that re-scrapes an entire following list
over time, diffs it, and fuses the changes with LinkedIn and message history so they are ranked
by real relationships. The room map uses the judges' own guest list.

## Real-world value (10%)

I already run this CRM. Anyone who goes to events wants "who do I know here"; anyone with a
network wants "who changed jobs or moved" without checking 9,000 profiles. It runs on a laptop
over the person's own exports; nothing leaves the machine unless Cognee Cloud is switched on.
