import time
import random
import json
import urllib.request
import yt_dlp
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="runwise_podcasts")

NOTEBOOK_VIDEOS = [
    {"id": "2SIsQX4NBxA", "title": "30 ans d’expérience, des centaines d’athlètes coachés… il nous dit ce qui compte vraiment"},
    {"id": "7M-loGjtQcE", "title": "Alois Abraham: le jeune Français meilleur que Jakob au même âge"},
    {"id": "jmRaPbRVK78", "title": "Carbones, Fatigue Périphérique, Qualité Neuromusculaire, Musculation, Zones de FC, Seuil, Sommeil"},
    {"id": "WC85DTRK8pE", "title": "Ce coach a testé des dizaines de coureurs en laboratoire"},
    {"id": "3HyQ7Q-XVKA", "title": "Ce coach privilégie la VITESSE... Et ça marche! La philosophie gagnante de Samuel Marion"},
    {"id": "1kf4-nc7Q8Y", "title": "Ce jeune coach est derrière le succès de Jimmy Gressier et Nico Daru"},
    {"id": "MPnl55yLGOs", "title": "Cet étudiant en médecine a participé aux JO en courant moins de 100km par semaine 😤"},
    {"id": "TsDKJKVzI-8", "title": "Cette femme est derrière la domination du TRIATHLON français moderne"},
    {"id": "p56esuSw5eY", "title": "Comment s'entrainer pour du semi-marathon avec COACH Marc-Antoine Seneville"},
    {"id": "zbIFNftTrjA", "title": "De 2h32 à 2h05 : comment Nicolas Navarro est devenu l'un des meilleurs marathoniens français"},
    {"id": "tMXJY7tvmDM", "title": "Elle court 31'15 sur 10km avec 80km/semaine 😮 | SPÉCIAL TOKYO 2025"},
    {"id": "bDHmgcH2NLI", "title": "Elle quitte la France et devient la meilleure Française sur 3000m Steeple avec Alice Finot"},
    {"id": "N4y78GF3icM", "title": "Entrainement marathon, VMA, sorties longues, chaussures carbone, côtes avec Jérémy Cabadet"},
    {"id": "6G3DCBcuDKg", "title": "Entraînement, Seuil, Musculation… Comment Habz est devenu le meilleur Français sur 1500m"},
    {"id": "OarmN8TGgYA", "title": "Fatigue neuro, Système nerveux, Ultra, Descentes et Week-end choc avec le Dr. Guillaume Millet"},
    {"id": "9QkuiNKTUDI", "title": "Félix-Antoine Lapointe: l'entraîneur qui fait voler les coureurs Canadiens"},
    {"id": "k2Gp0nYFOeE", "title": "Gels, Électrolytes, Gut-training, Carb-load, Pic Glycémique, NutriScore, Suppléments @nouchkadiet"},
    {"id": "V7L1H4gkGPA", "title": "Glucides, Suppléments, Crampes, Caféine, Électrolytes, Calories et Poids avec Valentin Lacroix"},
    {"id": "R2wxhazHoDk", "title": "Il a coaché Mehdi Baala, Renelle Lamotte, Bob Tahri, Bosse: On parle entrainement avec Bruno Gajer"},
    {"id": "rI6T6TjYEVs", "title": "Il court 59’27 au semi… sans copier les méthodes classiques"},
    {"id": "DFG3TzGk280", "title": "Ils racontent leur expérience étudiant-athlète aux USA sur le circuit NCAA"},
    {"id": "RcFe3gJePb4", "title": "Importance du foncier, Réserve de vitesse, Altitude, Affutage, Qualité de pied, Pliométrie et Muscu"},
    {"id": "33jma7_FGMw", "title": "Julien Wanders me reçoit chez lui au Kenya: Retour à haut niveau? Sa santé? Sa vie au Kenya?"},
    {"id": "8SDvKnsLOxs", "title": "Kevin Mayer me donne une leçon de DECATHLON 🥵"},
    {"id": "O4UXHcnQuUo", "title": "L'entrainement 100km, Marathon, Parentalité, Nutrition, Musculation"},
    {"id": "uSGKXoI4e00", "title": "L'entraînement des années 80 et ce qui a vraiment changé avec Jacques Marechet"},
    {"id": "x-0kwT8Aegw", "title": "La vie d'un Olympien au 1500m (pas toujours rose...)"},
    {"id": "buZa2MH-rjg", "title": "Le PRÉPARATEUR PHYSIQUE qui fait voler les meilleurs coureurs canadiens 🏋️"},
    {"id": "b28j4InkFYI", "title": "Le RunWise Podcast débarque sur YouTube"},
    {"id": "agnpvIys0-E", "title": "Le coaching en ligne, YouTube, nos erreurs et nos leçons avec @RunningAddict"},
    {"id": "8S4kh-O1YuI", "title": "Le parcours improbable de Jimmy Whelan : de cycliste pro à 61 minutes au semi"},
    {"id": "ztDKBYRO_Ws", "title": "Les coulisses de Run'ix, le Kenya, les meilleures chaussures et pourquoi il s'entraine comme Jakob"},
    {"id": "3XXIrY1gY64", "title": "Les secrets de la méthode NORVÉGIENNE expliqués par un physiologiste 🤓"},
    {"id": "LKM8iU3jEGY", "title": "Mon expérience de coaching avec @anthony.frontera (un athlète élite qui n'en fait qu'à sa tête 😅)"},
    {"id": "1qyeMqZe2TQ", "title": "On prend une leçon de TRAIL par Mathieu Blanchard"},
    {"id": "xw_o1s7fpTg", "title": "PEACE & LOVE : la meilleure méthode pour traiter les bl*ssures chez les coureurs ?"},
    {"id": "0joleErKKLk", "title": "Physiologiste, 30 ans à l’INSEP, elle a formé nos meilleurs entraîneurs et athlètes français"},
    {"id": "lRtEr1NMnew", "title": "Plaques carbones inutiles, le fameux 180 pas par minute : Blaise Dubois démonte des mythes !"},
    {"id": "HYv055ki_fQ", "title": "Pourquoi les coureurs d’endurance devraient s’intéresser au sprint avec Younès Nezar"},
    {"id": "yi25FpeTKmA", "title": "Pourquoi les meilleurs coureurs s'entrainent en altitude avec le Dr Grégory Doucende"},
    {"id": "J7LteQARFmk", "title": "Pression des chronos et besoin de reconnaissance: Les sujets TABOU en course à pied"},
    {"id": "Xz1OvhpPL6Y", "title": "Primes, contrats, sponsors, pacers : dans les coulisses du métier d’agent avec Julien Di Maria"},
    {"id": "ZyvawZ7IjrM", "title": "Quand la course devient une addiction avec le Dr Nicolas Moreau"},
    {"id": "jRpwbeXqhhg", "title": "Rencontre avec la marathonienne la plus RAPIDE du Québec, RP en 2h33 🥵"},
    {"id": "uuCBDEu5HVY", "title": "Rencontre avec mon Dorys Langlois, mon ancien coach : le plus gros geek de course à pied 🤓"},
    {"id": "oYBfpc5ttjk", "title": "Son Histoire, le Marathon de Berlin, sa Relation avec son Père avec @mustaphasalmi"},
    {"id": "yIo6qB0t6sc", "title": "Son entraînement, 240km/sem, Mental, Auto-Coaching, Record du monde, Nutrition, Comrades, Salomon"},
    {"id": "RQGvfi6GW_Q", "title": "Sprint, plio, biomécanique, économie de course, VO₂max, musculation et coordination avec JB Morin"},
    {"id": "Cb8HzzDGtRs", "title": "Syblo: son Entrainement, Création de Contenu, Sponsoring, Équipe de France, Ses études, Marathon?"},
    {"id": "IyX6iCKzPlw", "title": "« J’ai utilisé ChatGPT pour me qualifier aux JO » John Heymans | 13’03 sur 5000m"},
    {"id": "3HyS0cmuTWQ", "title": "« Pour vraiment progresser, il faut apprendre à ralentir » Bastien Perraux, entraineur national"},
    {"id": "4u4TJIYT2YM", "title": "« À l’armée, l’erreur coûte la vie… sur piste, c’est juste une course de plus » Nicolas Marie Dary"},
]

def is_already_indexed(video_id: str) -> bool:
    """Vérifie si la vidéo est déjà dans ChromaDB pour ne pas la retélécharger."""
    existing = collection.get(where={"video_id": video_id}, limit=1)
    return len(existing.get("ids", [])) > 0

def fetch_transcript_via_ytdlp(video_id: str):
    """Récupère les sous-titres JSON3 via yt-dlp (beaucoup plus résistant au blocage IP)."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["fr", "en"],
        "quiet": True,
        "no_warnings": True,
        # Décommente la ligne ci-dessous ("firefox" ou "chrome") si YouTube bloque encore :
        # "cookiesfrombrowser": ("firefox",),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        subs = info.get("subtitles", {}) or info.get("automatic_captions", {})
        lang_subs = subs.get("fr") or subs.get("en")
        if not lang_subs:
            return None

        # On cherche le format json3 qui contient les timestamps précis
        json3_url = next((s["url"] for s in lang_subs if s.get("ext") == "json3"), None)
        if not json3_url:
            return None

        req = urllib.request.Request(json3_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        transcript = []
        for event in data.get("events", []):
            if "segs" in event:
                text = "".join(seg.get("utf8", "") for seg in event["segs"]).strip()
                if text:
                    start_sec = event.get("tStartMs", 0) / 1000.0
                    transcript.append({"text": text, "start": start_sec})
        return transcript

def index_video(video_id: str, title: str, chunk_duration: int = 120):
    try:
        transcript = fetch_transcript_via_ytdlp(video_id)
        if not transcript:
            print(f"⚠️ Aucun sous-titre trouvé pour '{title[:40]}...'")
            return
    except Exception as e:
        print(f"⚠️ Erreur sur '{title[:40]}...' ({video_id}): {e}")
        return

    chunks, metadatas, ids = [], [], []
    current_text = []
    chunk_start = 0.0

    for item in transcript:
        if not current_text:
            chunk_start = item["start"]
        current_text.append(item["text"].replace("\n", " "))

        if (item["start"] - chunk_start) >= chunk_duration:
            timestamp_sec = int(chunk_start)
            chunks.append(f"[{title}] " + " ".join(current_text))
            metadatas.append({
                "video_id": video_id,
                "title": title,
                "start_sec": timestamp_sec,
                "url": f"https://www.youtube.com/watch?v={video_id}&t={timestamp_sec}s"
            })
            ids.append(f"{video_id}_{timestamp_sec}")
            current_text = []

    if current_text:
        timestamp_sec = int(chunk_start)
        chunks.append(f"[{title}] " + " ".join(current_text))
        metadatas.append({
            "video_id": video_id,
            "title": title,
            "start_sec": timestamp_sec,
            "url": f"https://www.youtube.com/watch?v={video_id}&t={timestamp_sec}s"
        })
        ids.append(f"{video_id}_{timestamp_sec}")

    if chunks:
        collection.upsert(documents=chunks, metadatas=metadatas, ids=ids)
        print(f"✅ Indexé : {title[:55]}... ({len(chunks)} blocs)")

if __name__ == "__main__":
    print(f"🚀 Reprise de l'indexation ({collection.count()} blocs déjà en base)...")
    for idx, v in enumerate(NOTEBOOK_VIDEOS, 1):
        if is_already_indexed(v["id"]):
            print(f"⏭️  [{idx}/{len(NOTEBOOK_VIDEOS)}] Déjà indexé : {v['title'][:50]}...")
            continue

        print(f"📥 [{idx}/{len(NOTEBOOK_VIDEOS)}] Téléchargement de {v['id']}...")
        index_video(v["id"], v["title"])

        # Pause de 2.5 à 4.5 secondes pour éviter le rate-limit YouTube
        time.sleep(random.uniform(2.5, 4.5))

    print(f"\n🎉 Terminé ! Total de segments dans ChromaDB : {collection.count()}")
