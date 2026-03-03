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

# ---------- Config ----------
PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = os.environ.get("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(DATA_DIR, "data.json")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")

PARTICIPANTS = ["Edje", "Maxime", "El Sierd", "Miqi", "Koen"]
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
    "next_id": 1
}

state = None
connected_clients = set()


# ---------- State Management ----------
def load_state():
    global state
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            state = json.load(f)
        for day in DAYS:
            if day not in state["days"]:
                state["days"][day] = {"proposals": [], "agenda": [], "notes": {}}
            if "notes" not in state["days"][day]:
                state["days"][day]["notes"] = {}
    else:
        state = json.loads(json.dumps(DEFAULT_STATE))


def save_state():
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
            "author": msg["author"],
            "created": datetime.now().isoformat()
        }
        state["next_id"] += 1
        state["suggestions"].append(suggestion)

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

    elif action == "remove_from_agenda":
        day = msg["day"]
        sid = msg["suggestion_id"]
        state["days"][day]["agenda"] = [
            a for a in state["days"][day]["agenda"] if a["id"] != sid
        ]

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
