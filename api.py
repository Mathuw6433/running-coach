import socket
_orig_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, port, family=0, type=0, proto=0, flags=0: _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

import os
import re
from datetime import date, timedelta
from typing import List, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ingest_videos import NOTEBOOK_VIDEOS
from tools import (
    ATHLETE_ID,
    INTERVALS_API_KEY,
    BASE_URL,
    collection,
    speed_to_pace,
)
from agent_cli import agent

app = FastAPI(title="RunWise x Intervals.icu API", version="1.0.0")

# Autoriser le Front-End (Google AI Studio / localhost:3000 / Vite) à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mémoire des conversations par session
SESSIONS = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

@app.get("/api/videos")
def list_videos():
    """Renvoie les 52 vidéos RunWise avec miniatures et statut d'indexation ChromaDB."""
    existing = collection.get(include=["metadatas"])
    indexed_ids = {m["video_id"] for m in existing.get("metadatas", []) if m and "video_id" in m}

    videos = []
    for v in NOTEBOOK_VIDEOS:
        vid = v["id"]
        videos.append({
            "id": vid,
            "title": v["title"],
            "url": f"https://www.youtube.com/watch?v={vid}",
            "embed_url": f"https://www.youtube.com/embed/{vid}",
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "indexed": vid in indexed_ids,
        })
    return {"total": len(videos), "indexed_count": len(indexed_ids), "videos": videos}

@app.get("/api/videos/search")
def search_videos(q: str, limit: int = 6):
    """Recherche sémantique directe dans les transcriptions RunWise avec timestamps."""
    if collection.count() == 0:
        return {"results": []}
    res = collection.query(query_texts=[q], n_results=limit)
    hits = []
    for doc, meta in zip(res["documents"][0], res["metadatas"][0]):
        mins, secs = divmod(meta["start_sec"], 60)
        hits.append({
            "video_id": meta["video_id"],
            "title": meta["title"],
            "start_sec": meta["start_sec"],
            "timestamp_str": f"{mins:02d}:{secs:02d}",
            "url": meta["url"],
            "thumbnail": f"https://i.ytimg.com/vi/{meta['video_id']}/hqdefault.jpg",
            "excerpt": doc,
        })
    return {"results": hits}

@app.get("/api/intervals/dashboard")
def get_dashboard_data(days: int = 14):
    """Renvoie les données JSON brutes (Wellness + Séances) pour les graphiques du Front-End."""
    oldest = (date.today() - timedelta(days=days)).isoformat()
    newest = date.today().isoformat()

    w_resp = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/wellness?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY),
        timeout=10,
    )
    a_resp = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/activities?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY),
        timeout=10,
    )

    wellness = []
    if w_resp.ok:
        for w in w_resp.json():
            ctl = round(w.get("ctl") or 0, 1)
            atl = round(w.get("atl") or 0, 1)
            wellness.append({
                "date": w.get("id"),
                "ctl": ctl,
                "atl": atl,
                "tsb": round(ctl - atl, 1),
                "resting_hr": w.get("restingHR"),
                "hrv": w.get("hrv"),
            })

    activities = []
    if a_resp.ok:
        for act in a_resp.json():
            if act.get("type") in ["Run", "TrailRun", "VirtualRun", "Track"]:
                activities.append({
                    "id": act.get("id"),
                    "date": act.get("start_date_local", "")[:10],
                    "name": act.get("name"),
                    "distance_km": round((act.get("distance") or 0) / 1000, 2),
                    "moving_time_min": round((act.get("moving_time") or 0) / 60, 1),
                    "pace": speed_to_pace(act.get("average_speed")),
                    "avg_hr": act.get("average_heartrate"),
                    "max_hr": act.get("max_heartrate"),
                    "load": act.get("icu_training_load"),
                    "decoupling": act.get("decoupling"),
                })

    return {"wellness": wellness, "activities": activities}

@app.post("/api/chat")
def chat_with_coach(req: ChatRequest):
    """Envoie un message à l'agent LangGraph et retourne la réponse + les outils utilisés."""
    history = SESSIONS.get(req.session_id, [])
    prev_len = len(history)
    history.append(("user", req.message))

    result = agent.invoke({"messages": history})
    messages = result["messages"]
    SESSIONS[req.session_id] = messages

    tools_used = []
    for msg in messages[prev_len:]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_used.append({"name": tc["name"], "args": tc["args"]})

    final_msg = messages[-1].content
    if isinstance(final_msg, list):
        answer = "\n".join(p.get("text", "") for p in final_msg if isinstance(p, dict))
    else:
        answer = str(final_msg)

    # Extraire automatiquement les liens YouTube horodatés cités dans la réponse pour le lecteur vidéo du Front
    yt_refs = []
    for match in re.finditer(r"watch\?v=([a-zA-Z0-9_-]{11})(?:&t=(\d+)s)?", answer):
        yt_refs.append({
            "video_id": match.group(1),
            "start_sec": int(match.group(2)) if match.group(2) else 0,
        })

    return {
        "answer": answer,
        "tools_used": tools_used,
        "video_references": yt_refs,
    }

@app.post("/api/chat/reset")
def reset_chat(session_id: str = "default"):
    SESSIONS.pop(session_id, None)
    return {"status": "cleared"}

# --- NOUVELLES ROUTES POUR LES ONGLETS DÉTAILLÉS ---

@app.get("/api/intervals/activity/{activity_id}")
def get_full_activity_detail(activity_id: str):
    """Renvoie TOUTES les métriques d'une activité + ses intervalles/laps comme sur Intervals.icu."""
    act_resp = requests.get(
        f"{BASE_URL}/activity/{activity_id}",
        auth=("API_KEY", INTERVALS_API_KEY),
        timeout=10,
    )
    int_resp = requests.get(
        f"{BASE_URL}/activity/{activity_id}/intervals",
        auth=("API_KEY", INTERVALS_API_KEY),
        timeout=10,
    )
    if not act_resp.ok:
        raise HTTPException(status_code=act_resp.status_code, detail="Activité introuvable")

    act = act_resp.json()
    int_data = int_resp.json() if int_resp.ok else {}

    laps = []
    for idx, lap in enumerate(int_data.get("icu_intervals", []), start=1):
        raw_cad = lap.get("average_cadence")
        laps.append({
            "index": idx,
            "type": lap.get("type", "WORK"),
            "label": lap.get("label") or lap.get("type"),
            "distance_m": int(round(lap.get("distance") or 0)),
            "moving_time_s": lap.get("moving_time") or 0,
            "pace": speed_to_pace(lap.get("average_speed")),
            "avg_hr": lap.get("average_heartrate"),
            "max_hr": lap.get("max_heartrate"),
            "cadence_spm": int(round(raw_cad * 2)) if raw_cad else None,
            "zone": lap.get("zone"),
        })

    raw_avg_cad = act.get("average_cadence")
    return {
        "id": act.get("id"),
        "name": act.get("name"),
        "date": act.get("start_date_local"),
        "type": act.get("type"),
        "distance_km": round((act.get("distance") or 0) / 1000, 2),
        "moving_time_s": act.get("moving_time"),
        "pace": speed_to_pace(act.get("average_speed")),
        "gap_pace": speed_to_pace(act.get("gap")),  # Allure ajustée à la pente
        "avg_hr": act.get("average_heartrate"),
        "max_hr": act.get("max_heartrate"),
        "cadence_spm": int(round(raw_avg_cad * 2)) if raw_avg_cad else None,
        "calories": act.get("calories"),
        "elevation_gain_m": act.get("total_elevation_gain"),
        "training_load": act.get("icu_training_load"),
        "trimp": round(act.get("trimp") or 0, 1),
        "intensity": round(act.get("icu_intensity") or 0, 1),
        "decoupling": round(act.get("decoupling") or 0, 2),
        "efficiency_factor": round(act.get("icu_efficiency_factor") or 0, 2),
        "hr_zone_times": act.get("icu_hr_zone_times", []),
        "pace_zone_times": act.get("pace_zone_times", []),
        "laps": laps,
        "groups": int_data.get("icu_groups", []),
    }

@app.get("/api/intervals/events")
def get_upcoming_events(days_ahead: int = 21):
    """Renvoie les séances planifiées dans l'agenda Intervals.icu pour les X prochains jours."""
    oldest = date.today().isoformat()
    newest = (date.today() + timedelta(days=days_ahead)).isoformat()
    r = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/events?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY),
        timeout=10,
    )
    if not r.ok:
        return {"events": []}
    events = []
    for ev in r.json():
        events.append({
            "id": ev.get("id"),
            "date": ev.get("start_date_local", "")[:10],
            "start_date_local": ev.get("start_date_local"),
            "name": ev.get("name"),
            "category": ev.get("category"),
            "description": ev.get("description") or "",
            "distance_km": round((ev.get("distance") or 0) / 1000, 2),
            "moving_time_min": round((ev.get("moving_time") or 0) / 60, 1),
            "load": ev.get("icu_training_load"),
        })
    return {"events": events}

@app.get("/")
def serve_landing():
    """Affiche la landing page Shadow Coach."""
    return FileResponse("presentation.html")

@app.get("/app")
def serve_app():
    """Affiche le cockpit React Shadow Coach."""
    return FileResponse("app.html")
