import httpx
from config import settings

async def fetch_image(query: str) -> str | None:
    """Returns local file path of downloaded image, or None on failure."""
    import os, uuid
    os.makedirs(settings.output_dir, exist_ok=True)

    if settings.image_provider in ("unsplash", "both"):
        url = await _fetch_unsplash(query)
    elif settings.image_provider == "pexels":
        url = await _fetch_pexels(query)
    else:
        return None

    if not url:
        url = await _fetch_pexels(query)  # fallback

    if not url:
        return None

    return await _download_image(url)

async def _fetch_unsplash(query: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 1, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"}
            )
            data = r.json()
            return data["results"][0]["urls"]["regular"] if data["results"] else None
    except Exception:
        return None

async def _fetch_pexels(query: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 1, "orientation": "landscape"},
                headers={"Authorization": settings.pexels_api_key}
            )
            data = r.json()
            return data["photos"][0]["src"]["large"] if data.get("photos") else None
    except Exception:
        return None

async def _download_image(url: str) -> str | None:
    import uuid
    path = f"{settings.output_dir}/{uuid.uuid4().hex}.jpg"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            with open(path, "wb") as f:
                f.write(r.content)
        return path
    except Exception:
        return None