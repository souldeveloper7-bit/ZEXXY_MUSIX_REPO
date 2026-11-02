import aiohttp
from urllib.parse import quote

# Aapki API ka base URL
API_BASE_URL = "https://jiosavanapiryden.vercel.app/api"

class DownloadError(Exception):
    """Gaana load nahi ho paya."""

async def search_track(query: str):
    """
    Aapki API se search karke pehla result return karta hai.
    """
    url = f"{API_BASE_URL}/search/songs"
    params = {"query": query, "page": 0, "limit": 1}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=15) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                
                if not data.get("success"):
                    return None
                
                songs = data.get("data", {}).get("results", [])
                if not songs:
                    return None
                
                song = songs[0]
                # Duration ko seconds se format karein (jaise 245 -> "4:05")
                duration_sec = song.get("duration", 0)
                duration_str = f"{duration_sec // 60}:{duration_sec % 60:02d}"
                
                return {
                    "id": song.get("id"),
                    "title": song.get("name", "Unknown"),
                    "duration": duration_str,
                    "thumbnail": song.get("image", [{}])[-1].get("url", ""), # Best quality thumbnail
                    "channel": ", ".join([a.get("name", "") for a in song.get("artists", {}).get("primary", [])]),
                    "url": f"https://www.jiosaavn.com/song/{song.get('id')}", # Optional
                }
    except Exception as e:
        print(f"Search error: {e}")
        return None

async def get_stream_url(video: str) -> str:
    """
    Aapki API se song ID ke through direct stream URL nikalta hai.
    """
    # Agar video variable mein pehle se ID hai
    song_id = video
    
    url = f"{API_BASE_URL}/songs/{song_id}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=30) as resp:
                if resp.status != 200:
                    raise DownloadError(f"API Error: {resp.status}")
                
                data = await resp.json()
                
                if not data.get("success") or not data.get("data"):
                    raise DownloadError("API response mein song data nahi mila")
                
                song_info = data["data"][0]
                download_links = song_info.get("downloadUrl", [])
                
                if not download_links:
                    raise DownloadError("API response mein download link nahi mila")
                
                # Sabse best quality (320kbps) aakhri element mein hoti hai
                best_quality_url = download_links[-1].get("url")
                
                if not best_quality_url:
                    raise DownloadError("Download URL nahi mila")
                
                return best_quality_url
                
    except Exception as e:
        raise DownloadError(f"Stream URL fetch error: {e}")

async def get_related_track(title: str, exclude_id: str = None):
    """
    Autoplay ke liye related track dhoondta hai.
    (Filhaal isko simple rakha hai, aap chaahein toh ise improve kar sakte hain)
    """
    # Simple logic: same title se search karein aur pehla different result lein
    result = await search_track(title)
    if result and result.get("id") != exclude_id:
        return result
    return None
