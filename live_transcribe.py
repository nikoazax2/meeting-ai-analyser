"""
Meeting AI Analyser - Moteur de transcription audio temps reel
Capture audio systeme + micro et transcription via faster-whisper (local, gratuit)
Utilise PyAudioWPatch WASAPI loopback (Windows)

Capture les 2 sources :
  - WASAPI loopback = audio systeme (les autres en reunion)
  - Micro = ta voix

Usage:
    python live_transcribe.py                  # Mode normal (loopback + micro)
    python live_transcribe.py --no-mic         # Loopback uniquement (pas de micro)
    python live_transcribe.py --list-devices   # Lister les peripheriques audio
    python live_transcribe.py --mic-device 18  # Choisir un micro specifique
    python live_transcribe.py --segment 15     # Segments de 15 secondes
    python live_transcribe.py --model base     # Modele plus leger
"""

import argparse
import datetime
import os
import signal
import sys
import threading
import time
import wave

# Ajouter le chemin des DLLs NVIDIA CUDA avant tout import CUDA
_nvidia_path = os.path.join(
    os.path.expanduser("~"),
    "AppData", "Local", "Packages",
    "PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0",
    "LocalCache", "local-packages", "Python313",
    "site-packages", "nvidia", "cublas", "bin"
)
if os.path.isdir(_nvidia_path):
    os.environ["PATH"] = _nvidia_path + os.pathsep + os.environ.get("PATH", "")
    os.add_dll_directory(_nvidia_path)

import numpy as np
import pyaudiowpatch as pyaudio

# Fichiers de sortie
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "transcription_live.txt")
OUTPUT_LATEST = os.path.join(SCRIPT_DIR, "transcription_latest.txt")
AUDIO_TEMP = os.path.join(SCRIPT_DIR, "temp_segment.wav")

# Config
DEFAULT_SEGMENT_DURATION = 10
SAMPLE_RATE = 16000
SILENCE_THRESHOLD = 0.001

# Flag d'arret (threading.Event pour mode module, global pour standalone)
_stop_event = None
running = True


def signal_handler(sig, frame):
    global running
    print("\n[STOP] Arret en cours...")
    running = False
    if _stop_event:
        _stop_event.set()


def list_devices():
    """Liste les peripheriques audio"""
    p = pyaudio.PyAudio()
    print("\n=== Peripheriques audio ===\n")
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        direction = "IN" if dev["maxInputChannels"] > 0 else ""
        if dev["maxOutputChannels"] > 0:
            direction += "/OUT" if direction else "OUT"
        loopback = " [LOOPBACK]" if dev.get("isLoopbackDevice", False) else ""
        print(f"  [{i:2d}] {dev['name']:<55s} [{direction:<6s}]{loopback}")
    p.terminate()


def find_wasapi_loopback(p):
    """Trouve le device WASAPI loopback automatiquement"""
    try:
        wasapi_info = p.get_default_wasapi_loopback()
        print(f"[AUTO] WASAPI loopback: {wasapi_info['name']}")
        return wasapi_info
    except Exception:
        pass

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev.get("isLoopbackDevice", False):
            print(f"[AUTO] Loopback device: [{i}] {dev['name']}")
            return dev

    return None


def find_mic_device(p, mic_device_id=None):
    """Trouve le micro par defaut ou par ID"""
    if mic_device_id is not None:
        dev = p.get_device_info_by_index(mic_device_id)
        print(f"[MIC]  Micro: [{mic_device_id}] {dev['name']}")
        return dev

    # Chercher le micro par defaut via WASAPI
    try:
        default_info = p.get_default_wasapi_device(is_input=True)
        print(f"[MIC]  Micro WASAPI: {default_info['name']}")
        return default_info
    except Exception:
        pass

    # Fallback: micro par defaut general
    try:
        default_idx = p.get_default_input_device_info()["index"]
        dev = p.get_device_info_by_index(default_idx)
        print(f"[MIC]  Micro par defaut: [{default_idx}] {dev['name']}")
        return dev
    except Exception:
        return None


def is_silence(audio_data, threshold=SILENCE_THRESHOLD):
    rms = np.sqrt(np.mean(audio_data ** 2))
    return rms < threshold


def load_whisper_model(model_size="small"):
    print(f"[INIT] Chargement du modele Whisper '{model_size}'...")
    print("[INIT] (Premier lancement = telechargement du modele, patientez...)")

    from faster_whisper import WhisperModel

    try:
        model = WhisperModel(model_size, device="cuda", compute_type="float16")
        print("[INIT] Modele charge sur GPU (CUDA)")
    except Exception:
        try:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            print("[INIT] Modele charge sur CPU (int8)")
        except Exception as e:
            print(f"[ERREUR] Impossible de charger le modele: {e}")
            return None

    return model


def transcribe_segment(model, audio_data, sample_rate, language="fr"):
    """Transcrit un segment audio mono"""
    if is_silence(audio_data):
        return None

    audio_int16 = (audio_data * 32767).astype(np.int16)
    with wave.open(AUDIO_TEMP, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    try:
        segments, info = model.transcribe(
            AUDIO_TEMP,
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=500,
                speech_pad_ms=300,
            ),
        )
        text = " ".join([s.text.strip() for s in segments])
        return text if text.strip() else None
    except Exception as e:
        print(f"[ERREUR] Transcription: {e}")
        return None


def deduplicate(new_text, prev_text, min_overlap=5):
    """Supprime le debut du nouveau texte s'il repete la fin du precedent"""
    if not prev_text or not new_text:
        return new_text

    prev_words = prev_text.lower().split()
    new_words = new_text.split()
    new_words_lower = [w.lower() for w in new_words]

    # Chercher le plus long chevauchement (entre 3 et la moitie du texte)
    max_check = min(len(prev_words), len(new_words_lower), 20)
    best_overlap = 0

    for overlap_len in range(min_overlap, max_check + 1):
        tail = prev_words[-overlap_len:]
        head = new_words_lower[:overlap_len]
        if tail == head:
            best_overlap = overlap_len

    if best_overlap >= min_overlap:
        return " ".join(new_words[best_overlap:])

    return new_text


def to_mono_16k(raw_data, channels, source_sr):
    """Convertit raw bytes int16 -> numpy float32 mono 16kHz"""
    audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio_np = audio_np.reshape(-1, channels)
        audio_np = np.mean(audio_np, axis=1)
    if source_sr != SAMPLE_RATE:
        from scipy.signal import resample
        num_samples = int(len(audio_np) * SAMPLE_RATE / source_sr)
        audio_np = resample(audio_np, num_samples).astype(np.float32)
    return audio_np


def start(stop_event, mic_device=None, segment=DEFAULT_SEGMENT_DURATION,
          model_size="small", language="fr", no_mic=False):
    """Point d'entree pour le mode module (appele depuis main.py en thread)"""
    global _stop_event, running
    _stop_event = stop_event
    running = True
    _run(stop_event=stop_event, mic_device=mic_device, segment=segment,
         model_size=model_size, language=language, no_mic=no_mic)


def _run(stop_event=None, mic_device=None, segment=DEFAULT_SEGMENT_DURATION,
         model_size="small", language="fr", no_mic=False):
    """Logique principale de transcription"""
    global running

    def is_running():
        if stop_event and stop_event.is_set():
            return False
        return running

    p = pyaudio.PyAudio()

    # === Device loopback (audio systeme) ===
    loopback_dev = find_wasapi_loopback(p)
    if loopback_dev is None:
        print("[ERREUR] Aucun device WASAPI loopback trouve.")
        p.terminate()
        return

    lb_channels = int(loopback_dev["maxInputChannels"])
    lb_sr = int(loopback_dev["defaultSampleRate"])
    lb_index = int(loopback_dev["index"])

    # === Device micro ===
    mic_dev = None
    mic_channels = 1
    mic_sr = 48000
    mic_index = None
    use_mic = not no_mic

    if use_mic:
        mic_dev = find_mic_device(p, mic_device)
        if mic_dev is None:
            print("[WARN] Aucun micro trouve, mode loopback uniquement.")
            use_mic = False
        else:
            mic_channels = int(mic_dev["maxInputChannels"])
            mic_sr = int(mic_dev["defaultSampleRate"])
            mic_index = int(mic_dev["index"])

    print(f"\n[CONFIG] Loopback: {loopback_dev['name']} ({lb_channels}ch, {lb_sr}Hz)")
    if use_mic:
        print(f"[CONFIG] Micro:    {mic_dev['name']} ({mic_channels}ch, {mic_sr}Hz)")
    else:
        print(f"[CONFIG] Micro:    desactive")
    print(f"[CONFIG] Segments: {segment}s")
    print(f"[CONFIG] Modele: {model_size}, Langue: {language}")
    print(f"[CONFIG] Sortie: {OUTPUT_FILE}")

    # Charger Whisper
    model = load_whisper_model(model_size)
    if model is None:
        p.terminate()
        return

    # Init fichier sortie
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== Transcription Live - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")

    print("\n" + "=" * 60)
    print("  TRANSCRIPTION EN COURS - Ctrl+C pour arreter")
    if use_mic:
        print("  Sources: audio systeme + micro")
    else:
        print("  Source: audio systeme uniquement")
    print("=" * 60 + "\n")

    # Buffers thread-safe
    loopback_lock = threading.Lock()
    mic_lock = threading.Lock()
    loopback_frames = []
    mic_frames = []

    def loopback_callback(in_data, frame_count, time_info, status):
        with loopback_lock:
            loopback_frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    def mic_callback(in_data, frame_count, time_info, status):
        with mic_lock:
            mic_frames.append(in_data)
        return (in_data, pyaudio.paContinue)

    samples_per_segment = segment * lb_sr
    segment_count = 0
    prev_text = ""

    try:
        # Ouvrir stream loopback
        stream_lb = p.open(
            format=pyaudio.paInt16,
            channels=lb_channels,
            rate=lb_sr,
            input=True,
            input_device_index=lb_index,
            frames_per_buffer=int(lb_sr * 0.5),
            stream_callback=loopback_callback,
        )
        stream_lb.start_stream()

        # Ouvrir stream micro
        stream_mic = None
        if use_mic:
            stream_mic = p.open(
                format=pyaudio.paInt16,
                channels=mic_channels,
                rate=mic_sr,
                input=True,
                input_device_index=mic_index,
                frames_per_buffer=int(mic_sr * 0.5),
                stream_callback=mic_callback,
            )
            stream_mic.start_stream()

        while is_running() and stream_lb.is_active():
            time.sleep(0.5)

            # Verifier si on a assez de samples loopback
            with loopback_lock:
                total_bytes = sum(len(f) for f in loopback_frames)
            total_samples = total_bytes // (2 * lb_channels)

            if total_samples >= samples_per_segment:
                segment_count += 1

                # Recuperer les frames loopback
                with loopback_lock:
                    lb_raw = b"".join(loopback_frames)
                    loopback_frames.clear()

                # Recuperer les frames micro
                mic_raw = None
                if use_mic:
                    with mic_lock:
                        mic_raw = b"".join(mic_frames)
                        mic_frames.clear()

                # Convertir en mono 16kHz
                lb_mono = to_mono_16k(lb_raw, lb_channels, lb_sr)

                if use_mic and mic_raw and len(mic_raw) > 0:
                    mic_mono = to_mono_16k(mic_raw, mic_channels, mic_sr)

                    # Debug: afficher les niveaux
                    lb_rms = np.sqrt(np.mean(lb_mono ** 2))
                    mic_rms = np.sqrt(np.mean(mic_mono ** 2))
                    print(f"[levels: loopback={lb_rms:.4f}, mic={mic_rms:.4f}] ", end="", flush=True)

                    # Aligner les tailles (prendre la plus courte)
                    min_len = min(len(lb_mono), len(mic_mono))
                    lb_mono = lb_mono[:min_len]
                    mic_mono = mic_mono[:min_len]

                    # Mixer : additionner les deux sources
                    mixed = lb_mono + mic_mono

                    # Normaliser pour eviter le clipping
                    peak = np.max(np.abs(mixed))
                    if peak > 0.95:
                        mixed = mixed * (0.95 / peak)

                    audio_final = mixed
                else:
                    audio_final = lb_mono

                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"[{timestamp}] Segment #{segment_count}...", end=" ", flush=True)

                raw_text = transcribe_segment(model, audio_final, SAMPLE_RATE, language)

                if raw_text:
                    text = deduplicate(raw_text, prev_text)
                    prev_text = raw_text

                    if not text.strip():
                        print("(doublon)")
                        continue

                    line = f"[{timestamp}] {text}"
                    print(f"\n  >> {text}")

                    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                        f.write(line + "\n")

                    with open(OUTPUT_LATEST, "w", encoding="utf-8") as f:
                        f.write(text)
                else:
                    print("(silence)")

        stream_lb.stop_stream()
        stream_lb.close()
        if stream_mic:
            stream_mic.stop_stream()
            stream_mic.close()

    except Exception as e:
        print(f"\n[ERREUR] {e}")
        import traceback
        traceback.print_exc()

    finally:
        p.terminate()
        if os.path.exists(AUDIO_TEMP):
            os.remove(AUDIO_TEMP)
        print(f"\n[FIN] Transcription sauvegardee dans: {OUTPUT_FILE}")


def main():
    """Point d'entree standalone (ligne de commande)"""
    global running
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description="Meeting AI Analyser - Transcription")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--no-mic", action="store_true", help="Desactiver la capture micro")
    parser.add_argument("--mic-device", type=int, default=None, help="ID du micro")
    parser.add_argument("--segment", type=int, default=DEFAULT_SEGMENT_DURATION)
    parser.add_argument("--model", type=str, default="small",
                        help="tiny, base, small, medium, large-v3")
    parser.add_argument("--language", type=str, default="fr")
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    _run(mic_device=args.mic_device, segment=args.segment,
         model_size=args.model, language=args.language, no_mic=args.no_mic)


if __name__ == "__main__":
    main()
