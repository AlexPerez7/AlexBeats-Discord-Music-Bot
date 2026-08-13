from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import discord

from musicbot.embeds import LOOP_LABELS
from musicbot.source import Track
from musicbot.utils import format_duration

if TYPE_CHECKING:
    from cogs.music import Music

log = logging.getLogger(__name__)


class MusicControls(discord.ui.View):
    """Vista persistente de botones para el mensaje de "reproduciendo ahora".

    Una única instancia de esta vista sirve a *todos* los servidores: los
    componentes tienen `custom_id` fijo y se registran una sola vez en
    `setup_hook` con `bot.add_view(...)`, así siguen funcionando después de un
    reinicio del bot. Cada callback resuelve el estado del servidor a partir
    de `interaction.guild_id` en el momento del clic, en vez de guardar una
    referencia por servidor.
    """

    def __init__(self, cog: "Music"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _require_state(self, interaction: discord.Interaction):
        state = self.cog.states.get(interaction.guild_id)
        if state is None or state.current is None:
            await interaction.response.send_message("🚫 No hay música reproduciéndose.", ephemeral=True)
            return None
        return state

    @discord.ui.button(label="⏯️ Pausa / Reanuda", style=discord.ButtonStyle.primary, custom_id="music:pause_resume")
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        vc = state.voice_client
        if vc and vc.is_paused():
            state.resume()
            await interaction.response.send_message("▶️ Reanudado.", ephemeral=True)
        elif vc and vc.is_playing():
            state.pause()
            await interaction.response.send_message("⏸️ Pausado.", ephemeral=True)
        else:
            await interaction.response.send_message("🚫 No hay nada para pausar/reanudar.", ephemeral=True)

    @discord.ui.button(label="⏭️ Saltar", style=discord.ButtonStyle.secondary, custom_id="music:skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        if state.skip():
            await interaction.response.send_message("⏭️ Canción saltada.", ephemeral=True)
        else:
            await interaction.response.send_message("🚫 No hay nada sonando.", ephemeral=True)

    @discord.ui.button(label="⏹️ Detener", style=discord.ButtonStyle.danger, custom_id="music:stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        state.stop_and_clear()
        await interaction.response.send_message("⏹️ Reproducción detenida y cola vaciada.", ephemeral=True)

    @discord.ui.button(label="🔉", style=discord.ButtonStyle.secondary, row=1, custom_id="music:vol_down")
    async def volume_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        state.set_volume(int(state.volume * 100) - 10)
        await interaction.response.send_message(f"🔉 Volumen: {int(state.volume * 100)}%", ephemeral=True)
        await state.refresh_control_message()

    @discord.ui.button(label="🔊", style=discord.ButtonStyle.secondary, row=1, custom_id="music:vol_up")
    async def volume_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        state.set_volume(int(state.volume * 100) + 10)
        await interaction.response.send_message(f"🔊 Volumen: {int(state.volume * 100)}%", ephemeral=True)
        await state.refresh_control_message()

    @discord.ui.button(label="🔁 Loop", style=discord.ButtonStyle.secondary, row=1, custom_id="music:loop")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        mode = state.cycle_loop_mode()
        await interaction.response.send_message(f"🔁 Loop: {LOOP_LABELS[mode]}", ephemeral=True)
        await state.refresh_control_message()

    @discord.ui.button(label="🔀 Aleatorio", style=discord.ButtonStyle.secondary, row=1, custom_id="music:shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = await self._require_state(interaction)
        if state is None:
            return
        if state.shuffle():
            await interaction.response.send_message("🔀 Cola mezclada.", ephemeral=True)
        else:
            await interaction.response.send_message("🚫 No hay suficientes canciones para mezclar.", ephemeral=True)


class TrackSelect(discord.ui.Select):
    def __init__(self, cog: "Music", tracks: list[Track]):
        self.cog = cog
        self.tracks = tracks
        options = [
            discord.SelectOption(
                label=track.title[:100],
                description=format_duration(track.duration),
                value=str(index),
            )
            for index, track in enumerate(tracks)
        ]
        super().__init__(placeholder="Elegí una canción...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        track = self.tracks[int(self.values[0])]
        await self.cog.play_selected_track(interaction, track)
        self.view.stop()
        with contextlib.suppress(discord.HTTPException):
            await interaction.message.delete()


class SearchResultsView(discord.ui.View):
    """Vista de un solo uso para elegir una canción de los resultados de `!search`."""

    def __init__(self, cog: "Music", tracks: list[Track]):
        super().__init__(timeout=60)
        self.message: discord.Message | None = None
        self.add_item(TrackSelect(cog, tracks))

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        if self.message:
            with contextlib.suppress(discord.HTTPException):
                await self.message.edit(view=self)
