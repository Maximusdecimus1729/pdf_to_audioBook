import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

INPUT_DIR   = BASE_DIR / "input"           # Where you put your PDF book
CHUNKS_DIR  = BASE_DIR / "output" / "chunks"  # One .wav file per sentence
FINAL_DIR   = BASE_DIR / "output" / "final"   
LOG_FILE    = BASE_DIR / "logs" / "run.log" 

DEFAULT_PDF = INPUT_DIR / "book.pdf"

BARK_VOICE_PRESET = "v2/en_speaker_6"

DEVICE = os.getenv("DEVICE", "cpu") #change this for GPU 

USE_SMALL_MODELS = True # use complete model cause i've GPU!!!
CPU_OFFLOAD = True

MAX_CHUNK_CHARS = 180

MIN_CHUNK_CHARS = 10

RESUME_ENABLED = True

PROGRESS_FILE = BASE_DIR / "output" / "progress.json"

SAMPLE_RATE = 24000 # 24k Hz fixed for this model

PAUSE_BETWEEN_CHUNKS_MS = 400

FINAL_OUTPUT_FILENAME = "audiobook.wav"

LOG_LEVEL = "INFO"

LOG_TO_CONSOLE = True

# Nice Thing it is: his means if you ever want to change a folder name, 
# a voice, or a setting — you only change it in one place, and it updates everywhere automatically.
