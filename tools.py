import os
import requests
import chromadb
from datetime import date, timedelta
from dotenv import load_dotenv
from langchain_core.tools import tool

load_dotenv()

ATHLETE_ID = os.getenv("INTERVALS_ATHLETE_ID")
INTERVALS_API_KEY = os.getenv("INTERVALS_API_KEY")
BASE_URL = "https://intervals.icu/api/v1"

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="runwise_podcasts")

def speed_to_pace(speed_ms: float) -> str:
    if not speed_ms or speed_ms <= 0:
        return "N/A"
    sec_per_km = 1000.0 / speed_ms
    mins = int(sec_per_km // 60)
    secs = int(round(sec_per_km % 60))
    if secs == 60:
        mins += 1
        secs = 0
    return f"{mins}'{secs:02d}\"/km"

def format_duration(seconds: int) -> str:
    if not seconds:
        return "0s"
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}'{secs:02d}\"" if mins > 0 else f"{secs}\""

@tool
def search_runwise_knowledge(query: str) -> str:
    """Cherche dans les transcriptions du RunWise Podcast les concepts d'entraînement,
    allures, seuil, volume ou physiologie. Retourne les extraits avec le titre et l'URL horodatée."""
    if collection.count() == 0:
        return "La base ChromaDB RunWise est vide pour le moment (lance ingest_videos.py)."
    results = collection.query(query_texts=[query], n_results=4)
    formatted = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        mins, secs = divmod(meta["start_sec"], 60)
        formatted.append(
            f"🎥 Épisode: {meta['title']} (à {mins:02d}:{secs:02d})\n"
            f"🔗 Lien: {meta['url']}\n"
            f"💬 Extrait: {doc}\n"
        )
    return "\n---\n".join(formatted)

@tool
def get_intervals_activities(days: int = 14) -> str:
    """Récupère la liste des séances des X derniers jours avec leur activity_id."""
    oldest = (date.today() - timedelta(days=days)).isoformat()
    newest = date.today().isoformat()
    r = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/activities?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY), timeout=10
    )
    r.raise_for_status()

    output = []
    for act in r.json():
        if act.get("type") in ["Run", "TrailRun", "VirtualRun", "Track"]:
            dist_km = round((act.get("distance") or 0) / 1000, 2)
            pace = speed_to_pace(act.get("average_speed"))
            output.append(
                f"🆔 ID: {act.get('id')} | 📅 {act.get('start_date_local')[:10]} | "
                f"🏃 {act.get('name')} | {dist_km} km ({pace}) | "
                f"FC Moy/Max: {act.get('average_heartrate')}/{act.get('max_heartrate')} bpm | "
                f"Load: {act.get('icu_training_load')} | Découplage: {act.get('decoupling')}%"
            )
    return "\n".join(output) if output else "Aucune activité trouvée sur cette période."

@tool
def get_activity_intervals_detail(activity_id: str) -> str:
    """Récupère le détail complet des tours (laps/intervalles) d'une séance précise
    à partir de son activity_id (distance, durée, allure au km, FC moy/max, cadence)."""
    r = requests.get(
        f"{BASE_URL}/activity/{activity_id}/intervals",
        auth=("API_KEY", INTERVALS_API_KEY), timeout=10
    )
    r.raise_for_status()
    data = r.json()

    intervals = data.get("icu_intervals", [])
    if not intervals:
        return f"Aucun intervalle détecté pour la séance {activity_id}."

    lines = [f"📊 Détail des intervalles pour la séance {activity_id} :"]
    for idx, lap in enumerate(intervals, start=1):
        lap_type = lap.get("type", "UNKNOWN")
        label = lap.get("label") or lap_type
        dist_m = int(round(lap.get("distance") or 0))
        duration = format_duration(lap.get("moving_time"))
        pace = speed_to_pace(lap.get("average_speed"))
        avg_hr = lap.get("average_heartrate") or "N/A"
        max_hr = lap.get("max_heartrate") or "N/A"
        raw_cad = lap.get("average_cadence")
        cadence = f"{int(round(raw_cad * 2))} spm" if raw_cad else "N/A"

        icon = "🔥 [EFFORT]" if lap_type == "WORK" else "💧 [RÉCUP] "
        lines.append(
            f"Tour {idx:02d} {icon} ({label}) : {dist_m}m en {duration} "
            f"| Allure: {pace} | FC: {avg_hr} bpm (Max: {max_hr}) | Cadence: {cadence}"
        )

    groups = data.get("icu_groups", [])
    if groups:
        lines.append("\n📌 Synthèse automatique des blocs d'effort (Groups) :")
        for g in groups:
            g_pace = speed_to_pace(g.get("average_speed"))
            lines.append(
                f"- Bloc '{g.get('id')}' ({g.get('count')} répétitions) : "
                f"Moyenne {int(round(g.get('distance') or 0))}m en {format_duration(g.get('moving_time'))} ({g_pace}) "
                f"| FC Moy: {g.get('average_heartrate')} bpm"
            )
    return "\n".join(lines)

@tool
def get_intervals_wellness(days: int = 7) -> str:
    """Récupère l'état de forme (Fitness CTL, Fatigue ATL, Form TSB = CTL - ATL), FC au repos et VFC/HRV."""
    oldest = (date.today() - timedelta(days=days)).isoformat()
    newest = date.today().isoformat()
    r = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/wellness?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY), timeout=10
    )
    r.raise_for_status()

    output = []
    for w in r.json():
        ctl = round(w.get("ctl") or 0, 1)
        atl = round(w.get("atl") or 0, 1)
        tsb = round(ctl - atl, 1)
        output.append(
            f"📅 {w.get('id')} | CTL (Fitness): {ctl} | ATL (Fatigue): {atl} | "
            f"TSB (Forme): {tsb} | FC Repos: {w.get('restingHR')} bpm | HRV: {w.get('hrv')}"
        )
    return "\n".join(output)

@tool
def get_planned_workouts(days_ahead: int = 7) -> str:
    """Consulte les séances et événements déjà prévus dans le calendrier Intervals.icu pour les X prochains jours."""
    oldest = date.today().isoformat()
    newest = (date.today() + timedelta(days=days_ahead)).isoformat()
    r = requests.get(
        f"{BASE_URL}/athlete/{ATHLETE_ID}/events?oldest={oldest}&newest={newest}",
        auth=("API_KEY", INTERVALS_API_KEY), timeout=10
    )
    r.raise_for_status()
    events = r.json()
    if not events:
        return f"Aucun entraînement planifié entre le {oldest} et le {newest}."

    output = [f"🗓️ Calendrier prévu du {oldest} au {newest} :"]
    for ev in events:
        ev_date = ev.get("start_date_local", "")[:10]
        output.append(f"- {ev_date} | [{ev.get('category')}] {ev.get('name')} |\n{ev.get('description', '')}")
    return "\n".join(output)

@tool
def schedule_intervals_workout(workout_date: str, name: str, workout_syntax: str) -> str:
    """Planifie et crée une séance d'entraînement structurée dans le calendrier Intervals.icu.
    workout_date: 'YYYY-MM-DD'
    name: Titre de la séance
    workout_syntax: Syntaxe stricte Intervals.icu avec sections (Warmup, Main Set Nx, Cooldown) et lignes commençant par '- '."""
    url = f"{BASE_URL}/athlete/{ATHLETE_ID}/events"
    payload = {
        "category": "WORKOUT",
        "start_date_local": f"{workout_date}T00:00:00",
        "name": name,
        "description": workout_syntax,
        "type": "Run"
    }
    r = requests.post(url, auth=("API_KEY", INTERVALS_API_KEY), timeout=10, json=payload)
    if r.status_code not in (200, 201):
        return f"❌ Erreur ({r.status_code}): {r.text}"
    data = r.json()
    est_dist = round((data.get("distance") or 0) / 1000, 2)
    return f"✅ Séance '{name}' programmée le {workout_date} (ID: {data.get('id')}, ~{est_dist} km, Load: {data.get('icu_training_load')})"
