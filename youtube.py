import os
import asyncio
import aiohttp
from youtube_search import YoutubeSearch

# --- PRIMARY API (Nexor) ---
NEXOR_STREAM_URL = os.environ.get("NEXOR_STREAM_URL", "https://nexor-yt-pannl.lovable.app")
NEXOR_STREAM_KEY = os.environ.get("NEXOR_STREAM_KEY", "NEXOR_3481fsghsh62ghs")

# --- NEW FALLBACK API (Paxsenix) ---
PAXSENIX_API = "https://api.paxsenix.biz.id/dl/ytmp3"

DOWNLOAD_TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT", "180"))

async def search_youtube(query: str):
    loop = asyncio.get_event_loop()
    def _search():
        results = YoutubeSearch(query, max_results=1).to_dict()
        return results[0] if results else None
    return await loop.run_in_executor(None, _search)

async def search_track(query: str):
    result = await search_youtube(query)
    if not result:
        return None
    thumbnails = result.get("thumbnails") or []
    video_id = result.get("id")
    return {
        "id": video_id,
        "title": result.get("title", "Unknown"),
        "duration": result.get("duration", ""),
        "thumbnail": thumbnails[0] if thumbnails else None,
        "channel": result.get("channel") or result.get("uploader") or "",
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
    }

class DownloadError(Exception):
    pass

def _video_id(video: str) -> str:
    video = (video or "").strip()
    if not video: return ""
    if "youtu.be/" in video: video = video.split("youtu.be/")[1]
    elif "v=" in video: video = video.split("v=")[1]
    elif "/shorts/" in video: video = video.split("/shorts/")[1]
    elif "/embed/" in video: video = video.split("/embed/")[1]
    for sep in ("?", "&", "/", "#"): video = video.split(sep)[0]
    return video

async def get_stream_url(video: str) -> str:
    video_id = _video_id(video)
    if not video_id: raise DownloadError("Video id nahi mila")

    timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, sock_connect=30)

    # 1. TRY NEXOR API
    nexor_url = f"{NEXOR_STREAM_URL}/stream/{video_id}?key={NEXOR_STREAM_KEY}"
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(nexor_url) as resp:
                if resp.status == 200:
                    return nexor_url 
    except Exception:
        pass # Nexor fail hua, ab fallback chalega

    # 2. TRY PAXSENIX FALLBACK API
    try:
        fallback_url = f"{PAXSENIX_API}?url=https://youtu.be/{video_id}"
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(fallback_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Paxsenix ka response format check karna
                    if data.get("status") and data.get("result", {}).get("url"):
                        return data["result"]["url"]
    except Exception:
        pass

    raise DownloadError("Dono API fail ho gayi.")

async def get_related_track(title: str, exclude_id: str = None):
    loop = asyncio.get_event_loop()
    base = (title or "").split("|")[0].split("(")[0].strip()
    if not base: return None
    def _search():
        try: return YoutubeSearch(f"{base} song", max_results=8).to_dict()
        except: return []
    results = await loop.run_in_executor(None, _search)
    for result in results or []:
        video_id = result.get("id")
        if not video_id or video_id == exclude_id: continue
        thumbnails = result.get("thumbnails") or []
        return {
            "id": video_id,
            "title": result.get("title", "Unknown"),
            "duration": result.get("duration", ""),
            "thumbnail": thumbnails[0] if thumbnails else None,
            "channel": result.get("channel") or result.get("uploader") or "",
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
    return None
