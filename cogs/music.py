from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands

import config
from musicbot.embeds import (
    LOOP_LABELS,
    build_error_embed,
    build_now_playing_embed,
    build_queue_embed,
    build_search_embed,
)
from musicbot.source import Track, resolve_track, search_tracks
from musicbot.state import GuildMusicState
from musicbot.ui import MusicControls, SearchResultsView
from musicbot.utils import LoopMode

log = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.states: dict[int, GuildMusicState] = {}
        self.controls_view = MusicControls(self)

    def get_state(self, guild_id: int) -> GuildMusicState:
        state = self.states.get(guild_id)
        if state is None:
            state = GuildMusicState(self.bot, guild_id, self.controls_view)
            self.states[guild_id] = state
        return state

    async def _enqueue(
        self,
        *,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        voice_channel: discord.VoiceChannel,
        requester: discord.abc.User,
        track: Track,
    ) -> GuildMusicState:
        state = self.get_state(guild.id)
        state.text_channel = channel
        vc = state.voice_client
        if vc is None:
            await voice_channel.connect()
        elif vc.channel.id != voice_channel.id:
            await vc.move_to(voice_channel)
        track.requester = requester
        state.enqueue(track)
        return state

    async def play_selected_track(self, interaction: discord.Interaction, track: Track) -> None:
        """Llamado por el menú desplegable de `/search` al elegir una canción."""
        if interaction.user.voice is None or interaction.user.voice.channel is None:
            await interaction.response.send_message(
                embed=build_error_embed("Tenés que estar en un canal de voz."), ephemeral=True
            )
            return
        await interaction.response.send_message(f"➕ **{track.title}** añadida a la cola.", ephemeral=True)
        await self._enqueue(
            guild=interaction.guild,
            channel=interaction.channel,
            voice_channel=interaction.user.voice.channel,
            requester=interaction.user,
            track=track,
        )

    # -- comandos -------------------------------------------------

    @commands.hybrid_command(name="join", description="Conecta el bot a tu canal de voz.")
    async def join(self, ctx: commands.Context):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send(embed=build_error_embed("Tenés que estar en un canal de voz para usar este comando."))
            return
        state = self.get_state(ctx.guild.id)
        state.text_channel = ctx.channel
        vc = state.voice_client
        if vc is None:
            await ctx.author.voice.channel.connect()
        else:
            await vc.move_to(ctx.author.voice.channel)
        await ctx.send(f"🔗 Conectado a **{ctx.author.voice.channel.name}**.", delete_after=6)

    @commands.hybrid_command(name="leave", description="Desconecta el bot y limpia la cola.")
    async def leave(self, ctx: commands.Context):
        state = self.states.pop(ctx.guild.id, None)
        if state is None or state.voice_client is None:
            await ctx.send(embed=build_error_embed("No estoy conectado a ningún canal de voz."), delete_after=5)
            return
        await state.shutdown()
        await ctx.send("👋 Me desconecté del canal de voz.", delete_after=6)

    @commands.hybrid_command(name="play", description="Reproduce una canción o la agrega a la cola.")
    @app_commands.describe(query="Nombre de la canción o una URL de YouTube")
    async def play(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send(embed=build_error_embed("Tenés que estar en un canal de voz para reproducir música."))
            return
        try:
            track = await resolve_track(query, requester=ctx.author, loop=self.bot.loop)
        except Exception:
            log.exception("Error al resolver '%s'", query)
            await ctx.send(embed=build_error_embed(f"No pude encontrar/reproducir: {query}"))
            return
        await self._enqueue(
            guild=ctx.guild, channel=ctx.channel, voice_channel=ctx.author.voice.channel, requester=ctx.author, track=track
        )
        await ctx.send(f"➕ **{track.title}** añadida a la cola.", delete_after=8)

    @commands.hybrid_command(name="search", description="Busca canciones en YouTube y elegí una para reproducir.")
    @app_commands.describe(query="Qué buscar en YouTube")
    async def search(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        try:
            tracks = await search_tracks(query, limit=10, loop=self.bot.loop)
        except Exception:
            log.exception("Error buscando '%s'", query)
            await ctx.send(embed=build_error_embed("Ocurrió un error al buscar."))
            return
        if not tracks:
            await ctx.send(embed=build_error_embed("No se encontraron resultados."))
            return
        view = SearchResultsView(self, tracks)
        message = await ctx.send(embed=build_search_embed(query, tracks), view=view)
        view.message = message

    @commands.hybrid_command(name="skip", description="Salta la canción actual.")
    async def skip(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or not state.skip():
            await ctx.send(embed=build_error_embed("No hay nada sonando."), delete_after=5)
            return
        await ctx.send("⏭️ Canción saltada.", delete_after=5)

    @commands.hybrid_command(name="pause", description="Pausa la reproducción.")
    async def pause(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or not state.pause():
            await ctx.send(embed=build_error_embed("No hay nada reproduciéndose."), delete_after=5)
            return
        await ctx.send("⏸️ Pausado.", delete_after=5)

    @commands.hybrid_command(name="resume", description="Reanuda la reproducción.")
    async def resume(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or not state.resume():
            await ctx.send(embed=build_error_embed("No hay nada pausado."), delete_after=5)
            return
        await ctx.send("▶️ Reanudado.", delete_after=5)

    @commands.hybrid_command(name="stop", description="Detiene la música y vacía la cola (sin desconectar).")
    async def stop(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None:
            await ctx.send(embed=build_error_embed("No hay nada reproduciéndose."), delete_after=5)
            return
        state.stop_and_clear()
        await ctx.send("⏹️ Reproducción detenida y cola vaciada.", delete_after=5)

    @commands.hybrid_command(name="queue", description="Muestra la cola de reproducción.")
    async def queue(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or (state.current is None and not state.queue):
            await ctx.send(embed=build_error_embed("La cola está vacía."), delete_after=5)
            return
        await ctx.send(embed=build_queue_embed(state))

    @commands.hybrid_command(name="nowplaying", description="Muestra la canción que está sonando.")
    async def nowplaying(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or state.current is None:
            await ctx.send(embed=build_error_embed("No hay nada reproduciéndose."), delete_after=5)
            return
        await ctx.send(embed=build_now_playing_embed(state))

    @commands.hybrid_command(name="volume", description="Ajusta el volumen (0-100).")
    @app_commands.describe(level="Nivel de volumen, de 0 a 100")
    async def volume(self, ctx: commands.Context, level: int):
        if not (0 <= level <= 100):
            await ctx.send(embed=build_error_embed("El volumen debe estar entre 0 y 100."), delete_after=5)
            return
        state = self.get_state(ctx.guild.id)
        state.set_volume(level)
        await state.refresh_control_message()
        await ctx.send(f"🔊 Volumen ajustado al {level}%.", delete_after=5)

    @commands.hybrid_command(name="loop", description="Cambia el modo de repetición.")
    @app_commands.describe(mode="off = sin repetición, song = repetir canción, queue = repetir toda la cola")
    async def loop(self, ctx: commands.Context, mode: Literal["off", "song", "queue"]):
        state = self.get_state(ctx.guild.id)
        state.loop_mode = LoopMode(mode)
        await state.refresh_control_message()
        await ctx.send(f"🔁 Loop: {LOOP_LABELS[state.loop_mode]}", delete_after=5)

    @commands.hybrid_command(name="shuffle", description="Mezcla la cola actual.")
    async def shuffle(self, ctx: commands.Context):
        state = self.states.get(ctx.guild.id)
        if state is None or not state.shuffle():
            await ctx.send(embed=build_error_embed("No hay suficientes canciones en la cola para mezclar."), delete_after=5)
            return
        await ctx.send("🔀 Cola mezclada.", delete_after=5)

    @commands.hybrid_command(name="remove", description="Quita una canción de la cola por su número.")
    @app_commands.describe(index="Número de la canción en la cola (ver /queue)")
    async def remove(self, ctx: commands.Context, index: int):
        state = self.states.get(ctx.guild.id)
        track = state.remove(index) if state else None
        if track is None:
            await ctx.send(embed=build_error_embed("Número inválido. Usá /queue para ver la lista."), delete_after=5)
            return
        await ctx.send(f"🗑️ Quité **{track.title}** de la cola.", delete_after=5)

    @commands.command(name="sync")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        """Sincroniza los slash commands (solo el dueño del bot)."""
        if config.DEV_GUILD_ID:
            guild = discord.Object(id=config.DEV_GUILD_ID)
            self.bot.tree.copy_global_to(guild=guild)
            synced = await self.bot.tree.sync(guild=guild)
            await ctx.send(f"🔄 Sincronizados {len(synced)} comandos en el servidor de desarrollo.")
        else:
            synced = await self.bot.tree.sync()
            await ctx.send(f"🔄 Sincronizados {len(synced)} comandos globalmente (puede tardar hasta 1 hora en propagarse).")

    # -- eventos -------------------------------------------------

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        if member.id == self.bot.user.id:
            return
        state = self.states.get(member.guild.id)
        if state is None:
            return
        vc = state.voice_client
        if vc is None or vc.channel is None or len(vc.channel.members) > 1:
            return

        # Debounce: esperamos un poco por si es un reconexión momentánea antes
        # de desconectar por quedarnos solos en el canal.
        await asyncio.sleep(8)
        vc = state.voice_client
        if vc and vc.channel and len(vc.channel.members) <= 1:
            self.states.pop(member.guild.id, None)
            await state.shutdown()

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        error = getattr(error, "original", error)
        if isinstance(error, (commands.CommandNotFound, commands.NotOwner)):
            return
        log.error("Error en comando '%s'", ctx.command, exc_info=error)
        with contextlib.suppress(discord.HTTPException):
            await ctx.send(embed=build_error_embed(f"Ocurrió un error: {error}"), delete_after=10)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
