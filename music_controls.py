import discord
from discord.ui import Button, View

class MusicControls(View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.control_message = None  # Inicializa el mensaje de control como un atributo de la clase

    async def set_message(self, message):
        """Guarda el mensaje de control para futuras ediciones."""
        self.control_message = message

    @discord.ui.button(label="⏸️ Pausar", style=discord.ButtonStyle.primary)
    async def pause(self, interaction: discord.Interaction, button: Button):
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.pause()
            if self.control_message:
                await self.control_message.edit(content="⏸️ La reproducción ha sido pausada.", view=self)
        else:
            if self.control_message:
                await self.control_message.edit(content="⚠️ No hay nada reproduciéndose para pausar.", view=self)
        await interaction.response.defer()  # Evita enviar un mensaje adicional

    @discord.ui.button(label="▶️ Reanudar", style=discord.ButtonStyle.success)
    async def resume(self, interaction: discord.Interaction, button: Button):
        if self.ctx.voice_client.is_paused():
            self.ctx.voice_client.resume()
            if self.control_message:
                await self.control_message.edit(content="▶️ La reproducción ha sido reanudada.", view=self)
        else:
            if self.control_message:
                await self.control_message.edit(content="⚠️ No hay nada pausado para reanudar.", view=self)
        await interaction.response.defer()

    @discord.ui.button(label="⏭️ Saltar", style=discord.ButtonStyle.danger)
    async def skip(self, interaction: discord.Interaction, button: Button):
        if self.ctx.voice_client.is_playing():
            self.ctx.voice_client.stop()
            if self.control_message:
                await self.control_message.edit(content="⏭️ Canción saltada. Reproduciendo la siguiente...", view=self)
        else:
            if self.control_message:
                await self.control_message.edit(content="⚠️ No hay nada reproduciéndose para saltar.", view=self)
        await interaction.response.defer()
