import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from collections import deque

# Configura los intents para habilitar message content
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

# Inicializa el bot con el prefijo "!"
bot = commands.Bot(command_prefix="!", intents=intents)

# Configuración para yt-dlp
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch',  # Habilitar búsqueda en YouTube
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}
ffmpeg_options = {
    'options': '-vn',
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Comando para unirse a un canal de voz
@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")

# Comando para salir del canal de voz
@bot.command(name="leave")
async def leave(ctx):
    """Desconecta al bot del canal de voz."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Me he desconectado del canal de voz.")
    else:
        await ctx.send("No estoy conectado a ningún canal de voz.")


# Estructura para la cola de canciones
song_queue = deque()

# Comando para reproducir música
@bot.command(name="play")
async def play(ctx, *, query):
    # Verifica si el bot está en un canal de voz
    if ctx.voice_client is None:
        await ctx.send("Primero usa el comando `!join` para que me una a un canal de voz.")
        return

    async with ctx.typing():
        try:
            # Agrega la canción a la cola
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            song_queue.append((player, ctx))
            await ctx.send(f"**{player.title}** ha sido agregada a la cola.")

            # Si no se está reproduciendo nada, inicia la reproducción
            if not ctx.voice_client.is_playing():
                await play_next(ctx.voice_client)
        except Exception as e:
            await ctx.send(f"Hubo un error al intentar reproducir la canción: {e}")

async def play_next(voice_client):
    if song_queue:
        # Reproducir la siguiente canción en la cola
        player, ctx = song_queue.popleft()
        voice_client.play(player, after=lambda e: play_next_callback(ctx.voice_client))
        await ctx.send(f"🎶 Reproduciendo ahora: **{player.title}**")
    else:
        # Mantenerse conectado al canal, pero no reproducir nada
        await ctx.send("✅ Todas las canciones en la cola han terminado. Usa `!play` para agregar más música.")


def play_next_callback(voice_client):
    # Llamar a la función asíncrona para continuar la cola
    coro = play_next(voice_client)
    asyncio.run_coroutine_threadsafe(coro, bot.loop)

@bot.command(name="pause")
async def pause(ctx):
    """Pausa la reproducción actual."""
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ La reproducción ha sido pausada.")
    else:
        await ctx.send("No hay nada reproduciéndose para pausar.")

@bot.command(name="resume")
async def resume(ctx):
    """Reanuda la reproducción pausada."""
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ La reproducción ha sido reanudada.")
    else:
        await ctx.send("No hay nada pausado para reanudar.")


@bot.command(name="skip")
async def skip(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏭️ Canción saltada. Reproduciendo la siguiente...")
    else:
        await ctx.send("No hay nada reproduciéndose para saltar.")


# Comando para detener la reproducción
@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("¡Reproducción detenida!")
    else:
        await ctx.send("No estoy reproduciendo música.")

# Comando de prueba para verificar si el bot responde
@bot.command(name="ping")
async def ping(ctx):
    await ctx.send("¡Pong!")

# Inicia el bot usando una variable de entorno
import os

TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Obtiene el token desde una variable de entorno
if not TOKEN:
    raise ValueError("El token del bot no está configurado. Verifica la variable de entorno DISCORD_BOT_TOKEN.")
    
bot.run(TOKEN)