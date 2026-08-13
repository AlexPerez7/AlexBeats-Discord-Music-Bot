from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from musicbot.source import Track
from musicbot.utils import LoopMode, format_duration

if TYPE_CHECKING:
    from musicbot.state import GuildMusicState

COLOR = discord.Color.blurple()
ERROR_COLOR = discord.Color.red()

LOOP_LABELS = {
    LoopMode.OFF: "Desactivado",
    LoopMode.SONG: "Canción actual",
    LoopMode.QUEUE: "Cola completa",
}


def _requester_text(track: Track) -> str:
    return track.requester.mention if track.requester else "Automático"


def build_now_playing_embed(state: "GuildMusicState") -> discord.Embed:
    track = state.current
    embed = discord.Embed(
        title="🎶 Reproduciendo ahora",
        description=f"[{track.title}]({track.webpage_url})",
        color=COLOR,
    )
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    embed.add_field(name="Duración", value=format_duration(track.duration))
    embed.add_field(name="Volumen", value=f"{int(state.volume * 100)}%")
    embed.add_field(name="Loop", value=LOOP_LABELS[state.loop_mode])
    if track.uploader:
        embed.add_field(name="Canal", value=track.uploader)
    embed.add_field(name="En cola", value=str(len(state.queue)))
    # Los footers de embed son texto plano: Discord no resuelve menciones ahí,
    # por eso "Pedido por" va como field en vez de footer.
    embed.add_field(name="Pedido por", value=_requester_text(track))
    return embed


def build_queue_embed(state: "GuildMusicState") -> discord.Embed:
    embed = discord.Embed(title="📜 Cola de reproducción", color=COLOR)

    if state.current:
        embed.add_field(
            name="Reproduciendo ahora",
            value=f"[{state.current.title}]({state.current.webpage_url}) — {format_duration(state.current.duration)}",
            inline=False,
        )

    if not state.queue:
        embed.add_field(name="A continuación", value="No hay más canciones en la cola.", inline=False)
        return embed

    lines = [
        f"**{i}.** [{t.title}]({t.webpage_url}) — {format_duration(t.duration)}"
        for i, t in enumerate(state.queue, start=1)
    ]
    embed.add_field(name="A continuación", value="\n".join(lines[:15]), inline=False)
    if len(lines) > 15:
        embed.set_footer(text=f"y {len(lines) - 15} canciones más…")
    return embed


def build_search_embed(query: str, tracks: list[Track]) -> discord.Embed:
    embed = discord.Embed(
        title=f"🔍 Resultados para: {query}",
        description="Elegí una canción del menú de abajo.",
        color=COLOR,
    )
    lines = [f"**{i}.** {t.title} — {format_duration(t.duration)}" for i, t in enumerate(tracks, start=1)]
    embed.add_field(name="Resultados", value="\n".join(lines) or "Sin resultados.", inline=False)
    return embed


def build_idle_embed() -> discord.Embed:
    return discord.Embed(
        title="✅ Cola terminada",
        description="Todas las canciones en la cola han sido reproducidas.",
        color=COLOR,
    )


def build_error_embed(message: str) -> discord.Embed:
    return discord.Embed(title="🚫 Error", description=message, color=ERROR_COLOR)
