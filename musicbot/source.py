import asyncio
import functools
from dataclasses import dataclass
from typing import Optional

import discord
import yt_dlp as youtube_dl

YTDL_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "default_search": "ytsearch",
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# Instancia normal: resuelve metadata + formato de audio completos (usada para
# resolver una selección concreta y para obtener la URL de stream justo antes
# de reproducir, evitando URLs de stream vencidas).
_ytdl = youtube_dl.YoutubeDL(YTDL_FORMAT_OPTIONS)

# Instancia "flat": para listar resultados de búsqueda rápido, sin resolver
# el formato de audio de cada video uno por uno.
_ytdl_flat = youtube_dl.YoutubeDL({**YTDL_FORMAT_OPTIONS, "extract_flat": "in_playlist"})


@dataclass
class Track:
    title: str
    webpage_url: str
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    requester: Optional[discord.abc.User] = None


async def _extract(ytdl: youtube_dl.YoutubeDL, query: str, loop=None) -> dict:
    loop = loop or asyncio.get_running_loop()
    func = functools.partial(ytdl.extract_info, query, download=False)
    return await loop.run_in_executor(None, func)


def _track_from_entry(entry: dict, requester=None) -> Track:
    return Track(
        title=entry.get("title") or "Título desconocido",
        webpage_url=entry.get("webpage_url") or entry.get("url"),
        duration=entry.get("duration"),
        thumbnail=entry.get("thumbnail"),
        uploader=entry.get("uploader") or entry.get("channel"),
        requester=requester,
    )


async def search_tracks(query: str, limit: int = 10, loop=None) -> list[Track]:
    """Busca canciones en YouTube sin resolver metadata completa (rápido)."""
    data = await _extract(_ytdl_flat, f"ytsearch{limit}:{query}", loop=loop)
    entries = [e for e in (data.get("entries") or []) if e][:limit]

    tracks = []
    for entry in entries:
        video_id = entry.get("id")
        webpage_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else entry.get("url")
        tracks.append(
            Track(
                title=entry.get("title") or "Título desconocido",
                webpage_url=webpage_url,
                duration=entry.get("duration"),
                thumbnail=entry.get("thumbnail"),
                uploader=entry.get("uploader") or entry.get("channel"),
            )
        )
    return tracks


async def resolve_track(query_or_url: str, requester=None, loop=None) -> Track:
    """Resuelve una búsqueda directa o una URL a la metadata completa de una canción."""
    data = await _extract(_ytdl, query_or_url, loop=loop)
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
        if not entries:
            raise ValueError("No se encontraron resultados.")
        data = entries[0]
    return _track_from_entry(data, requester=requester)


async def resolve_stream(
    track: Track,
    *,
    volume: float,
    ffmpeg_path: str = "ffmpeg",
    loop=None,
) -> discord.PCMVolumeTransformer:
    """Resuelve una URL de stream *fresca* para el track y arma la fuente de audio.

    Se re-extrae justo antes de reproducir (en vez de usar una URL capturada al
    encolar la canción) porque las URLs de stream de YouTube expiran.
    """
    data = await _extract(_ytdl, track.webpage_url, loop=loop)
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
        if not entries:
            raise ValueError("No se pudo resolver el stream de la canción.")
        data = entries[0]

    stream_url = data["url"]
    source = discord.FFmpegPCMAudio(stream_url, executable=ffmpeg_path, **FFMPEG_OPTIONS)
    return discord.PCMVolumeTransformer(source, volume=volume)
