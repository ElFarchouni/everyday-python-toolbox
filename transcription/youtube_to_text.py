"""
YouTube Video -> Text Transcript
================================
1. Tries to retrieve existing YouTube captions.
2. If captions are unavailable, downloads audio with yt-dlp.
3. Transcribes the audio using Whisper.
4. Saves the result as a UTF-8 .txt file.

First-time installation:
    pip install -U youtube-transcript-api yt-dlp openai-whisper

Whisper fallback also requires FFmpeg.
"""

import os
import re
import sys
from urllib.parse import urlparse, parse_qs


# ============================================================
# SETTINGS
# ============================================================

# Folders are created next to this script, no matter where it is run from
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FOLDER = os.path.join(SCRIPT_DIR, "transcripts")

TEMP_FOLDER = os.path.join(SCRIPT_DIR, "temp_audio")

# Whisper model used only when YouTube captions are unavailable.
# Options: tiny, base, small, medium, large
WHISPER_MODEL = "base"


# ============================================================
# GET VIDEO ID
# ============================================================

def get_video_id(url):
    """Extract the YouTube video ID from different URL formats."""

    parsed = urlparse(url)

    # youtu.be/VIDEO_ID
    if parsed.hostname in ("youtu.be", "www.youtu.be"):
        return parsed.path.lstrip("/").split("/")[0]

    # youtube.com URLs
    if parsed.hostname in (
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
    ):
        # youtube.com/watch?v=VIDEO_ID
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]

        # youtube.com/shorts/VIDEO_ID
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/")[2]

        # youtube.com/embed/VIDEO_ID
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2]

        # youtube.com/live/VIDEO_ID
        if parsed.path.startswith("/live/"):
            return parsed.path.split("/")[2]

    raise ValueError("Could not recognize this YouTube URL.")


# ============================================================
# CLEAN FILE NAME
# ============================================================

def clean_filename(name):
    """Remove characters that cannot safely be used in filenames."""

    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", " ", name).strip()

    return name[:150] if name else "youtube_transcript"


# ============================================================
# GET VIDEO TITLE
# ============================================================

def get_video_title(url):
    """Get the YouTube video title using yt-dlp."""

    try:
        import yt_dlp

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)

        return info.get("title", "youtube_transcript")

    except Exception:
        return "youtube_transcript"


# ============================================================
# METHOD 1: YOUTUBE CAPTIONS
# ============================================================

def get_youtube_captions(video_id):
    """
    Try to retrieve existing YouTube captions.

    Preference:
        English
        French
        Arabic
        Italian
        Any other available language
    """

    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()

    transcript_list = api.list(video_id)

    preferred_languages = ["en", "fr", "ar", "it"]

    transcript = None

    # Try preferred languages
    for language in preferred_languages:
        try:
            transcript = transcript_list.find_transcript([language])
            break
        except Exception:
            pass

    # Otherwise use first available transcript
    if transcript is None:
        transcript = next(iter(transcript_list))

    fetched = transcript.fetch()

    lines = []

    for item in fetched:
        text = item.text.strip()

        if text:
            lines.append(text)

    full_text = "\n".join(lines)

    return full_text, transcript.language


# ============================================================
# METHOD 2: WHISPER FALLBACK
# ============================================================

def transcribe_with_whisper(url, video_id):
    """
    Download audio with yt-dlp and transcribe it using Whisper.
    """

    import yt_dlp
    import whisper

    print("\nDownloading audio...")

    os.makedirs(TEMP_FOLDER, exist_ok=True)

    audio_template = os.path.join(
        TEMP_FOLDER,
        f"{video_id}.%(ext)s"
    )

    options = {
        "format": "bestaudio/best",

        "outtmpl": audio_template,

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],

        "quiet": False,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    audio_file = os.path.join(
        TEMP_FOLDER,
        f"{video_id}.mp3"
    )

    if not os.path.exists(audio_file):
        raise FileNotFoundError(
            "Audio file was not created. "
            "Check that FFmpeg is installed."
        )

    print("\nLoading Whisper model:", WHISPER_MODEL)

    model = whisper.load_model(WHISPER_MODEL)

    print("\nTranscribing audio...")
    print("This can take several minutes.\n")

    result = model.transcribe(
        audio_file,
        fp16=False
    )

    text = result["text"].strip()

    language = result.get(
        "language",
        "unknown"
    )

    # Delete temporary audio
    try:
        os.remove(audio_file)
    except Exception:
        pass

    return text, language


# ============================================================
# SAVE TRANSCRIPT
# ============================================================

def save_transcript(text, title, video_id, language, url, method):

    os.makedirs(
        OUTPUT_FOLDER,
        exist_ok=True
    )

    filename = clean_filename(title)

    output_file = os.path.join(
        OUTPUT_FOLDER,
        f"{filename}.txt"
    )

    header = f"""
YouTube Transcript
==================

Title: {title}
Video ID: {video_id}
Language: {language}
Method: {method}
Source: {url}

==================
TRANSCRIPT
==================

"""

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(header)
        file.write(text)

    return output_file


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    print("=" * 60)
    print("        YOUTUBE VIDEO -> TEXT TRANSCRIPT")
    print("=" * 60)

    print("\nPaste your YouTube URL below.\n")

    url = input("YouTube URL: ").strip()

    if not url:
        print("\nNo URL provided.")
        sys.exit(1)

    try:

        # -----------------------------------------
        # Video information
        # -----------------------------------------

        video_id = get_video_id(url)

        print("\nVideo ID:")
        print(video_id)

        print("\nGetting video title...")

        title = get_video_title(url)

        print("\nTitle:")
        print(title)

        # -----------------------------------------
        # Try YouTube captions
        # -----------------------------------------

        print("\n" + "-" * 60)

        print(
            "Trying to retrieve existing "
            "YouTube captions..."
        )

        try:

            text, language = get_youtube_captions(
                video_id
            )

            method = "YouTube captions"

            print("\nSUCCESS!")
            print("Existing captions found.")

        except Exception as caption_error:

            print("\nYouTube captions unavailable.")

            print("\nReason:")
            print(caption_error)

            print(
                "\nSwitching automatically "
                "to Whisper..."
            )

            # -----------------------------------------
            # Whisper fallback
            # -----------------------------------------

            text, language = transcribe_with_whisper(
                url,
                video_id
            )

            method = "Whisper transcription"

        # -----------------------------------------
        # Save
        # -----------------------------------------

        output_file = save_transcript(
            text=text,
            title=title,
            video_id=video_id,
            language=language,
            url=url,
            method=method,
        )

        # -----------------------------------------
        # Results
        # -----------------------------------------

        print("\n" + "=" * 60)

        print("TRANSCRIPTION COMPLETED")

        print("=" * 60)

        print("\nTitle:")
        print(title)

        print("\nLanguage:")
        print(language)

        print("\nMethod:")
        print(method)

        print("\nTranscript length:")
        print(f"{len(text):,} characters")

        print("\nSaved to:")
        print(os.path.abspath(output_file))

        print("\nPreview:")
        print("-" * 60)

        print(text[:1500])

        if len(text) > 1500:
            print("\n[...]")

        print("-" * 60)

    except KeyboardInterrupt:

        print("\n\nOperation cancelled.")

    except Exception as error:

        print("\n" + "=" * 60)

        print("ERROR")

        print("=" * 60)

        print("\n", error)

        print(
            "\nMake sure the required packages "
            "and FFmpeg are installed."
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()