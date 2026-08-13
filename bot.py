import logging

import discord
from discord.ext import commands

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("alexbeats")

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True


class AlexBeatsBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=config.COMMAND_PREFIX, intents=intents)

    async def setup_hook(self):
        await self.load_extension("cogs.music")
        music_cog = self.get_cog("Music")
        # Registra la vista de controles una sola vez para que siga funcionando
        # después de reiniciar el proceso (ver musicbot/ui.py).
        self.add_view(music_cog.controls_view)

    async def on_ready(self):
        log.info("Conectado como %s (id: %s)", self.user, self.user.id)


def main():
    bot = AlexBeatsBot()
    bot.run(config.TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
