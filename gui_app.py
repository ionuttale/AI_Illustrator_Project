import tkinter as tk
from PIL import Image, ImageTk, ImageOps
import threading
import time
import os
import requests
from io import BytesIO

# Import your existing modules
from spotify_client import SpotifyHandler
from lyrics_provider import FreeLyricsHandler
from translator_service import TranslatorService
from image_generator import ImageGenerator

class SpotifyAIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Spotify AI Art")
        self.root.configure(bg="black")

        # --- 1. DETECT SCREEN RESOLUTION ---
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # Start in Fullscreen
        self.root.attributes('-fullscreen', True)
        
        # Bind Escape key to exit fullscreen/app
        self.root.bind("<Escape>", self.exit_app)
        self.root.bind("<Configure>", self.on_resize)

        # --- State Variables ---
        self.is_playing = False
        self.running = True
        # Initial placeholder: Black screen sized to monitor
        self.current_image_pil = Image.new('RGB', (self.screen_width, self.screen_height), "#000000")
        self.photo_ref = None 

        # --- UI Setup (Canvas) ---
        self.setup_canvas_ui()
        
        # --- Start Backend ---
        print(f"🚀 Detected Screen: {self.screen_width}x{self.screen_height}")
        threading.Thread(target=self.init_services, daemon=True).start()

    def exit_app(self, event=None):
        self.running = False
        self.root.destroy()

    def setup_canvas_ui(self):
        # Canvas fills the screen
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Background Image Layer
        self.bg_item = self.canvas.create_image(0, 0, anchor="nw", image=None, tags="bg")

        # --- Info Layer (Top Left) ---
        # Added a drop shadow effect for better readability
        self.title_shadow = self.canvas.create_text(52, 52, text="Initializing...", font=("Arial", 30, "bold"), fill="black", anchor="nw")
        self.title_item = self.canvas.create_text(50, 50, text="Initializing...", font=("Arial", 30, "bold"), fill="white", anchor="nw")
        
        self.artist_shadow = self.canvas.create_text(52, 102, text="", font=("Arial", 20), fill="black", anchor="nw")
        self.artist_item = self.canvas.create_text(50, 100, text="", font=("Arial", 20), fill="#dddddd", anchor="nw")

        # --- Controls Layer (Bottom Center) ---
        self.create_controls()

    def create_controls(self):
        # Calculate center positions based on screen size
        cx = self.screen_width / 2
        cy = self.screen_height - 120
        
        # Button styles (Unicode icons)
        # Prev
        self.canvas.create_text(cx - 100, cy, text="⏮", font=("Arial", 50), fill="white", tags=("btn", "prev"), activefill="#1DB954")
        # Play/Pause
        self.play_btn = self.canvas.create_text(cx, cy, text="▶", font=("Arial", 70), fill="white", tags=("btn", "play"), activefill="#1DB954")
        # Next
        self.canvas.create_text(cx + 100, cy, text="⏭", font=("Arial", 50), fill="white", tags=("btn", "next"), activefill="#1DB954")

        # Bindings
        self.canvas.tag_bind("prev", "<Button-1>", lambda e: self.prev_track())
        self.canvas.tag_bind("play", "<Button-1>", lambda e: self.toggle_play())
        self.canvas.tag_bind("next", "<Button-1>", lambda e: self.next_track())
        
        # Cursor hover effect
        self.canvas.tag_bind("btn", "<Enter>", lambda e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind("btn", "<Leave>", lambda e: self.canvas.config(cursor=""))

    def init_services(self):
        try:
            self.spotify = SpotifyHandler()
            self.lyrics_engine = FreeLyricsHandler()
            self.translator = TranslatorService()
            self.generator = ImageGenerator()
            threading.Thread(target=self.main_loop, daemon=True).start()
        except Exception as e:
            print(f"Init Error: {e}")

    def on_resize(self, event=None):
        """Ensures image covers the screen perfectly."""
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        
        # Resize current image to fit window exactly
        resized = ImageOps.fit(self.current_image_pil, (w, h), method=Image.Resampling.LANCZOS)
        self.photo_ref = ImageTk.PhotoImage(resized)
        
        self.canvas.itemconfig(self.bg_item, image=self.photo_ref)
        self.canvas.tag_lower("bg") # Keep image behind text

        # Update control positions in case window size changes
        cx = w / 2
        cy = h - 120
        # (Updating individual items by tag/id if needed, simplified here)

    def calculate_generation_dims(self):
        """
        Calculates optimal generation dimensions based on screen aspect ratio.
        Stable Diffusion works best around 512-1024px.
        We scale the resolution down to keep the ratio but save GPU time.
        """
        screen_ratio = self.screen_width / self.screen_height
        
        # Base size for the long edge (Higher = sharper but slower)
        # 1024 is a good balance for modern SD models.
        long_edge = 1024 

        if screen_ratio > 1: # Landscape
            width = long_edge
            height = int(long_edge / screen_ratio)
        else: # Portrait
            height = long_edge
            width = int(long_edge * screen_ratio)

        # Dimensions must be multiples of 8 for Stable Diffusion
        width = (width // 8) * 8
        height = (height // 8) * 8
        
        print(f"📏 Screen: {self.screen_width}x{self.screen_height} | Generating at: {width}x{height} (Ratio Preserved)")
        return width, height

    def update_image_display(self, image_path_or_url, is_url=False):
        try:
            if image_path_or_url is None:
                self.current_image_pil = Image.new('RGB', (self.screen_width, self.screen_height), "#000000")
            elif is_url:
                response = requests.get(image_path_or_url, timeout=5)
                self.current_image_pil = Image.open(BytesIO(response.content))
            else:
                self.current_image_pil = Image.open(image_path_or_url)
            
            # Apply dark overlay for text readability
            overlay = Image.new('RGBA', self.current_image_pil.size, (0,0,0,80))
            self.current_image_pil = Image.alpha_composite(self.current_image_pil.convert('RGBA'), overlay).convert('RGB')

            self.root.after(0, self.on_resize)
        except Exception as e:
            print(f"Image load error: {e}")

    def update_info(self, title, artist):
        self.root.after(0, lambda: self._update_text(title, artist))

    def _update_text(self, title, artist):
        self.canvas.itemconfig(self.title_item, text=title)
        self.canvas.itemconfig(self.title_shadow, text=title)
        self.canvas.itemconfig(self.artist_item, text=artist)
        self.canvas.itemconfig(self.artist_shadow, text=artist)

    def _update_play_icon(self):
        icon = "⏸" if self.is_playing else "▶"
        self.canvas.itemconfig(self.play_btn, text=icon)

    # --- MAIN LOOP ---
    def main_loop(self):
        last_track_id = None
        while self.running:
            try:
                current = self.spotify.get_current_track()
                if not current:
                    time.sleep(2)
                    continue

                self.is_playing = current.get('is_playing', False)
                self.root.after(0, self._update_play_icon)

                if current['id'] != last_track_id:
                    last_track_id = current['id']
                    self.handle_track_change(current)
                
                time.sleep(1)
            except Exception as e:
                print(f"Loop error: {e}")
                time.sleep(5)

    def handle_track_change(self, track):
        self.update_info(track['title'], track['artist'])
        
        # 1. Show Official Album Art first (Instant feedback)
        if track.get('album_art'):
            self.update_image_display(track['album_art'], is_url=True)

        # 2. Check if AI Art exists
        output_path = f"art_output/{track['id']}.png"
        if os.path.exists(output_path):
            self.update_image_display(output_path)
            return

        # 3. Generate New Art
        self.generate_new_art(track, output_path)

    def generate_new_art(self, track, output_path):
        # Fetch Lyrics (simplified)
        try:
            lyrics = self.lyrics_engine.get_lyrics_for_queue(track, []).get("current", "")
        except: lyrics = ""
        
        if not lyrics: 
            genres = track.get("genres", [])
            lyrics = f"{track['title']} {' '.join(genres) if genres else ''}"

        # Get Prompt
        prompt, _, _ = self.translator.create_smart_prompt(track["title"], track["artist"], lyrics, track.get("genres", []))

        # --- DYNAMIC RESOLUTION ---
        gen_w, gen_h = self.calculate_generation_dims()

        try:
            self.generator.generate_image(
                prompt,
                track['id'],
                album_art_url=track.get("album_art"),
                width=gen_w, 
                height=gen_h
            )
            self.update_image_display(output_path)
        except Exception as e:
            print(f"Generation Failed: {e}")

    # --- Controls ---
    def toggle_play(self):
        if self.is_playing: self.spotify.pause_playback()
        else: self.spotify.start_playback()
        self.is_playing = not self.is_playing
        self._update_play_icon()
    
    def next_track(self): self.spotify.next_track()
    def prev_track(self): self.spotify.previous_track()

if __name__ == "__main__":
    os.makedirs("art_output", exist_ok=True)
    root = tk.Tk()
    app = SpotifyAIApp(root)
    root.mainloop()