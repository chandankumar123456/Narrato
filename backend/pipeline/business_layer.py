from services.llm_client import call_llm_json


async def generate_business_context(topic: str) -> dict:
    system_prompt = """
You are a startup strategist.

Convert the idea into a REAL investor-ready startup.

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
  "pricing": "",
  "revenue_projection": "",
  "competition": "",
  "differentiation": ""
}

RULES:
- Must be concrete
- Must include NUMBERS where possible
- Pricing must include actual values (e.g. $20/month, enterprise tiers)
- Revenue must include projections (e.g. $1M ARR in 2 years)
- Competition must name real alternatives (BI tools, dashboards, etc.)
- Differentiation must clearly say WHY better
- No abstract language
"""

    user_prompt = f"Idea: {topic}"

    result = await call_llm_json(system_prompt, user_prompt)

    required = [
        "product_name",
        "product_type",
        "target_user",
        "problem",
        "solution",
        "key_features",
        "market",
        "monetization",
        "pricing",
        "revenue_projection",
        "competition",
        "differentiation"
    ]

    for key in required:
        if key not in result or not result[key]:
            raise ValueError(f"Missing: {key}")

    return result