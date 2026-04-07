from services.llm_client import call_llm_json


async def generate_business_context(topic: str) -> dict:
    system_prompt = """
You are a startup strategist.

Convert the given idea into a REAL, CONCRETE startup.

Return STRICT JSON:

{
  "product_name": "",
  "product_type": "",
  "target_user": "",
  "problem": "",
  "solution": "",
  "key_features": [],
  "market": "",
  "monetization": "",
  "differentiation": ""
}

Rules:
- Must be realistic
- No abstract words like "system" without explanation
- Each field must be filled
- Think like investor pitch
"""

    user_prompt = f"Idea: {topic}"

    result = await call_llm_json(system_prompt, user_prompt)

    # HARD VALIDATION
    required = [
        "product_name",
        "product_type",
        "target_user",
        "problem",
        "solution",
        "key_features",
        "market",
        "monetization",
        "differentiation"
    ]

    for key in required:
        if key not in result or not result[key]:
            raise ValueError(f"Missing: {key}")

    return result