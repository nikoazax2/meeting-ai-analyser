"""
Meeting AI Analyser - Module d'analyse IA
Lit la transcription toutes les 60s et lance Claude pour analyser la reunion en cours
"""
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTION_FILE = os.path.join(SCRIPT_DIR, "transcription_live.txt")
ANALYSIS_FILE = os.path.join(SCRIPT_DIR, "analyse_reunion.md")

PROMPT = """Tu es un assistant de reunion en temps reel. Voici la transcription live d'une reunion en cours.

INSTRUCTIONS :
1. Resume les sujets abordes
2. Liste les decisions prises
3. Identifie les questions ouvertes
4. Propose des solutions techniques si pertinent
5. Liste les actions a faire (qui fait quoi)

Sois concis et structure. Format Markdown.

TRANSCRIPTION :
{transcription}
"""


def read_transcription():
    if not os.path.exists(TRANSCRIPTION_FILE):
        return None
    with open(TRANSCRIPTION_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def analyze_with_claude(text):
    prompt = PROMPT.format(transcription=text)

    # Ecrire le prompt dans un fichier temp pour eviter les problemes de quotes Windows
    prompt_file = os.path.join(SCRIPT_DIR, "temp_prompt.txt")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    # Chercher claude dans les chemins connus
    claude_cmd = "claude"
    for path in [
        os.path.expanduser("~/AppData/Roaming/npm/claude.cmd"),
        "C:/Program Files/nodejs/claude.cmd",
    ]:
        if os.path.exists(path):
            claude_cmd = path
            break

    try:
        result = subprocess.run(
            [claude_cmd, "--print"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            print(f"[ERREUR] Claude: {result.stderr[:200] if result.stderr else 'pas de reponse'}")
            return None
    except FileNotFoundError:
        print("[ERREUR] 'claude' non trouve dans le PATH. Installez Claude Code.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("[WARN] Claude a mis trop de temps, on retry au prochain cycle.")
        return None
    finally:
        if os.path.exists(prompt_file):
            os.remove(prompt_file)


def start(stop_event, interval=60):
    """Point d'entree pour le mode module (appele depuis main.py en thread)"""
    _run(stop_event=stop_event, interval=interval)


def _run(stop_event=None, interval=60):
    """Logique principale d'analyse"""
    last_content = ""

    print("[ANALYST] Module analyse IA demarre")
    print(f"[ANALYST] Intervalle: {interval}s")

    while True:
        if stop_event and stop_event.is_set():
            break

        content = read_transcription()

        if content and content != last_content and len(content) > 50:
            last_content = content
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] Nouvelle transcription detectee, analyse en cours...")

            analysis = analyze_with_claude(content)

            if analysis:
                with open(ANALYSIS_FILE, "w", encoding="utf-8") as f:
                    f.write(f"# Analyse de reunion - {time.strftime('%Y-%m-%d %H:%M')}\n\n")
                    f.write(analysis)
                    f.write("\n")

                print(f"[{timestamp}] Analyse sauvegardee dans {ANALYSIS_FILE}")
            else:
                print(f"[{timestamp}] Pas d'analyse retournee.")
        else:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] En attente de nouvelle transcription...")

        if stop_event:
            stop_event.wait(interval)
        else:
            time.sleep(interval)

    print("[ANALYST] Module analyse arrete.")


def main():
    """Point d'entree standalone"""
    print("=" * 60)
    print("  MEETING AI ANALYSER - Module Analyse")
    print(f"  Lecture de: {TRANSCRIPTION_FILE}")
    print(f"  Resultat dans: {ANALYSIS_FILE}")
    print("  Ctrl+C pour arreter")
    print("=" * 60 + "\n")
    try:
        _run()
    except KeyboardInterrupt:
        print("\n[STOP] Arret analyse.")


if __name__ == "__main__":
    main()
