import os
import re
import requests
import json

CACHE_FILE = "lyrics_cache.json"

class FreeLyricsHandler:
    def __init__(self):
        # Persistent cache
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
        except:
            self.cache = {}

    def save_cache(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def _clean(self, s):
        """Clean artist/title strings for safe URLs."""
        return re.sub(r"[^\w\s\-']", "", s).strip()

    def _try_lyrics_ovh(self, title, artist):
        """Fetch lyrics from Lyrics.ovh."""
        try:
            artist_clean = self._clean(artist).replace(" ", "%20")
            title_clean = self._clean(title).replace(" ", "%20")
            url = f"https://api.lyrics.ovh/v1/{artist_clean}/{title_clean}"
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                return r.json().get("lyrics", "")
            return ""
        except:
            return ""

    def _fetch_single(self, track):
        t_id = track.get("id", "unknown")
        if t_id in self.cache:
            return t_id, self.cache[t_id]

        title = track.get("title", "")
        artist = track.get("artist", "")
        lyrics = ""

        if title and artist:
            lyrics = self._try_lyrics_ovh(title, artist)

        self.cache[t_id] = lyrics
        self.save_cache()
        return t_id, lyrics

    def get_lyrics_for_queue(self, current_track, upcoming_queue=None):
        results = {"current": "", "queue": {}}
        all_tracks = []
        if current_track: all_tracks.append(current_track)
        if upcoming_queue: all_tracks.extend(upcoming_queue)

        for track in all_tracks:
            t_id, text = self._fetch_single(track)
            if current_track and t_id == current_track["id"]:
                results["current"] = text
            else:
                results["queue"][t_id] = text

        return results
