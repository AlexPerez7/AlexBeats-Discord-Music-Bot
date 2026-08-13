from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from collections import deque
from typing import Optional

import discord

import config
from musicbot.embeds import build_error_embed, build_idle_embed, build_now_playing_embed
from musicbot.source import Track, resolve_stream
from musicbot.utils import LoopMode

log = logging.getLogger(__name__)

_LOOP_ORDER = [LoopMode.OFF, LoopMode.SONG, LoopMode.QUEUE]


class GuildMusicState:
    """Cola y reproductor de música de un único servidor de Discord.

    Cada instancia posee su propia tarea (`player_task`) que reproduce la cola
    de forma independiente, para que el estado de un servidor nunca afecte a
    otro (a diferencia de la versión original, que usaba variables globales).
    """

    def __init__(self, bot: discord.Client, guild_id: int, controls_view: discord.ui.View):
        self.bot = bot
        self.guild_id = guild_id
        self.controls_view = controls_view

        self.queue: deque[Track] = deque()
        self.current: Optional[Track] = None
        self.volume: float = config.DEFAULT_VOLUME
        self.loop_mode: LoopMode = LoopMode.OFF
        self.text_channel: Optional[discord.abc.Messageable] = None
        self.control_message: Optional[discord.Message] = None

        # Eventos separados a propósito: si compartieran uno solo, encolar una
        # canción mientras otra está sonando despertaría por error la espera de
        # "la canción actual terminó".
        self.track_finished = asyncio.Event()
        self.queue_updated = asyncio.Event()

        self.player_task: Optional[asyncio.Task] = None
        self._ensure_player_task()

    # -- acceso a discord.py -------------------------------------------------

    @property
    def voice_client(self) -> Optional[discord.VoiceClient]:
        guild = self.bot.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    # -- control de cola -------------------------------------------------

    def enqueue(self, track: Track) -> None:
        self.queue.append(track)
        self._ensure_player_task()
        self.queue_updated.set()

    def skip(self) -> bool:
        vc = self.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            return True
        return False

    def stop_and_clear(self) -> None:
        self.queue.clear()
        # Si no reseteamos el loop, el bucle de reproducción re-encolaría la
        # canción interrumpida en cuanto termine de "detenerse" (ver _player_loop).
        self.loop_mode = LoopMode.OFF
        vc = self.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()

    def pause(self) -> bool:
        vc = self.voice_client
        if vc and vc.is_playing():
            vc.pause()
            return True
        return False

    def resume(self) -> bool:
        vc = self.voice_client
        if vc and vc.is_paused():
            vc.resume()
            return True
        return False

    def set_volume(self, percent: int) -> None:
        self.volume = max(0, min(100, percent)) / 100
        vc = self.voice_client
        if vc and vc.source:
            vc.source.volume = self.volume

    def shuffle(self) -> bool:
        if len(self.queue) < 2:
            return False
        items = list(self.queue)
        random.shuffle(items)
        self.queue = deque(items)
        return True

    def remove(self, index: int) -> Optional[Track]:
        if 1 <= index <= len(self.queue):
            items = list(self.queue)
            track = items.pop(index - 1)
            self.queue = deque(items)
            return track
        return None

    def cycle_loop_mode(self) -> LoopMode:
        next_index = (_LOOP_ORDER.index(self.loop_mode) + 1) % len(_LOOP_ORDER)
        self.loop_mode = _LOOP_ORDER[next_index]
        return self.loop_mode

    async def refresh_control_message(self) -> None:
        """Vuelve a renderizar el mensaje de control con el estado actual (p. ej.
        tras cambiar el volumen o el modo de loop desde un botón/comando)."""
        await self._update_control_message()

    async def shutdown(self) -> None:
        """Cancela el reproductor y desconecta. Usado por !leave/!stop y por el
        chequeo de "el bot se quedó solo en el canal"."""
        if self.player_task and not self.player_task.done():
            self.player_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.player_task

        self.queue.clear()
        vc = self.voice_client
        if vc and vc.is_connected():
            with contextlib.suppress(discord.ClientException):
                await vc.disconnect(force=True)

        if self.control_message:
            with contextlib.suppress(discord.HTTPException):
                await self.control_message.delete()
            self.control_message = None

    # -- bucle de reproducción -------------------------------------------------

    def _ensure_player_task(self) -> None:
        if self.player_task is None or self.player_task.done():
            self.player_task = self.bot.loop.create_task(self._player_loop())

    def _after_playback(self, error: Optional[Exception]) -> None:
        if error:
            log.error("Error de reproducción en guild %s: %s", self.guild_id, error)
        self.bot.loop.call_soon_threadsafe(self.track_finished.set)

    async def _player_loop(self) -> None:
        while True:
            if not self.queue:
                self.queue_updated.clear()
                try:
                    await asyncio.wait_for(
                        self.queue_updated.wait(), timeout=config.INACTIVITY_TIMEOUT_SECONDS
                    )
                except asyncio.TimeoutError:
                    await self._handle_idle_timeout()
                    return
                continue

            vc = self.voice_client
            if vc is None:
                # Nos desconectaron (p. ej. manualmente) sin pasar por shutdown().
                return

            self.current = self.queue.popleft()
            try:
                source = await resolve_stream(
                    self.current,
                    volume=self.volume,
                    ffmpeg_path=config.FFMPEG_PATH,
                    loop=self.bot.loop,
                )
            except Exception:
                log.exception("No se pudo resolver el stream para '%s'", self.current.title)
                await self._notify_error(f"No se pudo reproducir **{self.current.title}**, la salto.")
                continue

            self.track_finished.clear()
            vc.play(source, after=self._after_playback)
            await self._update_control_message()
            await self.track_finished.wait()

            if self.loop_mode is LoopMode.SONG:
                self.queue.appendleft(self.current)
            elif self.loop_mode is LoopMode.QUEUE:
                self.queue.append(self.current)

    async def _handle_idle_timeout(self) -> None:
        vc = self.voice_client
        if vc and vc.is_connected():
            with contextlib.suppress(discord.ClientException):
                await vc.disconnect(force=True)
        if self.control_message:
            with contextlib.suppress(discord.HTTPException):
                await self.control_message.edit(embed=build_idle_embed(), view=None)
            self.control_message = None

    async def _update_control_message(self) -> None:
        if self.text_channel is None or self.current is None:
            return
        embed = build_now_playing_embed(self)
        try:
            if self.control_message:
                await self.control_message.edit(embed=embed, view=self.controls_view)
            else:
                self.control_message = await self.text_channel.send(embed=embed, view=self.controls_view)
        except discord.HTTPException:
            log.exception("No se pudo actualizar el mensaje de control en guild %s", self.guild_id)

    async def _notify_error(self, message: str) -> None:
        if self.text_channel is None:
            return
        with contextlib.suppress(discord.HTTPException):
            await self.text_channel.send(embed=build_error_embed(message), delete_after=10)
