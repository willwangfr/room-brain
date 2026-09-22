# Room Brain · live demo script (about 2.5 minutes)

## Before you walk up (2 minutes, at your seat)

```bash
cd ~/Documents/personal-brain
open data/graph_anon.html            # tab 1: the room map, names hidden (drag a bubble once so it is "live")
open data/updates_anon.html          # tab 2: the diff table, names hidden
ROOM_BRAIN_PROVIDER=openai ROOM_BRAIN_MEMORY=plain ./run.sh agent.py --anon "Who do I know at tonight's hackathon, and who should I go meet?"
```

Leave that agent answer sitting in the terminal. It is your safety net if the live run is slow.
Font size up in the terminal. Close everything else. Everything on screen is anonymized
(`--anon` replaces names, links and employers in the printed answer); if you decide names are
fine in the room, drop `--anon` and open `graph.html` and `updates.html` instead.

## The script

**[Terminal in front, 0:00]**
"Everyone here has thousands of people in their phone and no idea who is in this room. I have
about fifty thousand across Instagram, LinkedIn, iMessage, WhatsApp, Gmail and event guest
lists, all exported, all in one graph on my laptop. Tonight I gave it a brain and an agent."

**[Type the question, hit enter, 0:15]**

```bash
ROOM_BRAIN_PROVIDER=openai ROOM_BRAIN_MEMORY=plain ./run.sh agent.py --anon "Who do I know at tonight's hackathon, and who should I go meet?"
```

"While it runs: this is a Strands agent with eight tools over my CRM. I pulled tonight's Luma
guest list, 291 people, into the graph an hour ago. It matches guests on real identifiers,
LinkedIn slug, Instagram handle, phone, email. A name match alone never counts."

**[Switch to the map tab while it thinks, 0:35]**
"This is the room. Me in the middle. Inner ring: 25 people I already know, edge color is how we
know each other, bubble size is how much we actually talk. Outer ring: 75 strangers who wrote a
bio." Drag one bubble. Hover one stranger. "Hover gives me the bio."

**[Back to the terminal, answer is in, 0:55]**
Read two lines out loud. "Sixty-five messages with Person 1, here is why to go say hi. And three strangers it picked from their bios. Every line comes from a tool
result. It cannot invent a name, and it cannot send anything. Its only write is a note back into
my CRM."

**[Diff table tab, 1:20]**
"Now the part nobody else does. The brain keeps every snapshot instead of overwriting. It
re-scrapes the Instagram bios of everyone I follow and diffs them, same for LinkedIn titles
across my exports. Red is before, green is after. 905 job changes and 159 bio changes came out
of data I already had, ranked by who I actually talk to. That is how you notice a friend changed
jobs without checking nine thousand profiles."

**[Terminal, 1:50]**

```bash
./run.sh -c "from brain.web import enrich_url; r=enrich_url('https://www.cosmorahealth.com/'); print(r['via'], r['status'], r['text'][:200])"
```

"Strangers get enriched from the public web through Bright Data's Web Unlocker. There is the
path: brightdata, ok. That is also how the bio re-scrape runs at scale."

**[Close, 2:10]**
"Stack: Strands is the agent and the memory manager. Cognee is the memory, my store implements
Strands' memory protocol over it, and the graph for tonight was built with cognee.remember.
Bright Data is the web. All of it runs on my laptop over my own exports. Repo is public:
github.com/willwangfr/room-brain. Thanks."

## If something breaks

- Agent slow or errors: switch to the terminal tab where the pre-run answer is sitting and read
  from it. Say "here is the run from two minutes ago."
- Map does not load: `open data/graph_anon.html` again; it needs internet for d3. If no internet, the
  README screenshots are the fallback: github.com/willwangfr/room-brain.
- Bright Data errors: `via: direct` still prints; say the zone was created an hour ago and show
  the README line. Do not fight it on stage.

## 30-second version (if they cut time)

"Fifty thousand people from my own exports, one graph. The agent tells me who in this room I
already know, 25 tonight, and notices when the people I follow change their bio or job, 905 job
changes and 159 bio changes so far. Strands agent, Cognee memory, Bright Data for the web. It
drafts, never sends. github.com/willwangfr/room-brain."

## Questions they will ask

- **Is scraping Instagram allowed?** "Public profile pages of accounts already in my own export,
  at a slow rate, and Bright Data is the sponsor-supported way to do it. Terms are on the user."
- **Isn't this just a CRM?** "A CRM stores what you typed. This diffs what the world changed."
- **Does anyone else do this?** "Per-account bio trackers exist, and Dex does LinkedIn job
  alerts. I did not find anything that re-scrapes a whole following list over time and fuses
  it with your LinkedIn and messages. I searched before claiming that."
- **What is Cognee doing exactly?** "It is the memory store behind Strands' memory manager. The
  graph for tonight was built with cognee.remember; the demo answers from the keyword fallback so
  nothing waits on a graph build on stage."
- **Privacy?** "Everything is local. Nothing leaves the laptop unless I turn on Cognee Cloud, and
  the agent cannot send messages."
