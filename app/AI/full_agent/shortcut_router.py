import re

from google.adk import Event
from google.adk.workflow import node

from app.AI.full_agent.search_agent.schema import Validation
from app.AI.full_agent.triage_agent.schema import QueryClassifier
from app.AI.schema import TargetType
from app.database.db import get_db_gen
from app.poi.models import POI

ROOM_RE = re.compile(r"\broom\s+([A-Z]?\d{3,4})\b", re.IGNORECASE)


def room_lookup(room: str) -> list[dict]:
    with get_db_gen() as db:
        db.load_collection("poi")
        return db.query(
            collection_name="poi", filter=f'name like "%{room}%"', limit=9
        )


@node(name="shortcut_router", rerun_on_resume=True)
def room_shortcut(node_input: QueryClassifier):
    rooms = ROOM_RE.findall(node_input.semantics)
    if node_input.target_type != TargetType.EXPLICIT or len(rooms) != 1:
        return Event(route="llm", output=node_input)

    hits = room_lookup(rooms[0])
    # Several rooms share the number, so let the search pick
    if len(hits) > 1:
        return Event(route="llm", output=node_input)

    # No hits means the room doesn't exist; actions_agent turns that into a clarify
    return Event(
        route="shortcut",
        output=Validation(
            order=node_input.order,
            selected_pois=[POI(**hit) for hit in hits],
        ),
    )
