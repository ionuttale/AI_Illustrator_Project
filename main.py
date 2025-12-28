import time
import datetime
import concurrent.futures
from spotipy.exceptions import SpotifyException
from spotify_client import SpotifyHandler
from lyrics_provider import FreeLyricsHandler
from translator_service import TranslatorService
from image_generator import ImageGenerator
import os
import requests
import json

LOG_FILE = "generated_prompts.jsonl"

def fetch_lyrics_task(lyrics_engine, track):
    return lyrics_engine.get_lyrics_for_queue(track, [])

def get_target_resolution(track_id):
    # Tries to get resolution from Flask app, defaults to 512x512
    try:
        res_req = requests.get(f"http://127.0.0.1:5000/api/get_resolution/{track_id}", timeout=0.5)
        res_data = res_req.json()
        return res_data.get("width", 512), res_data.get("height", 512)
    except:
        return 512, 512

def log_track_info(track, prompt, visual_desc, lyrics, output_path):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        "timestamp": timestamp,
        "track_id": track["id"],
        "title": track["title"],
        "artist": track["artist"],
        "prompt": prompt,
        "output_image": output_path
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def process_track(track, spotify, lyrics_engine, translator, generator, is_pregeneration=False):
    """Core logic to generate art for a single track."""
    track_id = track['id']
    output_path = f"art_output/{track_id}.png"

    # Skip if already exists
    if os.path.exists(output_path):
        return

    prefix = "🔮 [PRE-GEN]" if is_pregeneration else "🎵 [NOW PLAYING]"
    print(f"\n{prefix} Processing: {track['title']} by {track['artist']}")

    # 1. Fetch Lyrics
    lyrics = ""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_lyrics_task, lyrics_engine, track)
            lyrics = future.result(timeout=6).get("current", "")
    except Exception as e:
        print(f"⚠️ Lyrics fetch error: {e}")

    if not lyrics:
        genres = track.get("genres", [])
        lyrics = f"{track['title']} {' '.join(genres) if genres else ''}"

    # 2. Generate Prompt
    print(f"🧠 Generating AI prompt for {track['title']}...")
    prompt, visual_desc, _ = translator.create_smart_prompt(
        track["title"],
        track["artist"],
        lyrics,
        track.get("genres", [])
    )

    # 3. Get Resolution (If pre-generating, we might not have custom dims yet, so default is safe)
    width, height = get_target_resolution(track_id)

    # 4. Generate Image
    print(f"🎨 Generating image ({width}x{height})...")
    start_time = time.time()
    generator.generate_image(
        prompt,
        track_id,
        album_art_url=track.get("album_art"),
        width=width,
        height=height
    )
    print(f"✅ Image saved in {time.time() - start_time:.1f}s")
    
    log_track_info(track, prompt, visual_desc, lyrics, output_path)

def main():
    print("🚀 Initializing AI Services...")
    try:
        spotify = SpotifyHandler()
        lyrics_engine = FreeLyricsHandler()
        translator = TranslatorService()
        generator = ImageGenerator()
        print("✅ Services Ready. Waiting for Spotify...")
    except Exception as e:
        print(f"❌ Initialization Error: {e}")
        return

    current_track_id = None
    default_sleep = 5 

    while True:
        try:
            # --- 1. PRIORITY: Handle Current Track ---
            try:
                current = spotify.get_current_track()
            except SpotifyException as e:
                if e.http_status == 429:
                    print(f"⏳ Rate limited. Sleeping...")
                    time.sleep(int(e.headers.get("Retry-After", 10)))
                    continue
                else:
                    raise

            if current:
                current_track_id = current['id']
                # Process the current track immediately if missing
                process_track(current, spotify, lyrics_engine, translator, generator, is_pregeneration=False)
            else:
                current_track_id = None

            # --- 2. SECONDARY: Handle Next Track (Look Ahead) ---
            # Only look ahead if we successfully processed the current one (or nothing is playing)
            try:
                # We reuse the method we added to spotify_client.py
                next_track_info = spotify.get_queue() 
                if next_track_info:
                    # We need to reshape the simple queue data into the full track object expected by process_track
                    # Note: get_queue usually returns minimal info, we might need to fetch full audio features
                    # But for now, we pass what we have.
                    
                    # Check if next track is different from current and not generated
                    next_output = f"art_output/{next_track_info['id']}.png"
                    if next_track_info['id'] != current_track_id and not os.path.exists(next_output):
                        print(f"👀 Peeking at next song: {next_track_info['title']}")
                        
                        # Enhance data (get genres/album art) because queue object is often sparse
                        full_next_track = spotify.sp.track(next_track_info['id'])
                        
                        # Extract necessary fields to match 'current' object structure
                        track_obj = {
                            "id": full_next_track['id'],
                            "title": full_next_track['name'],
                            "artist": full_next_track['artists'][0]['name'],
                            "album_art": full_next_track['album']['images'][0]['url'] if full_next_track['album']['images'] else None,
                            "genres": [] # Optimisation: Skip genre fetch for pre-gen to save API calls
                        }
                        
                        process_track(track_obj, spotify, lyrics_engine, translator, generator, is_pregeneration=True)
            except Exception as e:
                # Don't let queue errors crash the main loop
                print(f"⚠️ Queue check skipped: {e}")

        except KeyboardInterrupt:
            print("\n🛑 Stopping services...")
            break
        except Exception as e:
            print(f"⚠️ Runtime loop error: {e}")
            time.sleep(default_sleep)

        time.sleep(default_sleep)

if __name__ == "__main__":
    main()