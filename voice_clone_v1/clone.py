"""
Voice cloning with mlx-audio and Qwen3-TTS.

Record your voice:
    python clone.py --record [--record_seconds 10] [--output_path output/]

Clone a voice:
    python clone.py --clone --ref_audio path/to/voice.wav --text "Text to speak" [--play] [--output_path output/]
"""

import argparse
import os

import sounddevice as sd
import soundfile as sf

#MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit"
#MODEL = "fishaudio/fish-speech-1.5"
MODEL = "mlx-community/chatterbox-turbo-fp16"
SAMPLE_RATE = 24000


def cmd_record(args):
    os.makedirs(args.output_path, exist_ok=True)
    out_file = os.path.join(args.output_path, "my_voice.wav")

    print(f"Recording for {args.record_seconds} seconds... speak now!")
    audio = sd.rec(
        int(args.record_seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    print("Recording done.")

    sf.write(out_file, audio, SAMPLE_RATE)
    print(f"Saved: {out_file}")


def cmd_clone(args):
    from mlx_audio.tts.generate import generate_audio

    if not os.path.exists(args.ref_audio):
        raise FileNotFoundError(f"Reference audio not found: {args.ref_audio}")

    os.makedirs(args.output_path, exist_ok=True)

    print(f"Model:     {MODEL}")
    print(f"Ref audio: {args.ref_audio}")
    print(f"Output:    {os.path.join(args.output_path, 'my_cloned_voice.wav')}\n")

    generate_audio(
        text=args.text,
        model=MODEL,
        voice="vivian",
        ref_audio=args.ref_audio,
        ref_text=args.ref_text,
        output_path=args.output_path,
        file_prefix="my_cloned_voice",
        play=args.play,
        join_audio=True,
        verbose=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Record and clone voices using mlx-audio and Qwen3-TTS.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true",
                      help="Record your voice to a wav file")
    mode.add_argument("--clone", action="store_true",
                      help="Clone a voice from a reference audio file")

    # --record options
    parser.add_argument("--record_seconds", type=int, default=20,
                        help="Seconds to record (default: 10, used with --record)")

    # --clone options
    parser.add_argument("--ref_audio", type=str,
                        help="Path to reference audio file (required with --clone)")
    parser.add_argument("--text", type=str,
                        help="Text to synthesize in the cloned voice (required with --clone)")
    parser.add_argument("--ref_text", type=str, default=None,
                        help="Transcript of the reference audio (optional, improves cloning accuracy)")
    parser.add_argument("--play", action="store_true",
                        help="Play the generated audio through speakers (used with --clone)")

    # shared
    parser.add_argument("--output_path", type=str, default=".",
                        help="Directory to save output files (default: .)")

    args = parser.parse_args()

    if args.clone:
        if not args.ref_audio:
            parser.error("--clone requires --ref_audio")
        if not args.text:
            parser.error("--clone requires --text")

    if args.record:
        cmd_record(args)
    else:
        cmd_clone(args)


if __name__ == "__main__":
    main()
