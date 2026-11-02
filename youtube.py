import os
import asyncio
import aiohttp
from youtube_search import YoutubeSearch

# --- PRIMARY API (Nexor) ---
NEXOR_STREAM_URL = os.environ.get("NEXOR_STREAM_URL", "https://nexor-yt-pannl.lovable.app")
NEXOR_STREAM_KEY = os.environ.get("NEXOR_STREAM_KEY", "NEXOR_3481fsghsh62ghs")

# --- FALLBACK API (Yuki API - backup ke liye) ---
YUKI_API_URL = "https://yuki-api.onrender.com/download/ytmp3"

DOWNLOAD_TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT", "180"))


async def search_youtube(query: str):
    """YouTube pe search karta hai, pehla result deta hai (raw dict, library format)."""
    loop = asyncio.get_event_loop()

    def _search():
        results = YoutubeSearch(query, max_results=1).to_dict()
        return results[0] if results else None

    return await loop.run_in_executor(None, _search)


async def search_track(query: str):
    """search_youtube ka normalized wrapper — id/title/duration/thumbnail/url deta hai."""
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
    """API se gaana download/ready nahi ho paya."""


def _video_id(video: str) -> str:
    """Poora YouTube link ya id — dono se sirf video id nikalta hai (API ko id chahiye)."""
    video = (video or "").strip()
    if not video:
        return ""
    if "youtu.be/" in video:
        video = video.split("youtu.be/")[1]
    elif "v=" in video:
        video = video.split("v=")[1]
    elif "/shorts/" in video:
        video = video.split("/shorts/")[1]
    elif "/embed/" in video:
        video = video.split("/embed/")[1]
    for sep in ("?", "&", "/", "#"):
        video = video.split(sep)[0]
    return video


async def get_stream_url(video: str) -> str:
    """
    Pehle Nexor API try karega. Agar wahan 502/Error aaya, toh 
    automatically Yuki API (Fallback) se link nikalega.
    """
    video_id = _video_id(video)
    if not video_id:
        raise DownloadError("Video id nahi mila")

    # ==========================================
    # 1. TRY PRIMARY API (Nexor)
    # ==========================================
    nexor_url = f"{NEXOR_STREAM_URL}/stream/{video_id}?key={NEXOR_STREAM_KEY}"
    timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, sock_connect=30)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(nexor_url) as resp:
                if resp.status == 200:
                    return nexor_url # Agar Nexor theek hai toh seedha return kar do
                else:
                    print(f"[WARNING] Nexor API ne status {resp.status} diya. Fallback par ja rahe hain...")
    except Exception as e:
        print(f"[WARNING] Nexor API fail hui: {e}. Fallback par ja rahe hain...")


    # ==========================================
    # 2. FALLBACK API (Yuki) - Agar Nexor down hai
    # ==========================================
    try:
        print(f"[INFO] Fallback API se stream nikal rahe hain: {video_id}")
        fallback_url = f"{YUKI_API_URL}?url=https://youtu.be/{video_id}"
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(fallback_url) as resp:
                if resp.status != 200:
                    raise DownloadError(f"Fallback API ne bhi error diya: {resp.status}")
                
                data = await resp.json()
                # Yuki API ka response check karein
                if data.get("status") and data.get("download_url"):
                    return data["download_url"]
                else:
                    raise DownloadError("Fallback API se valid link nahi mila")

    except Exception as e:
        # Agar dono API fail ho jayein toh error raise karein
        raise DownloadError(f"Dono API fail ho gayi. Last error: {e}")


async def get_related_track(title: str, exclude_id: str = None):
    """
    Autoplay ke liye — current gaane ke naam se milta-julta agla gaana dhoondta
    hai (youtube ke autoplay jaisa). Same video dobara na aaye iske liye
    `exclude_id` skip kar diya jaata hai.
    """
    loop = asyncio.get_event_loop()
    base = (title or "").split("|")[0].split("(")[0].strip()
    if not base:
        return None

    def _search():
        try:
            return YoutubeSearch(f"{base} song", max_results=8).to_dict()
        except Exception:
            return []

    results = await loop.run_in_executor(None, _search)
    for result in results or []:
        video_id = result.get("id")
        if not video_id or video_id == exclude_id:
            continue
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
