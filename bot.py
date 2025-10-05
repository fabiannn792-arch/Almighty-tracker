# bot.py
import os
import json
import requests
import time
import base64
from googleapiclient.discovery import build
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# --- Variables desde Secrets (GitHub Actions) ---
DISCORD_WEBHOOK = os.getenv(https://discord.com/api/webhooks/1424431655304560700/QABQzoYsrmJ2qkNiKDeBsSj9Ry82Vkq--UOZasPK3uPR9_fvP49mLOdM5FBo09eYPm5C)
YOUTUBE_API_KEY = os.getenv(AIzaSyBOGQN8Ljjb0SoSxTbyNhGNPQOPtQ9zdSE)
SPOTIFY_CLIENT_ID = os.getenv(59f397eed5ab405a90dc276330262223)
SPOTIFY_CLIENT_SECRET = os.getenv(2de2e956e20a43d790b6510fdd37b2ff)
YOUTUBE_CHANNEL_ID = os.getenv(UCxg9gU5cLuRkZ9a5VJYbSRA)       # debes poner el ID del canal de Almighty
SPOTIFY_ARTIST_ID = os.getenv(6P6GTRTigHBp8ZesNtpCKH?si=VhlJevaiSwSXCnHHy1-TXw)         # debes poner el artist id de Spotify
GITHUB_TOKEN = os.getenv(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)
GITHUB_REPOSITORY = os.getenv(fabiannn792-arch/almighty-tracker)         # p. ej. "tuUsuario/almighty-tracker"

DATA_FILE = "data.json"

# === YouTube setup ===
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# === Spotify setup ===
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# --- YouTube helpers ---
def get_youtube_videos():
    vids = []
    try:
        req = youtube.search().list(part="snippet", channelId=YOUTUBE_CHANNEL_ID, maxResults=20, order="date")
        res = req.execute()
        for v in res.get("items", []):
            if "videoId" in v["id"]:
                vids.append((v["snippet"]["title"], v["id"]["videoId"]))
    except Exception as e:
        print("Error al obtener videos YouTube:", e)
    return vids

def get_youtube_views(video_id):
    try:
        res = youtube.videos().list(part="statistics", id=video_id).execute()
        return int(res["items"][0]["statistics"].get("viewCount", 0))
    except Exception as e:
        print("Error al obtener views YouTube:", e)
        return 0

# --- Spotify helpers ---
def get_spotify_tracks():
    try:
        # obtenemos las top tracks del artista (país US como default)
        results = sp.artist_top_tracks(SPOTIFY_ARTIST_ID, country='US')
        return [(t["name"], t["id"]) for t in results["tracks"]]
    except Exception as e:
        print("Error al obtener tracks Spotify:", e)
        return []

def get_spotify_streams_estimate(track_id):
    # Nota: la API pública de Spotify no da el número exacto de reproducciones por track.
    # Aquí usamos "popularity" como estimación (0-100). Multiplicador es aproximado.
    try:
        track = sp.track(track_id)
        popularity = track.get("popularity", 0)
        return popularity * 10000  # estimación grosera; ajustar si lo deseas
    except Exception as e:
        print("Error al obtener popularity Spotify:", e)
        return 0

# --- Guardar / cargar ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data_local(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Notificaciones ---
def notify(title, platform, views, delta):
    msg = f"🔥 **{title}** alcanzó **{views:,}** reproducciones en {platform} ( +{delta:,} desde la última vez )"
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": msg})
        print("Notificación enviada:", title, platform, views)
    except Exception as e:
        print("Error al enviar notificación:", e)

# --- Persistir data.json en el repo (commit via GitHub API) ---
def persist_data_to_repo(data):
    if not GITHUB_TOKEN or not GITHUB_REPOSITORY:
        print("No hay GITHUB_TOKEN o GITHUB_REPOSITORY; saltando persistencia remota.")
        return
    url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/contents/{DATA_FILE}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    content_b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    # comprobar si existe el archivo para obtener sha
    get = requests.get(url, headers=headers)
    payload = {
        "message": "Update data.json (bot)",
        "content": content_b64,
        "branch": "main"
    }
    if get.status_code == 200:
        sha = get.json().get("sha")
        payload["sha"] = sha
    put = requests.put(url, headers=headers, json=payload)
    if put.status_code in (200,201):
        print("data.json actualizado en el repo.")
    else:
        print("Error al subir data.json al repo:", put.status_code, put.text)

# --- Main ---
def main():
    data = load_data()

    # YouTube
    videos = get_youtube_videos()
    for title, vid in videos:
        views = get_youtube_views(vid)
        key = f"yt_{vid}"
        prev = data.get(key, 0)
        delta = views - prev
        if prev == 0 and views >= 1_000_000:
            # si no teníamos registro y ya tiene >1M, notificamos la primera vez
            notify(title, "YouTube", views, delta)
        elif delta >= 1_000_000:
            notify(title, "YouTube", views, delta)
        data[key] = views

    # Spotify
    tracks = get_spotify_tracks()
    for title, tid in tracks:
        streams = get_spotify_streams_estimate(tid)
        key = f"sp_{tid}"
        prev = data.get(key, 0)
        delta = streams - prev
        if prev == 0 and streams >= 1_000_000:
            notify(title, "Spotify (estim.)", streams, delta)
        elif delta >= 1_000_000:
            notify(title, "Spotify (estim.)", streams, delta)
        data[key] = streams

    # guardar local y subir al repo (para preservar entre ejecuciones)
    save_data_local(data)
    persist_data_to_repo(data)

if __name__ == "__main__":
    main()
