"""
Meeting AI Analyser - Point d'entree unique
Lance transcription + analyse Claude + serveur web en threads
"""
import argparse
import multiprocessing
import os
import signal
import sys
import threading
import time
import webbrowser


def main():
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Meeting AI Analyser")
    parser.add_argument("--port", type=int, default=5555, help="Port du serveur web")
    parser.add_argument("--mic-device", type=int, default=None, help="ID du micro")
    parser.add_argument("--model", type=str, default="small",
                        help="Modele Whisper: tiny, base, small, medium, large-v3")
    parser.add_argument("--language", type=str, default="fr", help="Code langue")
    parser.add_argument("--segment", type=int, default=10, help="Duree segment (secondes)")
    parser.add_argument("--no-mic", action="store_true", help="Desactiver le micro")
    parser.add_argument("--no-analysis", action="store_true", help="Desactiver l'analyse Claude")
    parser.add_argument("--no-browser", action="store_true", help="Ne pas ouvrir le navigateur")
    args = parser.parse_args()

    stop_event = threading.Event()

    def shutdown(sig=None, frame=None):
        print("\n[MAIN] Arret en cours...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("=" * 60)
    print("  Meeting AI Analyser")
    print("=" * 60)

    # Thread 1: Transcription
    import live_transcribe
    t_transcribe = threading.Thread(
        target=live_transcribe.start,
        args=(stop_event,),
        kwargs={
            "mic_device": args.mic_device,
            "segment": args.segment,
            "model_size": args.model,
            "language": args.language,
            "no_mic": args.no_mic,
        },
        name="transcription",
        daemon=True,
    )
    t_transcribe.start()
    print("[MAIN] Transcription demarree")

    # Attendre que Whisper soit charge avant de lancer l'analyse
    time.sleep(5)

    # Thread 2: Analyse Claude (optionnel)
    t_analyst = None
    if not args.no_analysis:
        import analyst
        t_analyst = threading.Thread(
            target=analyst.start,
            args=(stop_event,),
            name="analyst",
            daemon=True,
        )
        t_analyst.start()
        print("[MAIN] Analyse Claude demarree")
    else:
        print("[MAIN] Analyse Claude desactivee")

    # Thread 3: Serveur web
    import server
    t_server = threading.Thread(
        target=server.start,
        args=(stop_event, args.port),
        name="server",
        daemon=True,
    )
    t_server.start()
    print(f"[MAIN] Serveur web demarre sur http://localhost:{args.port}")

    # Ouvrir le navigateur
    if not args.no_browser:
        time.sleep(2)
        webbrowser.open(f"http://localhost:{args.port}")

    print("\n[MAIN] Tout est lance. Ctrl+C pour arreter.\n")

    # Boucle principale - attend le signal d'arret
    try:
        while not stop_event.is_set():
            stop_event.wait(1)
    except KeyboardInterrupt:
        shutdown()

    print("[MAIN] Fermeture...")
    # Les threads daemon se terminent automatiquement
    time.sleep(1)
    os._exit(0)


if __name__ == "__main__":
    main()
