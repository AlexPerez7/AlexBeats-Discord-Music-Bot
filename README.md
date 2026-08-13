# AlexBeats — Bot de Música para Discord

Bot de música para Discord con comandos de texto (`!play`) y slash commands (`/play`), cola de reproducción, botones de control persistentes y soporte correcto para múltiples servidores a la vez.

## Requisitos

- Python 3.10 o superior.
- [FFmpeg](https://ffmpeg.org/) instalado y disponible en el `PATH` del sistema (o configurable vía `.env`, ver abajo).
- Una aplicación/bot creada en el [Discord Developer Portal](https://discord.com/developers/applications) (ver paso a paso abajo).

## 1. Crear y configurar la aplicación en Discord

Si ya existe una aplicación creada para este bot, se puede saltar directo al paso que corresponda.

1. Entrar a https://discord.com/developers/applications y crear una aplicación nueva (o abrir la existente).
2. En el menú izquierdo, ir a **Bot**:
   - Si no se copió el token antes, hacer clic en **Reset Token** para generarlo y copiarlo — Discord no lo vuelve a mostrar después, hay que guardarlo en un lugar seguro. **Nunca debe compartirse ni subirse a git** (por eso vive en `.env`, que está en `.gitignore`).
   - Bajar hasta **Privileged Gateway Intents** y activar **Message Content Intent** (obligatorio para que el bot pueda leer comandos de texto como `!play`).
3. Ir a **OAuth2** en el menú izquierdo y bajar hasta **"Generador de URL de OAuth2"**:
   - En **Scopes**, marcar `bot` y `applications.commands`.
   - Al marcar `bot` aparece la sección **"Permisos del bot"** — marcar al menos:
     - Texto: `Enviar mensajes`, `Leer el historial de mensajes`, `Insertar enlaces`, `Usar comandos de barra diagonal`.
     - Voz: `Conectarse`, `Hablar`.
   - Al final de la página se genera la **URL** — copiarla, abrirla en una pestaña nueva, elegir el servidor de destino y confirmar la invitación.
4. (Opcional, recomendado) Activar el **modo desarrollador** en Discord (⚙️ Ajustes de usuario → Avanzado) para poder copiar IDs de servidor con clic derecho — se usa en el paso de sincronización rápida más abajo.

## 2. Instalación del proyecto

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

Copiar `.env.example` a `.env`:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
```

Abrir `.env` y completar al menos el token del bot:

```env
DISCORD_BOT_TOKEN=el-token-del-bot
```

Las demás variables de `.env` son opcionales (tienen valores por defecto razonables):

| Variable | Default | Descripción |
|---|---|---|
| `COMMAND_PREFIX` | `!` | Prefijo de los comandos de texto (los `/slash` siempre funcionan). |
| `DEFAULT_VOLUME` | `50` | Volumen inicial (0-100) al empezar a reproducir en un servidor. |
| `INACTIVITY_TIMEOUT_SECONDS` | `300` | Segundos sin música antes de que el bot se desconecte solo. |
| `DEV_GUILD_ID` | *(vacío)* | ID del servidor de pruebas (clic derecho sobre el ícono del servidor → Copiar ID, con el modo desarrollador activado). Con esto, `!sync` sincroniza los slash commands al instante en vez de tardar hasta 1 hora. |
| `FFMPEG_PATH` | `ffmpeg` | Ruta al ejecutable de FFmpeg, si no está en el `PATH`. |

## 3. Ejecutar el bot

```bash
python bot.py
```

Si la conexión fue exitosa, la consola muestra algo como `Conectado como AlexBeats#0155` y el bot aparece **en línea** en el servidor.

Los slash commands (`/play`, `/skip`, etc.) no se sincronizan automáticamente al arrancar. La primera vez, o cada vez que se agregue o cambie un comando, hay que escribir en un canal donde el bot esté (con la cuenta que creó la aplicación):

```
!sync
```

Si se configuró `DEV_GUILD_ID`, la sincronización es casi instantánea en ese servidor. Si se deja vacío, sincroniza globalmente, lo que puede tardar hasta una hora en propagarse.

## Comandos

Todos funcionan tanto como `!comando` (texto) como `/comando` (slash).

| Comando | Descripción |
|---|---|
| `join` | Conecta el bot al canal de voz del usuario. |
| `play <query>` | Reproduce una canción (nombre o URL de YouTube) o la agrega a la cola. Se conecta solo al canal correspondiente si hace falta. |
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

El mensaje de "reproduciendo ahora" incluye botones (pausar/reanudar, saltar, detener, subir/bajar volumen, loop, aleatorio) que siguen funcionando incluso después de reiniciar el bot.

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

Cada servidor tiene su propia `GuildMusicState`, con su propia cola, volumen y tarea de reproducción — a diferencia de la versión original del bot, que usaba variables globales compartidas por todo el proceso (rompiéndose si el bot estaba en más de un servidor a la vez). El volumen se guarda en un único lugar (el estado del servidor); tanto los botones como el comando `/volume` lo leen y escriben ahí. La URL de streaming de cada canción se resuelve recién antes de reproducirla (no al encolarla), para evitar que expire si la canción espera un rato en la cola.

## Correr los tests

```bash
pytest
```

## Solución de problemas

**`RuntimeError: davey library needed in order to use voice`** al usar `play`/`join`
Desde discord.py 2.6+, conectarse a voz requiere la librería `davey` además de `PyNaCl`, y no se instala salvo que se pida explícitamente. Se soluciona instalando el extra `voice` (ya viene así en `requirements.txt` — si aparece este error es porque las dependencias se instalaron antes de este fix):
```bash
pip install -r requirements.txt
```

**El bot aparece desconectado/offline en Discord**
Solo está en línea mientras el proceso `python bot.py` esté corriendo. Si se cierra la terminal o se presiona `Ctrl+C`, se desconecta.

**Los slash commands (`/play`) no aparecen**
Hay que ejecutar `!sync` una vez que el bot esté online (ver sección "Ejecutar el bot"). Si no se configuró `DEV_GUILD_ID`, puede tardar hasta una hora en propagarse a Discord.

**Error de yt-dlp tipo "Sign in to confirm you're not a bot"**
Ver la sección de limitaciones conocidas abajo.

## Limitaciones conocidas

- YouTube bloquea ocasionalmente la extracción de ciertos videos (streams 24/7, contenido restringido) sin cookies de una cuenta logueada, mostrando un error de "Sign in to confirm you're not a bot". Es una limitación de `yt-dlp` sin autenticación, no del bot — para resolverlo permanentemente haría falta pasar cookies de un navegador (`--cookies-from-browser`), lo cual queda fuera del alcance de este proyecto.
- El bot solo reproduce audio de YouTube (vía búsqueda o URL directa); no soporta Spotify, SoundCloud u otras plataformas.
