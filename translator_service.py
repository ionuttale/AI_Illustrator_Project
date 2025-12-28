import ollama
from deep_translator import GoogleTranslator
from datetime import datetime
import re
import json

class TranslatorService:
    def __init__(self):
        self.translator = GoogleTranslator(source='auto', target='en')
        self.model = "llama3.2" 

    # -------- PASS 1: FEATURE & PHRASE EXTRACTION --------
    def _extract_song_features(self, title, artist, lyrics, genres_list):
        """
        Extracts structured data, focusing on meaningful lyrical phrases.
        """
        snippet = lyrics[:1200]
        genres_str = ", ".join(genres_list) if genres_list else "Unknown Genre"

        prompt = f"""
Analyze the song "{title}" by "{artist}".
Genres: {genres_str}
Lyrics Snippet: "{snippet}..."

TASK: Extract technical details and the most visual METAPHORICAL SENTENCES.
RETURN STRICTLY IN THIS FORMAT:
SINGER_GENDER: (Male / Female / Unknown)
SUBJECT_GENDER: (Male / Female / Unknown / None)
MOOD: (e.g. Melancholic, Euphoric, Aggressive, Dreamy)
KEY_PHRASES: (Extract 3 short, vivid phrases or sentences from the lyrics that paint a picture. Do not pick single words. Example: "Walking down a boulevard of broken dreams", "The sky is crying tears of rain")
SETTING: (e.g. Urban night, Forest, Void, Bedroom)
"""
        try:
            # Low temperature for precise extraction
            response = ollama.generate(
                model=self.model, prompt=prompt, stream=False, options={"temperature": 0.3}
            )
            return response["response"].strip()
        except Exception as e:
            print(f"Ollama Error (Features): {e}")
            return "SINGER_GENDER: Unknown\nSUBJECT_GENDER: Unknown\nMOOD: Dreamy\nKEY_PHRASES: Lost in the music\nSETTING: Void"

    # -------- PASS 2: VISUAL SYNTHESIS --------
    def _generate_cinematic_prompt(self, features):
        """
        Converts the specific lyric phrases into a cohesive visual description.
        """
        prompt = f"""
You are an expert AI Art Director.
DATA:
{features}

TASK: Create a Single, Cinematic Visual based on the KEY_PHRASES.
1. Combine the KEY_PHRASES into one surreal, metaphorical scene.
2. Apply the OPPOSITE GENDER RULE:
   - If SINGER is Male & SUBJECT is Female -> Visualize a mystical FEMALE figure.
   - If SINGER is Female & SUBJECT is Male -> Visualize a mystical MALE figure.
   - If genders are same or unknown -> Visualize the SETTING and PHRASES abstractly (no humans).
3. STYLE: Blurry, Cinematic, Emotional, Ethereal.

OUTPUT FORMAT (STRICT):
VISUAL: [A single sentence describing the scene, max 20 words]
"""
        try:
            # Higher temperature to creatively blend the phrases
            response = ollama.generate(
                model=self.model, prompt=prompt, stream=False, options={"temperature": 0.8}
            )
            return response["response"].strip()
        except Exception as e:
            return "VISUAL: A blurred silhouette wandering through a dream"

    # -------- MAIN METHOD --------
    def create_smart_prompt(self, title, artist, full_lyrics, genres):
        # 1. Translate
        try:
            en_lyrics = self.translator.translate(full_lyrics[:2000])
        except:
            en_lyrics = full_lyrics

        # 2. EXTRACT FEATURES (Pass 1)
        print(f"🧠 Analyzing features for '{title}'...")
        features_raw = self._extract_song_features(title, artist, en_lyrics, genres)
        
        # 3. GENERATE VISUAL (Pass 2)
        visual_raw = self._generate_cinematic_prompt(features_raw)

        # 4. Parse & Assemble
        visual_desc = "Abstract cinematic dream"
        visual_match = re.search(r"VISUAL:\s*(.*)", visual_raw, re.IGNORECASE)
        if visual_match:
            visual_desc = visual_match.group(1).strip().rstrip(".")

        # Extract Mood for the style stack
        mood = "Emotional"
        mood_match = re.search(r"MOOD:\s*(.*)", features_raw, re.IGNORECASE)
        if mood_match:
            mood = mood_match.group(1).strip()

        # 5. Final Prompt Construction
        # We place the visual description first, followed by the specific mood.
        final_prompt = (
            f"{visual_desc}, {mood} atmosphere, "
            "motion blur, soft focus, film grain, dreamlike, "
            "cinematic lighting, shallow depth of field, 8k, masterpiece"
        )

        # 6. Logging
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\nTIMESTAMP: {timestamp}")
        print(f"TRACK: {title}")
        print(f"EXTRACTED DATA:\n{features_raw}")
        print(f"GENERATED VISUAL: {visual_desc}")
        print(f"FINAL PROMPT: {final_prompt}\n")

        return final_prompt, features_raw, en_lyrics