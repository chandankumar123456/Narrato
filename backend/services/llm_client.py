import json
from config import settings

async def call_llm(system_prompt: str, user_prompt: str) -> str:
    if settings.llm_provider == "openai":
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content

    elif settings.llm_provider == "anthropic":
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model=settings.llm_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text

async def call_llm_json(system_prompt: str, user_prompt: str) -> dict:
    """Always returns parsed JSON — raises ValueError on parse failure."""
    raw = await call_llm(
        system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no backticks, no preamble.",
        user_prompt
    )
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {raw}")