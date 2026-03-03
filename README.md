# 📚 PDF Bark Reader
Convert any PDF book into a natural-sounding audiobook using
Suno's Bark AI text-to-speech model.

---

## 🧠 How It Works
```
PDF File
  → Extract text page by page        (PyMuPDF)
  → Split into sentences              (NLTK)
  → Break into Bark-safe chunks       (text_processor)
  → Convert each chunk to audio       (Bark TTS)
  → Merge all chunks into one file    (scipy + numpy)
  → audiobook.wav ✅
```

---

## 📁 Project Structure
```
pdf-bark-reader/
├── main.py                  # Entry point — runs the full pipeline
├── config.py                # All settings live here (voice, paths, device)
├── requirements.txt         # Python dependencies
├── .env                     # Your personal machine settings (GPU/CPU)
├── README.md                # This file
│
├── input/                   # Drop your PDF books here
├── output/
│   ├── chunks/              # Individual sentence .wav files
│   ├── final/               # Final merged audiobook.wav
│   └── progress.json        # Auto-saved progress tracker
├── models/                  # Bark model weights cached here
├── logs/                    # run.log lives here
└── src/
    ├── pdf_extractor.py     # Opens PDF, extracts and cleans text
    ├── text_processor.py    # Splits text into Bark-safe chunks
    ├── progress_tracker.py  # Saves/resumes progress to JSON
    ├── tts_engine.py        # Loads Bark, generates audio chunks
    └── audio_merger.py      # Merges chunks into final audiobook
```

---

## ⚙️ Requirements

- Python 3.10
- Anaconda (recommended)
- NVIDIA GPU (recommended — CPU works but is very slow)
- ~3GB disk space for Bark model weights (downloaded automatically)

---

## 🚀 Setup & Installation

### Step 1 — Clone or download the project
```bash
cd path/to/where/you/want/it
```

### Step 2 — Create and activate Conda environment
```bash
conda create -n pdf-bark-reader python=3.10
conda activate pdf-bark-reader
```

### Step 3 — Install PyTorch (do this BEFORE requirements.txt)

**If you have an NVIDIA GPU:**
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

**If you have no GPU (CPU only):**
```bash
pip install torch torchvision torchaudio
```

### Step 4 — Install all other dependencies
```bash
pip install -r requirements.txt
```

### Step 5 — Download NLTK tokenizer data (one time only)
```bash
python -c "import nltk; nltk.download('punkt_tab')"
```

### Step 6 — Configure your .env file
Open `.env` and set your device:
```
DEVICE=cuda   # if you have NVIDIA GPU
DEVICE=cpu    # if you have no GPU
```

---

## 📖 Usage

### Basic run (uses input/book.pdf by default)
```bash
python main.py
```

### Specify a PDF file
```bash
python main.py --pdf input/mybook.pdf
```

### Use a different voice
```bash
python main.py --pdf input/mybook.pdf --voice v2/en_speaker_3
```

### Reset progress and start fresh
```bash
python main.py --pdf input/mybook.pdf --reset
```

### Re-merge existing chunks without re-running Bark
```bash
python main.py --merge-only
```

### See all options
```bash
python main.py --help
```

---

## 🎙️ Available Voices

Change the voice in `config.py` or via `--voice` flag.

| Preset | Style |
|--------|-------|
| `v2/en_speaker_0` | Male, deep |
| `v2/en_speaker_1` | Male, neutral |
| `v2/en_speaker_2` | Male, clear |
| `v2/en_speaker_3` | Male, expressive |
| `v2/en_speaker_4` | Male, soft |
| `v2/en_speaker_5` | Female, neutral |
| `v2/en_speaker_6` | Male, natural ← default |
| `v2/en_speaker_7` | Female, clear |
| `v2/en_speaker_8` | Female, expressive |
| `v2/en_speaker_9` | Female, soft |

---

## ⚡ Performance Expectations

| Hardware | Per Chunk | 500 Chunk Book |
|----------|-----------|----------------|
| NVIDIA RTX 3080 | ~3-5 sec | ~45 min |
| NVIDIA GTX 1660 | ~8-12 sec | ~90 min |
| CPU only | ~60-120 sec | ~12-24 hours |

> **Tip:** Always use GPU if possible. CPU processing a full
> book overnight is doable but not fun.

---

## 🔁 Resume After Interruption

If the process is interrupted (Ctrl+C, crash, power cut):
```bash
# Just run the exact same command again
python main.py --pdf input/mybook.pdf
```

Progress is saved after every single chunk. You will
automatically resume from where you left off.

To start completely fresh instead:
```bash
python main.py --pdf input/mybook.pdf --reset
```

---

## 🔧 Configuration Reference

All settings are in `config.py`:

| Setting | Default | Description |
|---------|---------|-------------|
| `BARK_VOICE_PRESET` | `v2/en_speaker_6` | Voice to use |
| `USE_SMALL_MODELS` | `True` | Faster but slightly lower quality |
| `MAX_CHUNK_CHARS` | `180` | Max characters per Bark chunk |
| `MIN_CHUNK_CHARS` | `10` | Skip chunks shorter than this |
| `PAUSE_BETWEEN_CHUNKS_MS` | `400` | Silence between sentences (ms) |
| `RESUME_ENABLED` | `True` | Auto-resume on restart |
| `SAMPLE_RATE` | `24000` | Bark's audio sample rate (do not change) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

---

## ⚠️ Known Limitations

**Scanned PDFs won't work**
Scanned books are images of text — not real text.
PyMuPDF can only read real embedded text.
Solution: Run the PDF through an OCR tool first
(e.g. Adobe Acrobat, Tesseract OCR).

**Bark can sound inconsistent**
Bark is non-deterministic — the same text can sound
slightly different each run. This is normal behavior.

**Very long books take a long time**
A 500-page book = ~800 chunks = several hours even on GPU.
The progress tracker handles this — just let it run overnight.

**Non-English text**
Bark supports multiple languages but quality varies.
English gives the best results by far.

---

## 🐛 Troubleshooting

**"PDF file not found"**
→ Make sure your PDF is inside the `input/` folder
→ Check the filename spelling matches exactly

**"No text chunks were produced"**
→ Your PDF is likely scanned/image-based
→ Run it through OCR first

**"CUDA out of memory"**
→ Set `USE_SMALL_MODELS = True` in config.py
→ Or set `DEVICE=cpu` in .env (slower but uses RAM not VRAM)

**Audio sounds garbled or cuts off**
→ A chunk likely exceeded Bark's token limit
→ Try reducing `MAX_CHUNK_CHARS` to `150` in config.py

**Installation errors with Bark**
→ Make sure PyTorch was installed BEFORE requirements.txt
→ Confirm Python version is exactly 3.10

---



---

## 🙏 Credits
- [Suno Bark](https://github.com/suno-ai/bark) — TTS model
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF text extraction
- [NLTK](https://www.nltk.org/) — Sentence tokenization



