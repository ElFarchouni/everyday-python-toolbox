# Everyday Python Toolbox 🧰

Small tools for everyday tasks, for people who code and for people who don't.

- 🌐 **You don't code?** Open the web app. Nothing to install, it works on a
  phone, and it is free for good:
  **<https://elfarchouni.github.io/everyday-python-toolbox/>**
- 🐍 **You code?** Every tool is a small standalone Python script: merge PDFs,
  transcribe lectures, generate stylish QR codes, and more.

## Web tools (no coding needed)

| Tool | What it does | Use it |
|------|--------------|--------|
| 🔳 QR code generator | QR codes for links, Wi-Fi, contact cards, WhatsApp… in your colors, with your logo. The codes never expire. | [Open the tool](https://elfarchouni.github.io/everyday-python-toolbox/qr/) · [Read the guide](qr_codes/README.md) |

No account, no ads, no tracking. The tools run in your own browser, so what you
type and upload never leaves your device. More tools will get a web version
over time.

## Python scripts

Each tool lives in its own folder, is fully self-contained, and starts with a
docstring explaining its requirements and usage. No framework, no setup: just
`pip install` what the tool needs and run it.

| Tool | What it does | Run |
|------|--------------|-----|
| 📄 [PDF merger](pdf_tools/merge_pdf.py) | Combine several PDFs into one | `python pdf_tools/merge_pdf.py out.pdf a.pdf b.pdf` |
| 📝 [PDF → Word](pdf_tools/pdf_to_word.py) | Convert a PDF (or a whole folder) into editable `.docx`, keeping layout, tables and images | `python pdf_tools/pdf_to_word.py report.pdf` |
| 🎓 [Article → Word](pdf_tools/article_to_word.py) | Turn a research paper into a clean, editable Word document: two columns read in order, real headings, figures/tables/equations as images, references, no headers or page numbers | `python pdf_tools/article_to_word.py paper.pdf` |
| 🎙️ [Audio/video → text](transcription/audio_video_to_text.py) | Transcribe any recording locally with Whisper (supports French & Arabic) | `python transcription/audio_video_to_text.py lecture.mp3` |
| ▶️ [YouTube → text](transcription/youtube_to_text.py) | Grab a video's captions, or transcribe its audio with Whisper if there are none | `python transcription/youtube_to_text.py` |
| 🔳 [QR code generator](qr_codes/qr_generator.py) | Interactive designer: shapes, gradients, logo, high-res PNG + SVG ([guide](qr_codes/README.md)) | `python qr_codes/qr_generator.py` |
| 🤖 [Gemini chat](ai_chat/gemini_chat.py) | Chat with Google Gemini from the terminal | `python ai_chat/gemini_chat.py` |
| 🖼️ [Image → icon](image_tools/image_to_icon.py) | Turn a PNG/JPEG/etc. into a multi-size Windows `.ico` | `python image_tools/image_to_icon.py logo.png` |

### Getting started

Python 3.9+ recommended. Install everything at once:

```bash
pip install -r requirements.txt
```

…or open the tool you want and install only what its docstring lists.

Extra notes:

- **Transcription tools** need [FFmpeg](https://ffmpeg.org/download.html) installed and on your PATH.
- **Gemini chat** needs a free API key from [Google AI Studio](https://aistudio.google.com/apikey), set as the `GEMINI_API_KEY` environment variable.

### Testing the PDF merger

```bash
python pdf_tools/samples/make_test_pdfs.py   # creates file1–3.pdf in samples/
python pdf_tools/merge_pdf.py                # merges them into samples/merged.pdf
```

## How the website works

The web app is the [`docs/`](docs/) folder: plain HTML, CSS and JavaScript,
with no framework and no build step. GitHub Pages serves it as it is
(repository **Settings → Pages → Deploy from a branch → `main` / `/docs`**).

```
docs/
├── index.html        home page: one card per tool
├── assets/           styles and icon shared by every page
└── qr/               the QR code generator
```

To try it on your computer, open `docs/index.html` in a browser. To add a web
tool, create `docs/<tool>/index.html` and add a card for it in
`docs/index.html`.

## Roadmap

New tools are added over time. Suggestions are welcome in the
[Issues](https://github.com/ElFarchouni/everyday-python-toolbox/issues) tab.

## Credits

- QR encoding in the web app: [qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator)
  by Kazuhiko Arase, MIT license.
- Toolbox icon: [Fluent Emoji](https://github.com/microsoft/fluentui-emoji)
  by Microsoft, MIT license.

## License

[MIT](LICENSE): free to use, modify, and share.
