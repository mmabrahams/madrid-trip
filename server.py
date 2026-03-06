#!/usr/bin/env python3
"""Madrid Trip Planner - Single-port server (HTTP + WebSocket on same port)."""

import asyncio
import json
import os
import mimetypes
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

PARTICIPANTS = ["Edje", "Maxime", "El Sierd", "Miqi", "Koen", "Bart"]
DAYS = ["2026-04-01", "2026-04-02", "2026-04-03", "2026-04-04"]

DEFAULT_STATE = {
    "suggestions": [],
    "days": {
        day: {
            "proposals": [],
            "agenda": [],
            "notes": {}
        }
        for day in DAYS
    },
    "next_id": 1,
    "geocache": {}
}

state = None
connected_clients = set()


# ---------- State Management ----------
def init_db():
    """Initialize PostgreSQL table if DATABASE_URL is set."""
    global pg_conn
    if not DATABASE_URL:
        return
    pg_conn = psycopg2.connect(DATABASE_URL)
    pg_conn.autocommit = True
    with pg_conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY DEFAULT 1,
                data JSONB NOT NULL,
                CHECK (id = 1)
            )
        """)


def load_state():
    global state
    if DATABASE_URL and pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT data FROM app_state WHERE id = 1")
            row = cur.fetchone()
            if row:
                state = row[0]
            else:
                state = json.loads(json.dumps(DEFAULT_STATE))
                cur.execute("INSERT INTO app_state (id, data) VALUES (1, %s)", [json.dumps(state)])
    elif os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
    else:
        state = json.loads(json.dumps(DEFAULT_STATE))
    # Ensure geocache exists
    if "geocache" not in state:
        state["geocache"] = {}
    # Ensure all days have notes
    for day in DAYS:
        if day not in state["days"]:
            state["days"][day] = {"proposals": [], "agenda": [], "notes": {}}
        if "notes" not in state["days"][day]:
            state["days"][day]["notes"] = {}


def save_state():
    global pg_conn
    if DATABASE_URL and pg_conn:
        try:
            with pg_conn.cursor() as cur:
                cur.execute("UPDATE app_state SET data = %s WHERE id = 1", [json.dumps(state, ensure_ascii=False)])
        except Exception:
            # Reconnect on connection loss
            try:
                pg_conn = psycopg2.connect(DATABASE_URL)
                pg_conn.autocommit = True
                with pg_conn.cursor() as cur:
                    cur.execute("UPDATE app_state SET data = %s WHERE id = 1", [json.dumps(state, ensure_ascii=False)])
            except Exception as e:
                print(f"DB save failed: {e}")
    else:
        with open(DATA_FILE, "w") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)


def broadcast_state():
    return json.dumps({"type": "state", "data": state})


async def notify_all():
    if connected_clients:
        msg = broadcast_state()
        await asyncio.gather(*(client.send(msg) for client in connected_clients))
    save_state()


# ---------- WebSocket Message Handler ----------
async def handle_message(websocket, raw):
    msg = json.loads(raw)
    action = msg.get("action")

    if action == "get_state":
        await websocket.send(broadcast_state())
        return

    elif action == "add_suggestion":
        suggestion = {
            "id": state["next_id"],
            "title": msg["title"],
            "location": msg["location"],
            "duration": msg["duration"],
            "daypart": msg["daypart"],
            "cost": msg["cost"],
            "link": msg.get("link", ""),
            "description": msg.get("description", ""),
            "author": msg["author"],
            "created": datetime.now().isoformat()
        }
        state["next_id"] += 1
        state["suggestions"].append(suggestion)

    elif action == "edit_suggestion":
        sid = msg["id"]
        requester = msg["requester"]
        suggestion = next((s for s in state["suggestions"] if s["id"] == sid), None)
        if suggestion and suggestion.get("author") == requester:
            for field in ["title", "location", "duration", "daypart", "cost", "link", "description"]:
                if field in msg:
                    suggestion[field] = msg[field]
            # Also update copies in proposals and agenda
            for day in DAYS:
                for proposal in state["days"][day]["proposals"]:
                    if proposal["suggestion_id"] == sid:
                        proposal["suggestion"] = dict(suggestion)
                for i, a in enumerate(state["days"][day]["agenda"]):
                    if a["id"] == sid:
                        state["days"][day]["agenda"][i] = dict(suggestion)

    elif action == "delete_suggestion":
        sid = msg["id"]
        state["suggestions"] = [s for s in state["suggestions"] if s["id"] != sid]
        for day in DAYS:
            state["days"][day]["proposals"] = [
                p for p in state["days"][day]["proposals"]
                if p["suggestion_id"] != sid
            ]

    elif action == "propose_for_day":
        day = msg["day"]
        sid = msg["suggestion_id"]
        proposer = msg["proposer"]
        existing = [p for p in state["days"][day]["proposals"] if p["suggestion_id"] == sid]
        if not existing:
            suggestion = next((s for s in state["suggestions"] if s["id"] == sid), None)
            if suggestion:
                proposal = {
                    "id": state["next_id"],
                    "suggestion_id": sid,
                    "suggestion": suggestion,
                    "proposer": proposer,
                    "votes": {proposer: True},
                    "status": "pending"
                }
                state["next_id"] += 1
                state["days"][day]["proposals"].append(proposal)

    elif action == "vote":
        day = msg["day"]
        proposal_id = msg["proposal_id"]
        voter = msg["voter"]
        accept = msg["accept"]

        for proposal in state["days"][day]["proposals"]:
            if proposal["id"] == proposal_id:
                proposal["votes"][voter] = accept
                votes = proposal["votes"]
                if len(votes) == len(PARTICIPANTS) and all(votes.values()):
                    proposal["status"] = "accepted"
                    state["days"][day]["agenda"].append(proposal["suggestion"])
                    state["days"][day]["proposals"] = [
                        p for p in state["days"][day]["proposals"]
                        if p["id"] != proposal_id
                    ]
                elif any(not v for v in votes.values()):
                    proposal["status"] = "rejected"
                else:
                    proposal["status"] = "pending"
                break

    elif action == "revoke_vote":
        day = msg["day"]
        proposal_id = msg["proposal_id"]
        voter = msg["voter"]

        for proposal in state["days"][day]["proposals"]:
            if proposal["id"] == proposal_id:
                if voter in proposal["votes"]:
                    del proposal["votes"][voter]
                    if any(not v for v in proposal["votes"].values()):
                        proposal["status"] = "rejected"
                    else:
                        proposal["status"] = "pending"
                break

    elif action == "add_note":
        day = msg["day"]
        sid = str(msg["suggestion_id"])
        note = {
            "id": state["next_id"],
            "author": msg["author"],
            "text": msg["text"],
            "created": datetime.now().isoformat()
        }
        state["next_id"] += 1
        if sid not in state["days"][day]["notes"]:
            state["days"][day]["notes"][sid] = []
        state["days"][day]["notes"][sid].append(note)

    elif action == "delete_note":
        day = msg["day"]
        sid = str(msg["suggestion_id"])
        note_id = msg["note_id"]
        requester = msg["requester"]
        agenda_item = next((a for a in state["days"][day]["agenda"] if a["id"] == msg["suggestion_id"]), None)
        if agenda_item and agenda_item.get("author") == requester:
            if sid in state["days"][day]["notes"]:
                state["days"][day]["notes"][sid] = [
                    n for n in state["days"][day]["notes"][sid]
                    if n["id"] != note_id
                ]

    elif action == "update_geocache":
        location = msg["location"]
        state["geocache"][location] = {
            "lat": msg["lat"],
            "lng": msg["lng"]
        }

    elif action == "withdraw_proposal":
        day = msg["day"]
        proposal_id = msg["proposal_id"]
        requester = msg["requester"]
        proposal = next((p for p in state["days"][day]["proposals"] if p["id"] == proposal_id), None)
        if proposal:
            state["days"][day]["proposals"] = [
                p for p in state["days"][day]["proposals"] if p["id"] != proposal_id
            ]

    elif action == "remove_from_agenda":
        day = msg["day"]
        sid = msg["suggestion_id"]
        requester = msg["requester"]
        agenda_item = next((a for a in state["days"][day]["agenda"] if a["id"] == sid), None)
        if agenda_item:
            state["days"][day]["agenda"] = [
                a for a in state["days"][day]["agenda"] if a["id"] != sid
            ]
            # Clean up notes for removed item
            sid_str = str(sid)
            if sid_str in state["days"][day]["notes"]:
                del state["days"][day]["notes"][sid_str]

    elif action == "reset":
        state.clear()
        state.update(json.loads(json.dumps(DEFAULT_STATE)))

    await notify_all()


# ---------- WebSocket Connection Handler ----------
async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        await websocket.send(broadcast_state())
        async for message in websocket:
            await handle_message(websocket, message)
    finally:
        connected_clients.discard(websocket)


# ---------- HTTP Static File Server (via process_request) ----------
async def process_request(connection, request):
    """Serve static files for non-WebSocket requests."""
    # Let WebSocket connections through
    if request.path == "/ws":
        return None

    path = request.path or "/"
    if path == "/":
        path = "/index.html"

    # Strip query string
    if "?" in path:
        path = path.split("?")[0]

    file_path = os.path.join(STATIC_DIR, path.lstrip("/"))
    file_path = os.path.normpath(file_path)

    # Security: prevent path traversal
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
