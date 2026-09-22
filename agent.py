"""Room Brain: a Strands agent over William's personal CRM, with Cognee memory.

Tools wrap brain/crm_tools.py (his own exports in local sqlite), brain/updates.py
(diffs between snapshots he already holds) and brain/web.py (Bright Data Web
Unlocker when a zone exists, plain fetch otherwise). The agent never sends
anything: outward messages are drafts, and its only write is a note into the
CRM's human-judgment layer.
"""
import json
import os
import sys

from strands import Agent, tool
from strands.memory import MemoryManager
from strands.models.anthropic import AnthropicModel

from brain import crm_tools as ct
from brain import updates as up
from brain import web
from brain.memory import RoomBrainMemory
from brain.updates import self_person_ids

TONIGHT = os.environ.get("ROOM_BRAIN_EVENT", "evt-sBdX3tSZl05miG7")
SELF_IDS = set(self_person_ids())  # William is on his own guest lists; never list him as someone he knows


def _j(x):
    return json.dumps(x, default=str)[:14000]


@tool
def list_events() -> str:
    """Luma events whose guest lists are in the CRM: event_api_id, imported_at, n_guests."""
    return _j(ct.list_events())


@tool
def who_do_i_know_at(event_api_id: str = TONIGHT) -> str:
    """People at a Luma event whom William already knows from another source (messages, LinkedIn, Instagram, contacts), most-messaged first. Default event: tonight's hackathon."""
    return _j([p for p in ct.who_do_i_know_at(event_api_id) if p.get("person_id") not in SELF_IDS])


@tool
def strangers_at(event_api_id: str = TONIGHT, limit: int = 40) -> str:
    """Guests at a Luma event William has no prior evidence of, with public bios and links, for deciding whom to meet."""
    return _j(ct.strangers_at(event_api_id, limit=limit))


@tool
def find_person(query: str, limit: int = 10) -> str:
    """Search William's CRM by name, employer, title or handle."""
    return _j(ct.find_person(query, limit=limit))


@tool
def dossier(person_id: int) -> str:
    """Everything the CRM holds on one person: identities, links, message stats, shared events, notes."""
    return _j(ct.dossier(person_id))


@tool
def life_updates(kind: str = "all", limit: int = 25) -> str:
    """Job/title changes (LinkedIn export diffs) and Instagram bio changes for people William knows. kind: all, job or bio."""
    return _j(up.life_updates(kind=kind, limit=limit))


@tool
def enrich_url(url: str) -> str:
    """Fetch a public web page (Bright Data Web Unlocker when configured, otherwise direct) and return its cleaned text."""
    return _j(web.enrich_url(url))


@tool
def remember_note(person_id: int, field: str, value: str) -> str:
    """Save William's own note about a person into the CRM (field: how_we_met, likes, goals, freeform, ...). The only write this agent can make."""
    return _j(ct.remember_note(person_id, field, value))


SYSTEM = """You are Room Brain, William Wang's personal brain for people. William is a USC MD student and CSO of Cosmora Health (retinal AI), splitting time between LA and the Bay Area; he cares about emotion AI, computational psychiatry, longevity, and tools built over his own data.
Ground every claim in a tool result. Never invent names, employers, counts or dates; if a field is missing say so. When you name a person, include the profile link the tool returned. Rank people William has actually messaged above weak matches.
You never send messages. When asked to reach out, write the draft and, if useful, save a note with remember_note.
Answer tightly: a list of people, one line each, with how he knows them and why they matter right now."""


def make_model(model_id=None):
    """ROOM_BRAIN_PROVIDER=anthropic|openai|openrouter|ollama; auto picks the first key present."""
    provider = os.environ.get("ROOM_BRAIN_PROVIDER") or (
        "anthropic" if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("ROOM_BRAIN_PREFER_ANTHROPIC")
        else "openrouter" if os.environ.get("OPENROUTER_API_KEY")
        else "openai" if os.environ.get("OPENAI_API_KEY") else "anthropic")
    mid = model_id or os.environ.get("ROOM_BRAIN_MODEL")
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY") or sys.exit("no model key found: run via ./run.sh")
        return AnthropicModel(client_args={"api_key": key}, model_id=mid or "claude-sonnet-5", max_tokens=2500)
    from strands.models.openai import OpenAIModel
    if provider == "openrouter":
        return OpenAIModel(client_args={"api_key": os.environ["OPENROUTER_API_KEY"],
                                        "base_url": "https://openrouter.ai/api/v1"},
                           model_id=mid or "anthropic/claude-sonnet-5", params={"max_tokens": 2500})
    if provider == "ollama":  # fully local: no key, data never leaves the laptop
        from strands.models.ollama import OllamaModel
        return OllamaModel(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
                           model_id=mid or "qwen2.5:7b-instruct", max_tokens=1500, temperature=0.2)
    # gpt-5 family rejects max_tokens, and its reasoning tokens count against the
    # completion cap, so the cap must be generous and reasoning kept short.
    return OpenAIModel(client_args={"api_key": os.environ["OPENAI_API_KEY"]},
                       model_id=mid or "gpt-5-mini",
                       params={"max_completion_tokens": 12000, "reasoning_effort": "low"})


def build(model_id=None):
    model = make_model(model_id)
    memory = MemoryManager(stores=[RoomBrainMemory()], search_tool_config=True, add_tool_config=True)
    return Agent(model=model, system_prompt=SYSTEM, memory_manager=memory, callback_handler=None,
                 tools=[list_events, who_do_i_know_at, strangers_at, find_person, dossier,
                        life_updates, enrich_url, remember_note])


if __name__ == "__main__":
    anon = "--anon" in sys.argv  # hide names, links and employers in what gets printed
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    question = " ".join(args) or "Who do I know at tonight's hackathon, and who should I go meet?"
    agent = build()
    text = str(agent(question))
    if anon:
        from brain.answer_page import anonymize
        text = anonymize(text)
    print(text)
