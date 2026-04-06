import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure backend sits on sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

load_dotenv(backend_dir.parent / ".env")

import logging
logging.basicConfig(level=logging.INFO)

from pipeline.dynamic_composition_engine import generate_slide_html

async def main():
    slide_data = {
        "intent": "Highlight the dramatic improvement in our user retention metrics.",
        "content": "In Q3 of 2023, we performed a thorough analysis of our user funnel. The data showed that our new onboarding flow resulted in 27% fewer exits on the first page, and users completed their profiles 18% faster overall. This indicates a drastic improvement in user friction. Furthermore, the overall user satisfaction score increased from 4.2 to 4.8."
    }
    
    print("Testing generate_slide_html...")
    theme_dict = {
        "background": "dark",
        "primary_color": "vibrant blue",
        "font_scale": "massive headers",
        "spacing_scale": "cozy"
    }
    continuity_context = {"global_keywords": [], "entities": []}
    design, html, context = await generate_slide_html(slide_data, 0, theme_dict, continuity_context)
    
    print("\n--- DESIGN SPEC ---")
    print(design)
    print("\n--- FINAL HTML ---\n")
    print(html)

if __name__ == "__main__":
    asyncio.run(main())
