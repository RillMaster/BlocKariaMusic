# 🎵 Discord Music & Radio Bot

Un bot Discord moderne pour écouter de la musique et des radios en direct directement depuis ton serveur.  
Profite d'une interface intuitive, d’une gestion avancée de la file d’attente, et d’un accès instantané à plus de **20 radios françaises populaires**.

---

## ✨ Fonctionnalités

- 🎧 **Lecture de musique YouTube** : Utilise `/play` pour écouter une chanson ou une playlist.
- 📻 **Radios françaises en direct** : Écoute **NRJ, Skyrock, Fun Radio**, et bien d'autres via la commande `/radio`.
- 🎛️ **Contrôles interactifs** : Pause, reprise, skip, stop, volume, boucle.
- 🧠 **File d’attente intelligente** : Ajoute plusieurs morceaux, boucle une chanson ou toute la file.
- 🖥️ **Interface moderne** : Boutons et embeds pour une expérience fluide.

---

## 🛠️ Commandes principales

- `/play [titre ou lien]` : Joue une chanson ou une playlist YouTube.
- `/radio [nom de la radio]` : Lance une radio en direct.
- `/pause`, `/resume`, `/skip`, `/stop` : Contrôle la lecture.
- `/volume [0-100]` : Ajuste le volume.

---

## 📦 Prérequis

- Python **3.8+**
- **FFmpeg** installé et accessible dans le `PATH`
- Variable d’environnement `discord_token`

---

## 🚀 Installation

```bash
git clone https://github.com/Kylianbelon/BlocKariaMusic.git
cd BotMusicDiscord
pip install -r requirements.txt
Crée un fichier .env à la racine du projet avec ton token Discord :

env
Copier
Modifier
discord_token=VOTRE_TOKEN
Lance le bot :

bash
Copier
Modifier
python bot.py
📡 Radios disponibles
NRJ, Fun Radio, Skyrock, Nostalgie, RTL2, Chérie FM, Rire & Chansons, Radio FG, FIP, France Inter, France Info, France Musique, France Bleu, Europe 1, RTL, Virgin Radio, Latina, Générations, OÜI FM, Radio Nova, TSF Jazz, Sud Radio, Mouv’.

🙋 Support
Besoin d’aide ou envie de proposer une amélioration ?
Rejoins le serveur Discord de support :
👉 https://discord.com/invite/DHUyZUGKXB