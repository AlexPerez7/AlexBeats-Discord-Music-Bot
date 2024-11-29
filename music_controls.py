import discord

class MusicControls(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.volume = 50  # Nivel inicial de volumen (50%)

    @discord.ui.button(label="⏸️ Pausar", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.is_playing():
            self.ctx.voice_client.pause()
            await interaction.response.send_message("⏸️ La reproducción ha sido pausada.", ephemeral=True)

    @discord.ui.button(label="▶️ Reanudar", style=discord.ButtonStyle.success)
    async def resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.is_paused():
            self.ctx.voice_client.resume()
            await interaction.response.send_message("▶️ La reproducción ha sido reanudada.", ephemeral=True)

    @discord.ui.button(label="⏭️ Saltar", style=discord.ButtonStyle.secondary)
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.is_playing():
            self.ctx.voice_client.stop()
            await interaction.response.send_message("⏭️ Canción saltada. Reproduciendo la siguiente...", ephemeral=True)

    @discord.ui.button(label="🔊 +", style=discord.ButtonStyle.primary, row=1)
    async def volume_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.source:
            self.volume = min(self.volume + 10, 100)  # Aumenta el volumen hasta un máximo de 100%
            self.ctx.voice_client.source.volume = self.volume / 100
            await interaction.response.send_message(f"🔊 Volumen aumentado al {self.volume}%.", ephemeral=True)

    @discord.ui.button(label="🔉 -", style=discord.ButtonStyle.primary, row=1)
    async def volume_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.source:
            self.volume = max(self.volume - 10, 0)  # Disminuye el volumen hasta un mínimo de 0%
            self.ctx.voice_client.source.volume = self.volume / 100
            await interaction.response.send_message(f"🔉 Volumen reducido al {self.volume}%.", ephemeral=True)

    @discord.ui.button(label="🔇 Silenciar", style=discord.ButtonStyle.danger, row=1)
    async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.ctx.voice_client and self.ctx.voice_client.source:
            self.volume = 0  # Silencia el volumen
            self.ctx.voice_client.source.volume = 0
            await interaction.response.send_message("🔇 El volumen ha sido silenciado.", ephemeral=True)
