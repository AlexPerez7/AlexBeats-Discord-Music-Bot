# AlexBeats — Bot de Música para Discord

Bot de música para Discord con comandos de texto (`!play`) y slash commands (`/play`), cola de reproducción, botones de control persistentes y soporte correcto para múltiples servidores a la vez.

## Requisitos

- Python 3.10 o superior.
- [FFmpeg](https://ffmpeg.org/) instalado y disponible en el `PATH` del sistema (o configurable vía `.env`, ver abajo).
- Una aplicación/bot creada en el [Discord Developer Portal](https://discord.com/developers/applications) (ver paso a paso abajo).

## 1. Crear y configurar la aplicación en Discord

Si ya tenés una aplicación creada para este bot, saltá directo al paso donde corresponda.

1. Entrá a https://discord.com/developers/applications y creá una aplicación nueva (o abrí la que ya tengas).
2. En el menú izquierdo, andá a **Bot**:
   - Si nunca copiaste el token, hacé clic en **Reset Token** para generarlo y copiarlo — Discord no lo vuelve a mostrar después, guardalo en un lugar seguro. **Nunca lo compartas ni lo subas a git** (por eso vive en `.env`, que está en `.gitignore`).
   - Bajá hasta **Privileged Gateway Intents** y activá **Message Content Intent** (obligatorio para que el bot pueda leer comandos de texto como `!play`).
3. Andá a **OAuth2** en el menú izquierdo y bajá hasta **"Generador de URL de OAuth2"**:
   - En **Scopes**, marcá `bot` y `applications.commands`.
   - Al marcar `bot` aparece la sección **"Permisos del bot"** — marcá al menos:
     - Texto: `Enviar mensajes`, `Leer el historial de mensajes`, `Insertar enlaces`, `Usar comandos de barra diagonal`.
     - Voz: `Conectarse`, `Hablar`.
   - Al final de la página se genera la **URL** — copiala, abrila en una pestaña nueva, elegí tu servidor y confirmá la invitación.
4. (Opcional, recomendado) Activá el **modo desarrollador** en Discord (⚙️ Ajustes de usuario → Avanzado) para poder copiar IDs de servidor con clic derecho — lo vas a usar en el paso de sincronización rápida más abajo.

## 2. Instalación del proyecto

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

Copiá `.env.example` a `.env`:

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # Linux/Mac
```

Abrí `.env` y completá al menos el token del bot:

```env
DISCORD_BOT_TOKEN=el-token-de-tu-bot
```

Las demás variables de `.env` son opcionales (tienen valores por defecto razonables):

| Variable | Default | Descripción |
|---|---|---|
| `COMMAND_PREFIX` | `!` | Prefijo de los comandos de texto (los `/slash` siempre funcionan). |
| `DEFAULT_VOLUME` | `50` | Volumen inicial (0-100) al empezar a reproducir en un servidor. |
| `INACTIVITY_TIMEOUT_SECONDS` | `300` | Segundos sin música antes de que el bot se desconecte solo. |
| `DEV_GUILD_ID` | *(vacío)* | ID de tu servidor de pruebas (clic derecho sobre el ícono del servidor → Copiar ID, con el modo desarrollador activado). Con esto, `!sync` sincroniza los slash commands al instante en vez de tardar hasta 1 hora. |
| `FFMPEG_PATH` | `ffmpeg` | Ruta al ejecutable de FFmpeg, si no está en el `PATH`. |

## 3. Ejecutar el bot

```bash
python bot.py
```

Si conectó bien vas a ver en la consola algo como `Conectado como AlexBeats#0155` y el bot va a aparecer **en línea** en tu servidor.

Los slash commands (`/play`, `/skip`, etc.) no se sincronizan automáticamente al arrancar. La primera vez, o cada vez que agregues/cambies un comando, escribí en un canal donde el bot esté (con tu cuenta, la que creó la aplicación):

```
!sync
```

Si configuraste `DEV_GUILD_ID`, la sincronización es casi instantánea en ese servidor. Si lo dejás vacío, sincroniza globalmente, lo que puede tardar hasta una hora en propagarse.

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

## Solución de problemas

**`RuntimeError: davey library needed in order to use voice`** al usar `play`/`join`
Desde discord.py 2.6+, conectarse a voz requiere la librería `davey` además de `PyNaCl`, y no se instala salvo que se pida explícitamente. Se soluciona instalando el extra `voice` (ya viene así en `requirements.txt` — si ves este error es que instalaste las dependencias antes de este fix):
```bash
pip install -r requirements.txt
```

**El bot aparece desconectado/offline en Discord**
Solo está en línea mientras el proceso `python bot.py` esté corriendo en tu terminal. Si cerrás la ventana o hacés `Ctrl+C`, se desconecta.

**Los slash commands (`/play`) no aparecen**
Corré `!sync` una vez que el bot esté online (ver sección "Ejecutar el bot"). Si no configuraste `DEV_GUILD_ID`, puede tardar hasta una hora en propagarse a Discord.

**Error de yt-dlp tipo "Sign in to confirm you're not a bot"**
Ver la sección de limitaciones conocidas abajo.

## Limitaciones conocidas

- YouTube bloquea ocasionalmente la extracción de ciertos videos (streams 24/7, contenido restringido) sin cookies de una cuenta logueada, mostrando un error de "Sign in to confirm you're not a bot". Es una limitación de `yt-dlp` sin autenticación, no del bot — para resolverlo permanentemente haría falta pasar cookies de un navegador (`--cookies-from-browser`), lo cual queda fuera del alcance de este proyecto.
- El bot solo reproduce audio de YouTube (vía búsqueda o URL directa); no soporta Spotify, SoundCloud u otras plataformas.
