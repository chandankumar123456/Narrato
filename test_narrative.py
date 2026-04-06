import asyncio
import os
import sys

# Change dir to backend to ensure imports work
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from backend.orchestrator import run_pipeline

async def main():
    options = {
        "presentation_type": "startup_pitch",
        "audience": "investors",
        "tone": "confident",
        "slide_count": 7,
    }
    
    print("Running pipeline...")
    result = await run_pipeline("A new AI presentation tool", options=options)
    
    print("Success!")
    print(f"Generated {len(result['html_slides'])} slides.")
    print("First slide intent:")
    print(result['structured_slides'][0].get('intent', 'no intent found'))

if __name__ == "__main__":
    asyncio.run(main())
