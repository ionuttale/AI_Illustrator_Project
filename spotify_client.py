import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from dotenv import load_dotenv

load_dotenv()

class SpotifyHandler:
    def __init__(self):
        self.scope = "user-read-currently-playing user-read-playback-state user-modify-playback-state"
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("REDIRECT_URI"),
            scope=self.scope
        ))

    def get_current_track(self):
        """Fetches current track metadata including sync and genre info."""
        item = self.sp.current_user_playing_track()
        if not item or not item['item']: 
            return None

        track = item['item']
        artist_id = track['artists'][0]['id']
        
        try:
            artist_info = self.sp.artist(artist_id)
            genres = artist_info.get('genres', [])
        except:
            genres = ["music"]

        return {
            'id': track['id'],
            'title': track['name'],
            'artist': track['artists'][0]['name'],
            'album_art': track['album']['images'][0]['url'],
            'genres': genres,
            'progress_ms': item.get('progress_ms', 0),
            'is_playing': item.get('is_playing', False),
            'duration_ms': track['duration_ms'] # <--- Added for LRCLIB
        }

    def get_queue(self):
        try:
            queue_data = self.sp.queue()
            if queue_data and 'queue' in queue_data and len(queue_data['queue']) > 0:
                next_track = queue_data['queue'][0]
                return {
                    'id': next_track['id'],
                    'title': next_track['name'],
                    'artist': next_track['artists'][0]['name']
                }
            return None
        except Exception as e:
            print(f"Error fetching queue: {e}")
            return None

    def next_track(self): self.sp.next_track()
    def previous_track(self): self.sp.previous_track()
    def pause_playback(self): self.sp.pause_playback()
    def start_playback(self): self.sp.start_playback()