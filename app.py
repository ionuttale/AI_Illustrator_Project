from flask import Flask, render_template, jsonify, send_from_directory, request
from spotify_client import SpotifyHandler
import os
import time
import re
import requests
import json
import threading

app = Flask(__name__)
spotify = SpotifyHandler()

track_resolutions = {}
MAX_GENERATION_DIM = 1024

# --- LYRICS HANDLER (Integrated) ---
class FreeLyricsHandler:
    def __init__(self):
        self.cache_file = "lyrics_cache.json"
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        except:
            self.cache = {}

    def save_cache(self):
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _clean(self, s):
        return re.sub(r"[^\w\s\-']", "", s).strip()

    def get_lyrics(self, title, artist, song_id):
        if song_id in self.cache:
            return self.cache[song_id]
        
        try:
            print(f"Fetching lyrics for: {title}")
            url = f"https://api.lyrics.ovh/v1/{self._clean(artist)}/{self._clean(title)}"
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                lyrics = r.json().get("lyrics", "")
                if lyrics:
                    self.cache[song_id] = lyrics
                    self.save_cache()
                    return lyrics
        except Exception as e:
            print(f"Lyrics Error: {e}")
        return None

lyrics_handler = FreeLyricsHandler()

# --- CACHE CONFIGURATION ---
spotify_cache = {
    "data": None,
    "last_updated": 0,
    "ttl": 4 
}

def invalidate_cache():
    spotify_cache["last_updated"] = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/generate/<song_id>', methods=['POST'])
def receive_resolution(song_id):
    # This route triggers the generation logic (AI Prompt + Image Gen)
    # Ideally, your AI generation code runs here in a separate thread/process
    data = request.json
    raw_w = data.get("width", 512)
    raw_h = data.get("height", 512)

    final_width = min(int((raw_w / 2) // 8) * 8, MAX_GENERATION_DIM)
    final_height = min(int((raw_h / 2) // 8) * 8, MAX_GENERATION_DIM)

    track_resolutions[song_id] = (final_width, final_height)
    print(f"🎨 GENERATING ART: {song_id} ({final_width}x{final_height})")

    # NOTE: Ensure your AI generation function is called here!
    # generate_art_function(song_id, final_width, final_height) 

    return jsonify({"status": "resolution_received", "dims": [final_width, final_height]})

@app.route('/art/<song_id>')
def serve_art(song_id):
    return send_from_directory('art_output', f"{song_id}.png")

@app.route('/api/status')
def get_status():
    current_time = time.time()
    
    # 1. Return cached data if valid
    if spotify_cache["data"] and (current_time - spotify_cache["last_updated"] < spotify_cache["ttl"]):
        cached_data = spotify_cache["data"].copy()
        if cached_data["playing"]:
             # Check if current image is ready
             image_path = f"art_output/{cached_data['id']}.png"
             cached_data["image_ready"] = os.path.exists(image_path)
             cached_data["update_tick"] = int(current_time)
        return jsonify(cached_data)

    # 2. Fetch fresh data
    current = spotify.get_current_track()
    
    # --- NEW: Fetch Next Song in Queue ---
    next_track = spotify.get_queue() # Requires updated SpotifyHandler
    
    spotify_cache["last_updated"] = current_time

    if current:
        image_path = f"art_output/{current['id']}.png"
        
        # Fetch lyrics (optional, runs fast due to cache)
        lyric_text = lyrics_handler.get_lyrics(current['title'], current['artist'], current['id'])

        response_data = {
            "playing": True,
            "id": current['id'],
            "title": current['title'],
            "artist": current['artist'],
            "progress_ms": current.get('progress_ms', 0),
            "is_playing": current.get('is_playing', False),
            "image_ready": os.path.exists(image_path),
            "lyrics": lyric_text,
            "update_tick": int(current_time),
            # Send next track info so frontend can trigger pre-generation
            "next_track": next_track 
        }
        spotify_cache["data"] = response_data
        return jsonify(response_data)
    
    empty_state = {"playing": False}
    spotify_cache["data"] = empty_state
    return jsonify(empty_state)

# --- CONTROLS ---
@app.route('/api/next', methods=['POST'])
def next_track():
    spotify.next_track()
    invalidate_cache() 
    return jsonify({"status": "ok"})

@app.route('/api/previous', methods=['POST'])
def previous_track():
    spotify.previous_track()
    invalidate_cache()
    return jsonify({"status": "ok"})

@app.route('/api/pause', methods=['POST'])
def pause_track():
    spotify.pause_playback()
    invalidate_cache()
    return jsonify({"status": "ok"})

@app.route('/api/play', methods=['POST'])
def play_track():
    spotify.start_playback()
    invalidate_cache()
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)