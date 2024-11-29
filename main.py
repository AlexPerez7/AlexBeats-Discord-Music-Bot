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

# Configuración global
search_results_store = {}  # Diccionario global para almacenar resultados de búsqueda
search_messages_store = {}  # Diccionario global para almacenar mensajes de resultados
song_queue = deque()  # Cola de canciones
control_message = None  # Mensaje persistente para la interfaz de botones
message_content = ""  # Contenido dinámico del mensaje de control

# Configuración para yt-dlp
youtube_dl.utils.bug_reports_message = lambda: ''
ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'default_search': 'ytsearch',
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


# Comandos del Bot
@bot.command(name="join")
async def join(ctx):
    """Conecta al bot a un canal de voz."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
    else:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")


@bot.command(name="play")
async def play(ctx, *, query):
    """Reproduce música o la agrega a la cola."""
    global control_message, message_content

    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Ignorar si no tiene permisos para eliminar mensajes

    if ctx.voice_client is None:
        await ctx.send("Primero usa el comando `!join` para que me una a un canal de voz.", delete_after=5)
        return

    async with ctx.typing():
        try:
            # Agrega la canción a la cola
            player = await YTDLSource.from_url(query, loop=bot.loop, stream=True)
            song_queue.append((player, ctx))

            # Actualiza el contenido del mensaje persistente
            message_content += f"➕ **{player.title}** ha sido agregada a la cola.\n"
            if control_message:
                await control_message.edit(content=message_content, view=MusicControls(ctx))
            else:
                control_message = await ctx.send(content=message_content, view=MusicControls(ctx))

            # Inicia la reproducción si no hay nada sonando
            if not ctx.voice_client.is_playing():
                await play_next(ctx.voice_client)
        except Exception as e:
            await ctx.send(f"Hubo un error al intentar reproducir la canción: {e}", delete_after=5)


async def play_next(voice_client):
    """Reproduce la siguiente canción en la cola."""
    global control_message, message_content
    if song_queue:
        player, ctx = song_queue.popleft()
        voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(voice_client), bot.loop))

        # Actualiza el mensaje persistente
        message_content = f"🎶 Reproduciendo ahora: **{player.title}**\n"
        if control_message:
            await control_message.edit(content=message_content, view=MusicControls(ctx))
        else:
            control_message = await ctx.send(content=message_content, view=MusicControls(ctx))
    else:
        # Limpia el mensaje persistente cuando la cola está vacía
        if control_message:
            await control_message.edit(content="✅ Todas las canciones en la cola han terminado.", view=None)
        control_message = None


@bot.command(name="leave")
async def leave(ctx):
    """Desconecta al bot del canal de voz y limpia el mensaje persistente."""
    global control_message
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        if control_message:
            await control_message.delete()
            control_message = None
        await ctx.send("👋 Me he desconectado del canal de voz.")
    else:
        await ctx.send("No estoy conectado a ningún canal de voz.")


@bot.command(name="search")
async def search(ctx, *, query):
    """Busca canciones en YouTube y muestra los resultados en el mensaje persistente."""
    global control_message, message_content

    # Intenta eliminar el mensaje del usuario
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass  # Ignorar si no tiene permisos para eliminar mensajes

    async with ctx.typing():
        try:
            # Elimina resultados anteriores
            if ctx.author.id in search_results_store:
                del search_results_store[ctx.author.id]
            if ctx.author.id in search_messages_store:
                old_message = search_messages_store[ctx.author.id]
                try:
                    await old_message.delete()
                except discord.NotFound:
                    pass

            # Realiza la búsqueda en YouTube
            search_results = await bot.loop.run_in_executor(
                None, lambda: ytdl.extract_info(f"ytsearch10:{query}", download=False)
            )
            entries = search_results.get("entries", [])

            if not entries:
                await ctx.send("🚫 No se encontraron resultados para tu búsqueda.", delete_after=5)
                return

            # Genera la lista de resultados
            search_list = "\n".join(
                [f"{index + 1}. {entry['title']}" for index, entry in enumerate(entries[:10])]
            )
            # Almacena resultados para el usuario
            search_results_store[ctx.author.id] = entries[:10]

            # Actualiza el mensaje persistente con los resultados de búsqueda
            if control_message:
                message_content += f"\n\n🔍 **Resultados de búsqueda:**\n{search_list}\n\n"
                message_content += "Escribe `!select <número>` para elegir una canción."
                await control_message.edit(content=message_content, view=MusicControls(ctx))
            else:
                control_message = await ctx.send(
                    content=f"🔍 **Resultados de búsqueda:**\n{search_list}\n\n"
                            "Escribe `!select <número>` para elegir una canción.",
                    view=MusicControls(ctx)
                )

        except Exception as e:
            await ctx.send(f"🚫 Error al buscar: {e}", delete_after=5)



@bot.command(name="select")
async def select(ctx, index: int):
    """Selecciona una canción de los resultados para reproducir."""
    try:
        search_results = search_results_store.get(ctx.author.id)

        if not search_results:
            await ctx.send("🚫 No hay búsquedas recientes. Usa `!search <término>` primero.")
            return

        if 1 <= index <= len(search_results):
            selected_song = search_results[index - 1]
            await play(ctx, query=selected_song["webpage_url"])
        else:
            await ctx.send("🚫 Selección inválida. Elige un número de la lista.")
    except Exception as e:
        await ctx.send(f"🚫 Error al seleccionar la canción: {e}")


@bot.event
async def on_message_delete(message):
    """Limpia referencias a mensajes eliminados."""
    for user_id, stored_message in search_messages_store.items():
        if stored_message.id == message.id:
            del search_messages_store[user_id]
            break

@bot.command(name="volume")
async def volume(ctx, level: int):
    """Ajusta el volumen de la música."""
    global control_message, message_content

    # Verifica que el nivel esté entre 0 y 100
    if not (0 <= level <= 100):
        await ctx.send("🚫 Por favor, ingresa un nivel de volumen entre 0 y 100.", delete_after=5)
        return

    # Verifica que el bot esté conectado a un canal de voz
    if not ctx.voice_client:
        await ctx.send("🚫 No estoy conectado a un canal de voz.", delete_after=5)
        return

    # Verifica si hay música reproduciéndose
    if not ctx.voice_client.source:
        await ctx.send("🚫 No hay música reproduciéndose.", delete_after=5)
        return

    # Ajusta el volumen
    ctx.voice_client.source.volume = level / 100

    # Actualiza el mensaje persistente
    message_content += f"\n🔊 Volumen ajustado al {level}%."
    if control_message:
        await control_message.edit(content=message_content, view=MusicControls(ctx))

    # Notifica al usuario
    await ctx.send(f"🔊 Volumen ajustado al {level}%.", delete_after=5)


# Inicia el bot
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("El token del bot no está configurado.")
bot.run(TOKEN)
