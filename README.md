# Meeting AI Analyser

Outil de transcription audio temps reel et d'analyse IA des reunions pour Windows.

Capture l'audio systeme (WASAPI loopback) et le micro, transcrit localement via Whisper, et analyse automatiquement le contenu avec Claude AI. Interface web temps reel sur `http://localhost:5555`.

---

## Table des matieres

- [Fonctionnalites](#fonctionnalites)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Utilisation](#utilisation)
- [Interface web](#interface-web)
- [Configuration](#configuration)
- [Fichiers du projet](#fichiers-du-projet)
- [API du serveur](#api-du-serveur)
- [Details techniques](#details-techniques)
- [Troubleshooting](#troubleshooting)

---

## Fonctionnalites

### Transcription temps reel
- Capture simultanee de l'**audio systeme** (Teams, Zoom, navigateur...) et du **micro**
- Transcription locale via **faster-whisper** (aucune donnee envoyee a l'exterieur)
- Support GPU (CUDA) pour transcription acceleree, fallback CPU automatique
- Detection de silence (VAD) pour ignorer les pauses
- Deduplication intelligente entre segments contigus

### Analyse IA automatique
- Analyse de la reunion toutes les 60 secondes via **Claude Code CLI**
- Resume structure en Markdown :
  - Sujets abordes
  - Decisions prises
  - Questions ouvertes
  - Solutions techniques proposees
  - Actions a faire (qui fait quoi)
- Se declenche uniquement quand la transcription change

### Interface web
- Dashboard split-panel (transcription a gauche, analyse a droite)
- Streaming temps reel via Server-Sent Events (SSE)
- Polling de secours automatique si SSE echoue
- Auto-scroll intelligent (pause si l'utilisateur scroll manuellement)
- Indicateur de connexion (vert/rouge)
- Compteur de segments et horodatage
- Bouton Reset pour repartir a zero
- Theme sombre (GitHub-like)
- Rendu Markdown pour l'analyse

---

## Architecture

```
+-------------------+     +-------------------+     +-------------------+
|  Audio Hardware   |     |   analyst.py      |     |   index.html      |
|  (Systeme + Mic)  |     |  Analyse IA       |     |  Interface web    |
+--------+----------+     +--------+----------+     +--------+----------+
         |                         |                          |
         v                         v                          v
+-------------------+     +-------------------+     +-------------------+
| live_transcribe.py|---->| analyse_reunion.md|<----| server.py (Flask) |
| Capture + Whisper |     | Resultat analyse  |     | API + SSE         |
+--------+----------+     +-------------------+     +--------+----------+
         |                                                    ^
         v                                                    |
+-------------------+                                         |
|transcription_     |---------------------------------------->+
|   live.txt        |    Lu par server.py via /api/stream
+-------------------+
```

### Flux de donnees

1. **`live_transcribe.py`** capture l'audio en segments de 10s, transcrit via Whisper, ecrit dans `transcription_live.txt`
2. **`analyst.py`** lit `transcription_live.txt` toutes les 60s, envoie a Claude, ecrit le resultat dans `analyse_reunion.md`
3. **`server.py`** surveille les deux fichiers et les expose via une API REST + SSE
4. **`index.html`** se connecte en SSE et affiche les mises a jour en temps reel

---

## Prerequisites

### Obligatoires

| Dependance | Version | Usage |
|-----------|---------|-------|
| **Python** | 3.10+ (teste avec 3.13) | Runtime |
| **faster-whisper** | latest | Transcription speech-to-text |
| **pyaudiowpatch** | latest | Capture audio WASAPI (Windows) |
| **numpy** | latest | Traitement audio |
| **scipy** | latest | Resampling audio |
| **flask** | latest | Serveur web |
| **psutil** | latest | Gestion des processus |

### Optionnels

| Dependance | Usage |
|-----------|-------|
| **NVIDIA GPU + CUDA 11.8+** | Transcription acceleree (x5-10 plus rapide) |
| **Claude Code CLI** | Analyse IA des reunions (module `analyst.py`) |

### Systeme

- **Windows 10/11** uniquement (WASAPI loopback est une API Windows)
- Un **peripherique de sortie audio** actif (pour le loopback)
- Un **micro** (optionnel, peut etre desactive avec `--no-mic`)

---

## Installation

### 1. Installer les dependances Python

```bash
pip install faster-whisper pyaudiowpatch numpy scipy flask psutil
```

### 2. (Optionnel) Support GPU NVIDIA

Si vous avez une carte NVIDIA compatible CUDA :

```bash
pip install nvidia-cublas-cu11 nvidia-cudnn-cu11
```

Le script detecte automatiquement la disponibilite du GPU et bascule sur CPU si besoin.

### 3. (Optionnel) Installer Claude Code CLI

Pour l'analyse IA automatique des reunions :

```bash
npm install -g @anthropic-ai/claude-code
```

Sans Claude Code, la transcription fonctionne normalement mais sans analyse.

### 4. Premier lancement

Au premier lancement, Whisper telecharge automatiquement le modele choisi (~500 Mo pour `small`). Ce telechargement n'a lieu qu'une seule fois.

---

## Utilisation

### Methode 1 : Lanceur silencieux (recommande)

Double-cliquer sur **`launcher.vbs`**. Cela :
1. Lance la transcription en arriere-plan
2. Lance l'analyseur Claude (apres 8s)
3. Lance le serveur web
4. Ouvre automatiquement `http://localhost:5555` dans le navigateur

Aucune fenetre console visible. Pour arreter : bouton Stop dans l'interface web ou fermer l'onglet.

> **Note :** Les chemins dans `launcher.vbs` sont en dur. Si vous deplacez le projet, mettez-les a jour.

### Methode 2 : Lanceur console

```bash
start.bat
```

Affiche les logs de transcription dans la console. Utile pour le debug.

### Methode 3 : Lancement manuel (3 terminaux)

```bash
# Terminal 1 : Transcription
python live_transcribe.py

# Terminal 2 : Analyse IA (attendre 8s que Whisper soit charge)
python analyst.py

# Terminal 3 : Serveur web
python server.py
```

Puis ouvrir `http://localhost:5555`.

---

## Interface web

L'interface est accessible sur `http://localhost:5555` et se compose de :

### Header
- **Pastille verte pulsante** : connexion SSE active
- **Pastille rouge fixe** : connexion perdue
- **Bouton Reset** : efface transcription et analyse, repart a zero
- **Compteur de segments** : nombre de segments transcrits
- **Horodatage** : derniere mise a jour recue

### Panneau gauche : Transcription
- Affiche chaque segment avec son horodatage `[HH:MM:SS]`
- Les 3 derniers segments sont surlignés en bleu
- Auto-scroll vers le bas (se met en pause si vous scrollez manuellement)

### Panneau droit : Analyse Claude
- Resume structure de la reunion en Markdown
- Mis a jour automatiquement toutes les 60s
- Rendu : titres, listes, gras, italique, code

### Arret
- **Bouton Stop** ou **fermeture de l'onglet** : envoie un signal d'arret a tous les processus
- **Ctrl+C** dans la console si lance manuellement

---

## Configuration

### Options de ligne de commande

```
python live_transcribe.py [OPTIONS]
```

| Option | Defaut | Description |
|--------|--------|-------------|
| `--list-devices` | - | Liste les peripheriques audio et quitte |
| `--no-mic` | false | Desactive la capture micro (loopback seul) |
| `--mic-device ID` | auto | Index du peripherique micro a utiliser |
| `--segment N` | 10 | Duree des segments en secondes |
| `--model SIZE` | small | Modele Whisper : `tiny`, `base`, `small`, `medium`, `large-v3` |
| `--language LANG` | fr | Code langue ISO (fr, en, de, es...) |

### Choix du modele Whisper

| Modele | Taille | RAM GPU | Qualite | Vitesse |
|--------|--------|---------|---------|---------|
| `tiny` | 39 Mo | ~1 Go | Basique | Tres rapide |
| `base` | 74 Mo | ~1 Go | Correcte | Rapide |
| `small` | 244 Mo | ~2 Go | Bonne | Moyen |
| `medium` | 769 Mo | ~5 Go | Tres bonne | Lent |
| `large-v3` | 1.5 Go | ~10 Go | Excellente | Tres lent |

> **Recommandation :** `small` offre le meilleur compromis qualite/vitesse pour le francais.

### Parametres internes modifiables

| Parametre | Fichier | Valeur | Description |
|-----------|---------|--------|-------------|
| `DEFAULT_SEGMENT_DURATION` | live_transcribe.py | 10 | Duree segment (secondes) |
| `SILENCE_THRESHOLD` | live_transcribe.py | 0.001 | Seuil RMS de silence |
| `SAMPLE_RATE` | live_transcribe.py | 16000 | Frequence echantillonnage |
| `interval` | analyst.py | 60 | Frequence d'analyse (secondes) |
| `port` | server.py | 5555 | Port du serveur web |

---

## Fichiers du projet

### Code source

| Fichier | Lignes | Role |
|---------|--------|------|
| `live_transcribe.py` | 428 | Moteur de capture audio + transcription Whisper |
| `server.py` | 112 | Serveur Flask (API REST + SSE) |
| `analyst.py` | 123 | Module d'analyse IA via Claude CLI |
| `index.html` | 504 | Interface web (HTML + CSS + JS embedded) |

### Lanceurs

| Fichier | Role |
|---------|------|
| `start.bat` | Lanceur console (affiche les logs) |
| `launcher.vbs` | Lanceur silencieux (arriere-plan, ouvre le navigateur) |

### Fichiers generes (runtime)

| Fichier | Role |
|---------|------|
| `transcription_live.txt` | Transcription horodatee complete |
| `transcription_latest.txt` | Dernier segment transcrit uniquement |
| `analyse_reunion.md` | Derniere analyse Claude en Markdown |
| `temp_segment.wav` | Fichier audio temporaire (auto-supprime) |
| `temp_prompt.txt` | Prompt temporaire pour Claude (auto-supprime) |

---

## API du serveur

Le serveur Flask expose les endpoints suivants sur `http://localhost:5555` :

### `GET /`
Sert l'interface web (`index.html`).

### `GET /api/transcription`
Retourne la transcription courante.
```json
{
  "content": "[08:30:15] Bonjour, on commence...\n[08:30:25] Oui, premier point...",
  "mtime": 1708700000.123
}
```

### `GET /api/analysis`
Retourne l'analyse Claude courante.
```json
{
  "content": "# Analyse de reunion - 2026-02-23 10:30\n\n## Sujets abordes\n...",
  "mtime": 1708700060.456
}
```

### `GET /api/stream`
Endpoint SSE (Server-Sent Events). Envoie des evenements quand la transcription ou l'analyse change.
```
data: {"type": "transcription", "content": "..."}
data: {"type": "analysis", "content": "..."}
```
Intervalle de verification : 2 secondes.

### `POST /api/reset`
Reinitialise la transcription et l'analyse. Retourne `{"status": "reset"}`.

### `GET /api/stop`
Arrete tous les processus Meeting AI Analyser. Retourne `{"status": "stopped"}`.

---

## Details techniques

### Capture audio

- **WASAPI Loopback** : capture tout l'audio en sortie du systeme (ce que vous entendez dans vos ecouteurs/HP)
- **Micro** : capture via le peripherique d'entree par defaut ou un device specifie
- Les deux flux sont convertis en **mono 16kHz** (format requis par Whisper) puis **mixes** ensemble
- **Normalisation** automatique si le signal depasse 95% pour eviter le clipping
- **Threading** : chaque source audio a son propre callback thread-safe avec lock

### Transcription Whisper

- **Beam search** : taille 5 (compromis qualite/vitesse)
- **VAD** (Voice Activity Detection) active : ignore les segments silencieux
- **Min silence** : 500ms (seuil de coupure)
- **Speech padding** : 300ms (marge autour de la parole detectee)
- Le modele est charge une seule fois au demarrage, les segments sont transcrits a la volee

### Deduplication

Evite les repetitions entre segments consecutifs :
1. Compare les N derniers mots du segment precedent avec les N premiers du nouveau
2. Si chevauchement >= 5 mots, supprime la partie dupliquee du nouveau segment
3. Comparaison insensible a la casse, max 20 mots verifies

### Detection GPU

Au demarrage, le script tente dans l'ordre :
1. **CUDA float16** (GPU NVIDIA) - performance maximale
2. **CPU int8** (fallback) - fonctionne partout, plus lent

Le chemin des DLL NVIDIA est ajoute automatiquement au PATH (specifique Python 3.13 Windows Store).

### Analyse Claude

- Utilise `claude --print` en mode non-interactif
- Le prompt est ecrit dans un fichier temporaire pour eviter les problemes de quotes Windows
- Timeout : 120 secondes
- Se declenche uniquement si :
  - La transcription a change depuis la derniere analyse
  - Le contenu depasse 50 caracteres

---

## Troubleshooting

### "Aucun device WASAPI loopback trouve"
- Verifiez qu'un peripherique de sortie audio est actif (casque, HP, sortie virtuelle)
- Sur certains systemes, le loopback WASAPI n'est disponible que si de l'audio est en cours de lecture

### "Module faster_whisper non trouve"
```bash
pip install faster-whisper
```

### La transcription est lente (CPU)
- Installez les drivers NVIDIA + CUDA pour utiliser le GPU
- Ou utilisez un modele plus leger : `--model tiny` ou `--model base`

### "'claude' non trouve dans le PATH"
- Installez Claude Code CLI : `npm install -g @anthropic-ai/claude-code`
- Ou lancez sans le module analyst.py (transcription seule)

### L'interface web ne se charge pas
- Verifiez que `server.py` est lance et ecoute sur le port 5555
- Verifiez qu'aucun autre processus n'utilise le port : `netstat -ano | findstr 5555`

### Le micro n'est pas detecte
- Listez les peripheriques : `python live_transcribe.py --list-devices`
- Selectionnez manuellement : `python live_transcribe.py --mic-device ID`

### La transcription contient des repetitions
- Augmentez la duree des segments : `--segment 15` ou `--segment 20`
- Le mecanisme de deduplication gere la plupart des cas, mais des segments tres courts peuvent generer des doublons

---

## Licence

Projet interne Neoteem. Usage restreint.
