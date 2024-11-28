import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from collections import deque
from music_controls import MusicControls  # Importa la clase de botones
import os

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
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
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

# Estructura para la cola de canciones
song_queue = deque()

# Comando para unirse a un canal de voz
@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")

# Variable global para almacenar el mensaje de la intefaz de botones
control_message = None  # Mensaje persistente para los botones
message_content = ""  # Contenido dinámico del mensaje persistente

# Comando para reproducir música
@bot.command(name="play")
async def play(ctx, *, query):
    global control_message, message_content  # Variables globales

    # Intenta eliminar el mensaje del usuario
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        # Si el bot no tiene permisos para eliminar mensajes, ignora el error
        await ctx.send("⚠️ No tengo permisos para eliminar mensajes en este canal.", delete_after=5)

    if ctx.voice_client is None:
        await ctx.send("Primero usa el comando `!join` para que me una a un canal de voz.", delete_after=5)
        return

    async with ctx.typing():
        try:
            # Agrega la canción a la cola
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            song_queue.append((player, ctx))
            
            # Actualiza el mensaje persistente con la cola
            message_content += f"➕ **{player.title}** ha sido agregada a la cola.\n"
            if control_message:
                await control_message.edit(content=message_content, view=MusicControls(ctx))
            else:
                control_message = await ctx.send(content=message_content, view=MusicControls(ctx))

            # Inicia la reproducción si no hay nada sonando
            if not ctx.voice_client.is_playing():
                await play_next(ctx.voice_client, ctx)
        except Exception as e:
            await ctx.send(f"Hubo un error al intentar reproducir la canción: {e}", delete_after=5)



async def play_next(voice_client, ctx):
    global control_message, message_content  # Variables globales
    if song_queue:
        # Reproduce la siguiente canción
        player, ctx = song_queue.popleft()
        voice_client.play(player, after=lambda e: play_next_callback(ctx.voice_client, ctx))
        
        # Actualiza el contenido del mensaje persistente
        message_content = f"🎶 Reproduciendo ahora: **{player.title}**\n"
        if control_message:
            await control_message.edit(content=message_content, view=MusicControls(ctx))
        else:
            control_message = await ctx.send(content=message_content, view=MusicControls(ctx))
    else:
        # Limpia el mensaje persistente cuando la cola está vacía
        if control_message:
            await control_message.edit(content="✅ Todas las canciones en la cola han terminado.", view=None)
        control_message = None  # Resetea la referencia al mensaje



def play_next_callback(voice_client, ctx):
    coro = play_next(voice_client, ctx)
    asyncio.run_coroutine_threadsafe(coro, bot.loop)

@bot.command(name="leave")
async def leave(ctx):
    """Desconecta al bot y elimina el mensaje persistente."""
    global control_message  # Variable global
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if control_message:
            await control_message.delete()  # Elimina el mensaje persistente
            control_message = None  # Limpia la referencia al mensaje
        await ctx.send("👋 Me he desconectado del canal de voz.")
    else:
        await ctx.send("No estoy conectado a ningún canal de voz.")

# Inicia el bot usando una variable de entorno
TOKEN = os.getenv("DISCORD_BOT_TOKEN")  # Obtiene el token desde una variable de entorno
if not TOKEN:
    raise ValueError("El token del bot no está configurado. Verifica la variable de entorno DISCORD_BOT_TOKEN.")
    
bot.run(TOKEN)
