#!/usr/bin/env python3
"""Madrid Trip Planner - Single-port server (HTTP + WebSocket on same port)."""

import asyncio
import json
import os
import mimetypes
import secrets
from datetime import datetime

try:
    import websockets
    from websockets.asyncio.server import serve
    from websockets.http11 import Response
    from websockets.datastructures import Headers
except ImportError:
    print("Installing websockets...")
    import subprocess
    subprocess.check_call(["pip3", "install", "websockets"])
    import websockets
    from websockets.asyncio.server import serve
    from websockets.http11 import Response
    from websockets.datastructures import Headers

# Optional PostgreSQL support for persistent storage
DATABASE_URL = os.environ.get("DATABASE_URL")
pg_conn = None

if DATABASE_URL:
    try:
        import psycopg2
    except ImportError:
        import subprocess
        subprocess.check_call(["pip3", "install", "psycopg2-binary"])
        import psycopg2

# ---------- Config ----------
PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "data.json")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

DEFAULT_STATE = {"trips": {}}

state = None
# Maps each connected websocket to the trip_id it's currently viewing.
client_trips = {}


# ---------- Trip-code generation ----------
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I to avoid confusion
SLUG_SUFFIX_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

COLOR_PALETTE = [
    "#C4613A", "#3A8F85", "#C69C4E", "#6B5BAD",
    "#D08B4A", "#4A90A4", "#8B5A8C", "#5C8A47",
    "#B85C7A", "#5673A8", "#C2965A", "#7A6B47",
]

VALID_LANGUAGES = {"nl", "en", "es"}
VALID_VOTING_RULES = {"unanimous", "majority"}
MAX_TRIP_DAYS = 14
MIN_PARTICIPANTS = 2
MAX_PARTICIPANTS = 12


def generate_trip_code():
    chars = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{chars[:4]}-{chars[4:]}"


def slugify(name):
    out = []
    prev_dash = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            prev_dash = False
        elif not prev_dash:
            out.append("-")
            prev_dash = True
    slug = "".join(out).strip("-")
    return slug or "trip"


def generate_unique_slug(name):
    base = slugify(name)[:40]
    for _ in range(20):
        suffix = "".join(secrets.choice(SLUG_SUFFIX_ALPHABET) for _ in range(4))
        candidate = f"{base}-{suffix}"
        if candidate not in state["trips"]:
            return candidate
    raise RuntimeError("could not allocate unique slug")


# ---------- Migration ----------
MADRID_TRIP_ID = "madrid-2026"
MADRID_PARTICIPANTS = [
    {"name": "Edje",     "color": "#C4613A", "language": "es"},
    {"name": "Maxime",   "color": "#3A8F85"},
    {"name": "El Sierd", "color": "#C69C4E"},
    {"name": "Miqi",     "color": "#6B5BAD"},
    {"name": "Koen",     "color": "#D08B4A"},
    {"name": "Bart",     "color": "#4A90A4"},
]
MADRID_DAYS = ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]


def migrate_if_needed(loaded):
    """Wrap legacy single-trip data into the new multi-trip schema."""
    if isinstance(loaded, dict) and "trips" in loaded:
        return loaded, False

    days = loaded.get("days") or {
        d: {"proposals": [], "agenda": [], "notes": {}} for d in MADRID_DAYS
    }
    trip = {
        "id": MADRID_TRIP_ID,
        "name": "Madrid 2026",
        "flag": "\U0001F1EA\U0001F1F8",
        "code": generate_trip_code(),
        "owner": "Miqi",
        "start_date": "2026-04-01",
        "end_date": "2026-04-04",
        "language": "nl",
        "voting_rule": "unanimous",
        "hotel": None,
        "participants": MADRID_PARTICIPANTS,
        "suggestions": loaded.get("suggestions", []),
        "days": days,
        "geocache": loaded.get("geocache", {}),
        "next_id": loaded.get("next_id", 1),
        "created": "2026-02-27T23:55:00",
    }
    print(f"[migration] Wrapped legacy data into trip '{MADRID_TRIP_ID}', code: {trip['code']}")
    return {"trips": {MADRID_TRIP_ID: trip}}, True


def normalize_trip(trip):
    """Ensure a trip has all expected sub-structures."""
    trip.setdefault("geocache", {})
    trip.setdefault("days", {})
    for day in trip["days"].values():
        day.setdefault("proposals", [])
        day.setdefault("agenda", [])
        day.setdefault("notes", {})


# ---------- State Management ----------
def init_db():
    global pg_conn
    if not DATABASE_URL:
        return
    try:
        pg_conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
        pg_conn.autocommit = True
        with pg_conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_state (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    data JSONB NOT NULL,
                    CHECK (id = 1)
                )
            """)
        print("[db] Connected to Postgres.")
    except Exception as e:
        # Don't crash the server when the database is unreachable — fall back to file
        # storage so the app still starts. Useful during outages or if the Postgres
        # instance has been deleted (e.g. Render free tier expiry).
        pg_conn = None
        print(f"[db] WARNING: could not connect to Postgres ({e}); falling back to file storage at {DATA_FILE}")


def load_state():
    global state
    raw = None
    if DATABASE_URL and pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT data FROM app_state WHERE id = 1")
            row = cur.fetchone()
            if row:
                raw = row[0]
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)

    migrated = False
    if raw is None:
        state = json.loads(json.dumps(DEFAULT_STATE))
    else:
        state, migrated = migrate_if_needed(raw)

    for trip in state["trips"].values():
        normalize_trip(trip)

    if DATABASE_URL and pg_conn and raw is None:
        with pg_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO app_state (id, data) VALUES (1, %s) "
                "ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data",
                [json.dumps(state, ensure_ascii=False)],
            )

    if migrated:
        save_state()


def save_state():
    global pg_conn
    if DATABASE_URL and pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute(
                    "UPDATE app_state SET data = %s WHERE id = 1",
                    [json.dumps(state, ensure_ascii=False)],
                )
        except Exception:
            try:
                pg_conn = psycopg2.connect(DATABASE_URL)
                pg_conn.autocommit = True
                with pg_conn.cursor() as cur:
                    cur.execute(
                        "UPDATE app_state SET data = %s WHERE id = 1",
                        [json.dumps(state, ensure_ascii=False)],
                    )
            except Exception as e:
                print(f"DB save failed: {e}")
    else:
        with open(DATA_FILE, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)


def trip_state_payload(trip_id):
    trip = state["trips"].get(trip_id)
    if trip is None:
        return None
    return json.dumps({"type": "state", "data": trip})


async def notify_trip(trip_id):
    """Broadcast trip state to every connection currently viewing this trip."""
    payload = trip_state_payload(trip_id)
    if payload is None:
        return
    targets = [c for c, tid in client_trips.items() if tid == trip_id]
    if targets:
        await asyncio.gather(
            *(c.send(payload) for c in targets), return_exceptions=True
        )
    save_state()


# ---------- Permission helpers ----------
def is_owner(trip, name):
    return trip.get("owner") == name


def is_participant(trip, name):
    if not name:
        return False
    return any(p["name"] == name for p in trip.get("participants", []))


async def send_error(websocket, reason):
    try:
        await websocket.send(json.dumps({"type": "error", "reason": reason}))
    except Exception:
        pass


def is_archived(trip):
    end = parse_iso_date(trip.get("end_date"))
    if end is None:
        return False
    return end < datetime.now().date()


# Actions still allowed when a trip is archived (owner-management + personal preference).
ARCHIVED_ALLOWED_ACTIONS = {
    "get_state",
    "set_my_language",
    "update_trip_metadata",
    "update_trip_dates",
    "add_participant",
    "remove_participant",
    "regenerate_code",
    "delete_trip",
    "update_geocache",
}


# ---------- Voting helper ----------
def evaluate_proposal(proposal, participant_count, voting_rule):
    """Update proposal['status'] based on current votes. Returns True if accepted."""
    votes = proposal["votes"]
    yes_count = sum(1 for v in votes.values() if v)
    no_count = sum(1 for v in votes.values() if not v)

    if voting_rule == "majority":
        needed = participant_count // 2 + 1
        if yes_count >= needed:
            proposal["status"] = "accepted"
            return True
        if no_count >= needed:
            proposal["status"] = "rejected"
            return False
        proposal["status"] = "pending"
        return False

    # Default: unanimous
    if len(votes) == participant_count and all(votes.values()):
        proposal["status"] = "accepted"
        return True
    if no_count > 0:
        proposal["status"] = "rejected"
        return False
    proposal["status"] = "pending"
    return False


# ---------- Trip creation ----------
def parse_iso_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def days_between(start, end):
    return (end - start).days + 1


async def handle_create_trip(websocket, msg):
    name = (msg.get("name") or "").strip()
    flag = (msg.get("flag") or "").strip()
    start_s = msg.get("start_date")
    end_s = msg.get("end_date")
    language = msg.get("language", "nl")
    voting_rule = msg.get("voting_rule", "unanimous")
    raw_participants = msg.get("participants") or []
    hotel = msg.get("hotel") or None

    if not (1 <= len(name) <= 50):
        await send_error(websocket, "invalid_name"); return
    if not (1 <= len(flag) <= 12):
        await send_error(websocket, "invalid_flag"); return
    if language not in VALID_LANGUAGES:
        await send_error(websocket, "invalid_language"); return
    if voting_rule not in VALID_VOTING_RULES:
        await send_error(websocket, "invalid_voting_rule"); return

    start = parse_iso_date(start_s)
    end = parse_iso_date(end_s)
    if not start or not end or end < start:
        await send_error(websocket, "invalid_dates"); return
    span = days_between(start, end)
    if span > MAX_TRIP_DAYS:
        await send_error(websocket, "dates_too_long"); return

    if not (MIN_PARTICIPANTS <= len(raw_participants) <= MAX_PARTICIPANTS):
        await send_error(websocket, "invalid_participants_count"); return

    seen_names = set()
    participants = []
    for i, p in enumerate(raw_participants):
        pname = (p.get("name") or "").strip() if isinstance(p, dict) else ""
        if not (1 <= len(pname) <= 30):
            await send_error(websocket, "invalid_participant_name"); return
        key = pname.lower()
        if key in seen_names:
            await send_error(websocket, "duplicate_participant"); return
        seen_names.add(key)
        entry = {"name": pname, "color": COLOR_PALETTE[i % len(COLOR_PALETTE)]}
        plang = p.get("language") if isinstance(p, dict) else None
        if plang and plang in VALID_LANGUAGES and plang != language:
            entry["language"] = plang
        participants.append(entry)

    owner = participants[0]["name"]

    days = {}
    cur = start
    while cur <= end:
        days[cur.isoformat()] = {"proposals": [], "agenda": [], "notes": {}}
        cur = cur.fromordinal(cur.toordinal() + 1)

    slug = generate_unique_slug(name)
    code = generate_trip_code()

    trip = {
        "id": slug,
        "name": name,
        "flag": flag,
        "code": code,
        "owner": owner,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "language": language,
        "voting_rule": voting_rule,
        "hotel": hotel,
        "participants": participants,
        "suggestions": [],
        "days": days,
        "geocache": {},
        "next_id": 1,
        "created": datetime.now().isoformat(),
    }
    state["trips"][slug] = trip
    save_state()

    await websocket.send(json.dumps({
        "type": "trip_created",
        "trip_id": slug,
        "code": code,
    }))


# ---------- WebSocket Message Handler ----------
async def handle_message(websocket, raw):
    msg = json.loads(raw)
    action = msg.get("action")

    # create_trip is the one action that does not require an existing trip.
    if action == "create_trip":
        await handle_create_trip(websocket, msg)
        return

    trip_id = msg.get("trip_id")

    if not trip_id or trip_id not in state["trips"]:
        await send_error(websocket, "unknown_trip")
        return

    trip = state["trips"][trip_id]

    if msg.get("code") != trip["code"]:
        await send_error(websocket, "invalid_code")
        return

    # Track which trip this connection is currently viewing (post-validation).
    client_trips[websocket] = trip_id

    requester = msg.get("requester")

    if action == "get_state":
        await websocket.send(trip_state_payload(trip_id))
        return

    # Every mutation requires a valid participant as requester.
    if not is_participant(trip, requester):
        await send_error(websocket, "not_participant")
        return

    # Archived trips reject content mutations; owner-management remains allowed.
    if is_archived(trip) and action not in ARCHIVED_ALLOWED_ACTIONS:
        await send_error(websocket, "trip_archived")
        return

    mutated = False

    if action == "add_suggestion":
        suggestion = {
            "id": trip["next_id"],
            "title": msg["title"],
            "location": msg["location"],
            "duration": msg["duration"],
            "daypart": msg["daypart"],
            "cost": msg["cost"],
            "link": msg.get("link", ""),
            "description": msg.get("description", ""),
            "author": requester,
            "created": datetime.now().isoformat(),
        }
        trip["next_id"] += 1
        trip["suggestions"].append(suggestion)
        mutated = True

    elif action == "edit_suggestion":
        sid = msg["id"]
        suggestion = next((s for s in trip["suggestions"] if s["id"] == sid), None)
        if not suggestion:
            return
        if suggestion.get("author") != requester:
            await send_error(websocket, "forbidden")
            return
        for field in ["title", "location", "duration", "daypart", "cost", "link", "description"]:
            if field in msg:
                suggestion[field] = msg[field]
        for day in trip["days"].values():
            for proposal in day["proposals"]:
                if proposal["suggestion_id"] == sid:
                    proposal["suggestion"] = dict(suggestion)
            for i, a in enumerate(day["agenda"]):
                if a["id"] == sid:
                    day["agenda"][i] = dict(suggestion)
        mutated = True

    elif action == "delete_suggestion":
        sid = msg["id"]
        suggestion = next((s for s in trip["suggestions"] if s["id"] == sid), None)
        if not suggestion:
            return
        if suggestion.get("author") != requester and not is_owner(trip, requester):
            await send_error(websocket, "forbidden")
            return
        trip["suggestions"] = [s for s in trip["suggestions"] if s["id"] != sid]
        for day in trip["days"].values():
            day["proposals"] = [p for p in day["proposals"] if p["suggestion_id"] != sid]
        mutated = True

    elif action == "propose_for_day":
        day_key = msg["day"]
        sid = msg["suggestion_id"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        existing = [p for p in day["proposals"] if p["suggestion_id"] == sid]
        if not existing:
            suggestion = next((s for s in trip["suggestions"] if s["id"] == sid), None)
            if suggestion:
                proposal = {
                    "id": trip["next_id"],
                    "suggestion_id": sid,
                    "suggestion": suggestion,
                    "proposer": requester,
                    "votes": {requester: True},
                    "status": "pending",
                }
                trip["next_id"] += 1
                day["proposals"].append(proposal)
                mutated = True

    elif action == "vote":
        day_key = msg["day"]
        proposal_id = msg["proposal_id"]
        accept = msg["accept"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        participant_count = len(trip["participants"])
        voting_rule = trip.get("voting_rule", "unanimous")
        for proposal in day["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["votes"][requester] = accept
                accepted = evaluate_proposal(proposal, participant_count, voting_rule)
                if accepted:
                    day["agenda"].append(proposal["suggestion"])
                    day["proposals"] = [
                        p for p in day["proposals"] if p["id"] != proposal_id
                    ]
                mutated = True
                break

    elif action == "revoke_vote":
        day_key = msg["day"]
        proposal_id = msg["proposal_id"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        participant_count = len(trip["participants"])
        voting_rule = trip.get("voting_rule", "unanimous")
        for proposal in day["proposals"]:
            if proposal["id"] == proposal_id:
                if requester in proposal["votes"]:
                    del proposal["votes"][requester]
                    evaluate_proposal(proposal, participant_count, voting_rule)
                    mutated = True
                break

    elif action == "add_note":
        day_key = msg["day"]
        sid = str(msg["suggestion_id"])
        day = trip["days"].get(day_key)
        if day is None:
            return
        note = {
            "id": trip["next_id"],
            "author": requester,
            "text": msg["text"],
            "created": datetime.now().isoformat(),
        }
        trip["next_id"] += 1
        day.setdefault("notes", {}).setdefault(sid, []).append(note)
        mutated = True

    elif action == "delete_note":
        day_key = msg["day"]
        sid = str(msg["suggestion_id"])
        note_id = msg["note_id"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        notes = day.get("notes", {}).get(sid, [])
        target = next((n for n in notes if n["id"] == note_id), None)
        if not target:
            return
        if target.get("author") != requester and not is_owner(trip, requester):
            await send_error(websocket, "forbidden")
            return
        day["notes"][sid] = [n for n in notes if n["id"] != note_id]
        mutated = True

    elif action == "update_geocache":
        location = msg["location"]
        trip["geocache"][location] = {"lat": msg["lat"], "lng": msg["lng"]}
        mutated = True

    elif action == "withdraw_proposal":
        day_key = msg["day"]
        proposal_id = msg["proposal_id"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        proposal = next((p for p in day["proposals"] if p["id"] == proposal_id), None)
        if not proposal:
            return
        if proposal.get("proposer") != requester and not is_owner(trip, requester):
            await send_error(websocket, "forbidden")
            return
        day["proposals"] = [p for p in day["proposals"] if p["id"] != proposal_id]
        mutated = True

    elif action == "remove_from_agenda":
        day_key = msg["day"]
        sid = msg["suggestion_id"]
        day = trip["days"].get(day_key)
        if day is None:
            return
        agenda_item = next((a for a in day["agenda"] if a["id"] == sid), None)
        if not agenda_item:
            return
        if agenda_item.get("author") != requester and not is_owner(trip, requester):
            await send_error(websocket, "forbidden")
            return
        day["agenda"] = [a for a in day["agenda"] if a["id"] != sid]
        sid_str = str(sid)
        if sid_str in day.get("notes", {}):
            del day["notes"][sid_str]
        mutated = True

    elif action == "update_trip_metadata":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        for field, validator in (
            ("name", lambda v: isinstance(v, str) and 1 <= len(v.strip()) <= 50),
            ("flag", lambda v: isinstance(v, str) and 1 <= len(v.strip()) <= 12),
            ("language", lambda v: v in VALID_LANGUAGES),
            ("voting_rule", lambda v: v in VALID_VOTING_RULES),
        ):
            if field in msg:
                if not validator(msg[field]):
                    await send_error(websocket, f"invalid_{field}"); return
                trip[field] = msg[field].strip() if isinstance(msg[field], str) else msg[field]
        if "hotel" in msg:
            h = msg["hotel"]
            if h is None:
                trip["hotel"] = None
            elif isinstance(h, dict):
                hotel = {}
                if h.get("name"):
                    hotel["name"] = str(h["name"]).strip()[:100]
                if h.get("address"):
                    hotel["address"] = str(h["address"]).strip()[:200]
                trip["hotel"] = hotel or None
        mutated = True

    elif action == "update_trip_dates":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        new_start = parse_iso_date(msg.get("start_date"))
        new_end = parse_iso_date(msg.get("end_date"))
        if not new_start or not new_end or new_end < new_start:
            await send_error(websocket, "invalid_dates"); return
        if days_between(new_start, new_end) > MAX_TRIP_DAYS:
            await send_error(websocket, "dates_too_long"); return
        new_keys = []
        cur = new_start
        while cur <= new_end:
            new_keys.append(cur.isoformat())
            cur = cur.fromordinal(cur.toordinal() + 1)
        new_set = set(new_keys)
        for old_key, old_day in trip["days"].items():
            if old_key not in new_set and (old_day.get("proposals") or old_day.get("agenda")):
                await send_error(websocket, "removed_day_has_data"); return
        new_days = {}
        for k in new_keys:
            new_days[k] = trip["days"].get(k) or {"proposals": [], "agenda": [], "notes": {}}
        trip["days"] = new_days
        trip["start_date"] = new_start.isoformat()
        trip["end_date"] = new_end.isoformat()
        mutated = True

    elif action == "add_participant":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        pname = (msg.get("name") or "").strip()
        if not (1 <= len(pname) <= 30):
            await send_error(websocket, "invalid_participant_name"); return
        if any(p["name"].lower() == pname.lower() for p in trip["participants"]):
            await send_error(websocket, "duplicate_participant"); return
        if len(trip["participants"]) >= MAX_PARTICIPANTS:
            await send_error(websocket, "too_many_participants"); return
        used_colors = {p.get("color") for p in trip["participants"]}
        next_color = next((c for c in COLOR_PALETTE if c not in used_colors), COLOR_PALETTE[0])
        trip["participants"].append({"name": pname, "color": next_color})
        mutated = True

    elif action == "remove_participant":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        pname = msg.get("name")
        if not pname:
            await send_error(websocket, "invalid_participant_name"); return
        if is_owner(trip, pname):
            await send_error(websocket, "cannot_remove_owner"); return
        if len(trip["participants"]) <= MIN_PARTICIPANTS:
            await send_error(websocket, "min_participants"); return
        if not any(p["name"] == pname for p in trip["participants"]):
            return
        trip["participants"] = [p for p in trip["participants"] if p["name"] != pname]
        # Withdraw open proposals where this person was proposer; remove their votes from others.
        for day in trip["days"].values():
            day["proposals"] = [p for p in day["proposals"] if p.get("proposer") != pname]
            for p in day["proposals"]:
                if pname in p.get("votes", {}):
                    del p["votes"][pname]
                evaluate_proposal(p, len(trip["participants"]), trip.get("voting_rule", "unanimous"))
        mutated = True

    elif action == "set_my_language":
        lang = msg.get("language") or ""
        if lang and lang not in VALID_LANGUAGES:
            await send_error(websocket, "invalid_language"); return
        for p in trip["participants"]:
            if p["name"] == requester:
                if lang:
                    p["language"] = lang
                else:
                    p.pop("language", None)
                mutated = True
                break

    elif action == "regenerate_code":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        trip["code"] = generate_trip_code()
        save_state()
        await websocket.send(json.dumps({
            "type": "code_regenerated",
            "trip_id": trip_id,
            "code": trip["code"],
        }))
        # Notify other clients on this trip — their code is now invalid.
        for c, tid in list(client_trips.items()):
            if tid == trip_id and c is not websocket:
                try:
                    await c.send(json.dumps({"type": "error", "reason": "invalid_code"}))
                except Exception:
                    pass
        return

    elif action == "delete_trip":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden"); return
        confirmation = msg.get("confirm_name", "")
        if confirmation != trip.get("name"):
            await send_error(websocket, "confirmation_mismatch"); return
        del state["trips"][trip_id]
        save_state()
        # Notify everyone connected to this trip.
        for c, tid in list(client_trips.items()):
            if tid == trip_id:
                try:
                    await c.send(json.dumps({"type": "trip_deleted", "trip_id": trip_id}))
                except Exception:
                    pass
                client_trips[c] = None
        return

    elif action == "reset":
        if not is_owner(trip, requester):
            await send_error(websocket, "forbidden")
            return
        trip["suggestions"] = []
        trip["geocache"] = {}
        trip["next_id"] = 1
        for day in trip["days"].values():
            day["proposals"] = []
            day["agenda"] = []
            day["notes"] = {}
        mutated = True

    if mutated:
        await notify_trip(trip_id)


# ---------- WebSocket Connection Handler ----------
async def ws_handler(websocket):
    try:
        async for message in websocket:
            await handle_message(websocket, message)
    finally:
        client_trips.pop(websocket, None)


# ---------- HTTP Static File Server (via process_request) ----------
async def process_request(connection, request):
    """Serve static files for non-WebSocket requests."""
    if request.path == "/ws":
        return None

    path = request.path or "/"
    if path == "/":
        path = "/index.html"

    if "?" in path:
        path = path.split("?")[0]

    # SPA-routes: /t/<slug> and /new serve index.html so the frontend can route
    # client-side. Paths with file extensions fall through to static lookup.
    last = path.rsplit("/", 1)[-1]
    is_spa_route = (
        (path.startswith("/t/") and "." not in last)
        or path == "/new"
    )
    if is_spa_route:
        file_path = os.path.join(STATIC_DIR, "index.html")
    else:
        file_path = os.path.join(STATIC_DIR, path.lstrip("/"))
    file_path = os.path.normpath(file_path)

    if not file_path.startswith(os.path.normpath(STATIC_DIR)):
        return Response(403, "Forbidden", Headers(), b"Forbidden")

    if os.path.isfile(file_path):
        content_type, _ = mimetypes.guess_type(file_path)
        if content_type is None:
            content_type = "application/octet-stream"

        with open(file_path, "rb") as f:
            body = f.read()

        headers = Headers()
        headers["Content-Type"] = f"{content_type}; charset=utf-8"
        headers["Content-Length"] = str(len(body))
        headers["Cache-Control"] = "no-cache"
        return Response(200, "OK", headers, body)

    return Response(404, "Not Found", Headers(), b"Not Found")


# ---------- Main ----------
async def main():
    init_db()
    load_state()
    print("=" * 50)
    print("  Madrid Trip Planner")
    print("=" * 50)
    print(f"  Server:  http://0.0.0.0:{PORT}")
    print(f"  Data:    {DATA_FILE}")
    print(f"  Trips:   {list(state['trips'].keys())}")
    for tid, trip in state["trips"].items():
        print(f"    - {tid}  code={trip['code']}  owner={trip['owner']}")
    print("=" * 50)

    async with serve(
        ws_handler,
        "0.0.0.0",
        PORT,
        process_request=process_request,
    ):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
