# AlexBeats — Bot de Música para Discord

Bot de música para Discord con comandos de texto (`!play`) y slash commands (`/play`), cola de reproducción, botones de control persistentes y soporte correcto para múltiples servidores a la vez.

## Requisitos

- Python 3.10 o superior.
- [FFmpeg](https://ffmpeg.org/) instalado y disponible en el `PATH` del sistema (o configurable vía `.env`, ver abajo).
- Una aplicación/bot creada en el [Discord Developer Portal](https://discord.com/developers/applications), con los intents **Message Content** y **Server Members** habilitados si vas a usar comandos de texto, y con el bot invitado a tu servidor con permisos de conectar/hablar en voz.

## Instalación

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

Copiá `.env.example` a `.env` y completá al menos el token del bot:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
```

```env
DISCORD_BOT_TOKEN=el-token-de-tu-bot
```

Las demás variables de `.env` son opcionales (tienen valores por defecto razonables):

| Variable | Default | Descripción |
|---|---|---|
| `COMMAND_PREFIX` | `!` | Prefijo de los comandos de texto (los `/slash` siempre funcionan). |
| `DEFAULT_VOLUME` | `50` | Volumen inicial (0-100) al empezar a reproducir en un servidor. |
| `INACTIVITY_TIMEOUT_SECONDS` | `300` | Segundos sin música antes de que el bot se desconecte solo. |
| `DEV_GUILD_ID` | *(vacío)* | ID de un servidor de pruebas para sincronizar slash commands al instante. |
| `FFMPEG_PATH` | `ffmpeg` | Ruta al ejecutable de FFmpeg, si no está en el `PATH`. |

## Ejecutar el bot

```bash
python bot.py
```

Los slash commands (`/play`, `/skip`, etc.) no se sincronizan automáticamente al arrancar. La primera vez, o cada vez que agregues/cambies un comando, escribí en un canal donde el bot esté (con tu cuenta de dueño del bot):

```
!sync
```

Si configuraste `DEV_GUILD_ID`, la sincronización es casi instantánea en ese servidor. Si lo dejás vacío, sincroniza globalmente, lo que puede tardar hasta una hora en propagarse a todos los servidores.

## Comandos

Todos funcionan tanto como `!comando` (texto) como `/comando` (slash).

| Comando | Descripción |
|---|---|
| `join` | Conecta el bot a tu canal de voz. |
| `play <query>` | Reproduce una canción (nombre o URL de YouTube) o la agrega a la cola. Se conecta solo a tu canal si hace falta. |
| `search <query>` | Busca 10 resultados en YouTube y muestra un menú desplegable para elegir cuál reproducir. |
| `skip` | Salta la canción actual. |
| `pause` / `resume` | Pausa o reanuda la reproducción. |
| `stop` | Detiene la música y vacía la cola (sin desconectar del canal). |
| `queue` | Muestra la cola de reproducción. |
| `nowplaying` | Muestra la canción que está sonando. |
| `volume <0-100>` | Ajusta el volumen. |
| `loop <off\|song\|queue>` | Repite la canción actual, toda la cola, o desactiva la repetición. |
| `shuffle` | Mezcla el orden de la cola. |
| `remove <número>` | Quita una canción de la cola por su posición (ver `queue`). |
| `leave` | Desconecta el bot y limpia la cola. |
| `!sync` | *(solo texto, solo el dueño del bot)* Sincroniza los slash commands. |

El mensaje de "reproduciendo ahora" incluye botones (pausar/reanudar, saltar, detener, subir/bajar volumen, loop, aleatorio) que siguen funcionando incluso si reiniciás el bot.

## Arquitectura

```
bot.py                  # entrypoint: intents, carga el cog, registra la vista persistente
config.py                # carga variables de entorno desde .env
cogs/music.py             # todos los comandos, listener de voz, manejo de errores
musicbot/
  state.py                # GuildMusicState: cola y reproductor propios de cada servidor
  source.py                # búsqueda y extracción de audio vía yt-dlp
  ui.py                    # botones de control y menú de selección de búsqueda
  embeds.py                # construcción de los embeds mostrados en Discord
  utils.py                 # helpers puros (formato de duración, modos de loop)
tests/                    # tests unitarios de la lógica pura (sin red ni Discord)
```

Cada servidor tiene su propia `GuildMusicState`, con su propia cola, volumen y tarea de reproducción — a diferencia de la versión original del bot, que usaba variables globales compartidas por todo el proceso (rompiéndose si el bot estaba en más de un servidor a la vez). El volumen se guarda en un único lugar (el estado del servidor), tanto los botones como el comando `/volume` lo leen y escriben ahí. La URL de streaming de cada canción se resuelve recién antes de reproducirla (no al encolarla), para evitar que expire si la canción espera un rato en la cola.

## Correr los tests

```bash
pytest
```

## Limitaciones conocidas

- YouTube bloquea ocasionalmente la extracción de ciertos videos (streams 24/7, contenido restringido) sin cookies de una cuenta logueada, mostrando un error de "Sign in to confirm you're not a bot". Es una limitación de `yt-dlp` sin autenticación, no del bot — para resolverlo permanentemente haría falta pasar cookies de un navegador (`--cookies-from-browser`), lo cual queda fuera del alcance de este proyecto.
- El bot solo reproduce audio de YouTube (vía búsqueda o URL directa); no soporta Spotify, SoundCloud u otras plataformas.
