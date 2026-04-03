from services.llm_client import call_llm_json

async def parse_prompt(prompt: str) -> dict:
    system = """You are a presentation analyst. Extract structured signals from a user's prompt.
Return JSON with these fields:
- topic (string)
- presentation_type: "pitch" | "educational" | "report" | "general"
- slide_count (int or null)
- sections (list of strings or null)
- tone: "professional" | "casual" | "inspiring" | "academic" or null
- audience (string or null)
- examples_count (int or null)
- image_preference (bool, default true)
- language (ISO 639-1 code, default "en")"""

    return await call_llm_json(system, f"User prompt: {prompt}")