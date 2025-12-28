import torch
from diffusers import StableDiffusionImg2ImgPipeline, DEISMultistepScheduler
from PIL import Image, ImageFilter
import requests
from io import BytesIO
import os

class ImageGenerator:
    def __init__(self):
        print("DEBUG: Loading DreamShaper 8 (High Quality Model)...")
        self.pipe = StableDiffusionImg2ImgPipeline.from_pretrained(
            "Lykon/dreamshaper-8",
            torch_dtype=torch.float16,
            variant="fp16"
        ).to("cuda")
        
        self.pipe.scheduler = DEISMultistepScheduler.from_config(self.pipe.scheduler.config)
        self.pipe.safety_checker = None
        self.pipe.requires_safety_checker = False

    def generate_image(self, smart_prompt, track_id, album_art_url=None, width=512, height=512):
        try:
            response = requests.get(album_art_url, timeout=5)
            init_image = Image.open(BytesIO(response.content)).convert("RGB")
        except:
            init_image = Image.new('RGB', (width, height), color='black')

        # Heavy Blur = Creative Freedom
        # We give Llama's prompt the power to shape the image, using only the *colors* of the original album.
        init_image = init_image.resize((width, height)).filter(ImageFilter.GaussianBlur(50))

        print(f"DEBUG: Generating {width}x{height} | Prompt: {smart_prompt[:50]}...")
        
        with torch.inference_mode():
            image = self.pipe(
                prompt=smart_prompt,
                negative_prompt="text, watermark, ugly, deformed, bad anatomy, blurry, low quality, cartoon, sketch, amateur, grain, disfigured",
                image=init_image,
                strength=0.85, # High strength to follow the Llama prompt closely
                guidance_scale=7.5, 
                width=width,
                height=height,
                num_inference_steps=30
            ).images[0]

        os.makedirs("art_output", exist_ok=True)
        image.save(f"art_output/{track_id}.png")