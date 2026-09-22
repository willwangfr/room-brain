"""Print recent life updates as a table: what changed for the people I know.

    ./run.sh show_updates.py            # job + bio changes, top 15
    ./run.sh show_updates.py bio 20     # Instagram bio changes only
    ./run.sh show_updates.py job 20     # LinkedIn job/title changes only
"""
import sys

from rich.console import Console
from rich.table import Table

from brain.updates import life_updates

kind = sys.argv[1] if len(sys.argv) > 1 else "all"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 15

table = Table(title=f"Life updates · {kind} · ranked by how much we actually talk")
for col, width in (("Who", 20), ("Kind", 5), ("Before", 34), ("After", 34), ("Seen", 24), ("How I know them", 22), ("Msgs", 5)):
    table.add_column(col, overflow="fold", max_width=width)
for u in life_updates(kind=kind, limit=limit):
    table.add_row(u["name"] or "?", u["kind"], (u["before"] or "")[:90], (u["after"] or "")[:90],
                  f"{u['observed'][0]} to {u['observed'][1]}", ", ".join(u["how_we_know"]), str(u["n_messages"]))
Console().print(table)
