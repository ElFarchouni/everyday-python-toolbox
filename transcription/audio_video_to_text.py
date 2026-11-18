"""
audio_video_to_text.py: Transcribe a local audio or video file to text.

Uses OpenAI's Whisper locally (no API key, works offline after the first
model download). Handles mp3, wav, m4a, mp4, mkv, and anything FFmpeg reads.
Supports many languages, including French and Arabic.

Requirements:
    pip install openai-whisper
    FFmpeg must also be installed and on your PATH.

Usage:
    python audio_video_to_text.py path/to/recording.mp3
    (or run it with no arguments and paste the path when asked)

The transcript is printed and saved as a .txt file next to the media file.
"""

import sys
from pathlib import Path

import whisper

# Whisper model to use:
#   tiny   → smallest and fastest
#   base   → small with good accuracy (good default)
#   small  → better accuracy
#   medium → even better accuracy
#   large  → highest accuracy, but requires more resources
WHISPER_MODEL = "base"


def main():
    # Media file from the command line, or ask for it interactively
    if len(sys.argv) > 1:
        media_path = Path(sys.argv[1].strip('"'))
    else:
        media_path = Path(input("Audio/video file to transcribe: ").strip().strip('"'))

    if not media_path.is_file():
        print(f"File not found: {media_path}")
        sys.exit(1)

    print(f"\nLoading Whisper model '{WHISPER_MODEL}'...")
    model = whisper.load_model(WHISPER_MODEL)

    print("Transcribing... (this can take a few minutes)\n")
    result = model.transcribe(str(media_path), fp16=False)

    text = result["text"].strip()
    language = result.get("language", "unknown")

    # Save the transcript next to the media file
    output_file = media_path.with_suffix(".txt")
    output_file.write_text(text, encoding="utf-8")

    print("-" * 60)
    print(text)
    print("-" * 60)
    print(f"\nDetected language: {language}")
    print(f"Transcript saved to: {output_file}")


if __name__ == "__main__":
    main()
