
import os
import logging
import numpy as np
import scipy.io.wavfile as wav
from pathlib import Path

from bark import generate_audio, preload_models
from bark.generation import (
    generate_text_semantic,
    preload_models as preload_generation_models
)

from config import (
    BARK_VOICE_PRESET,
    CHUNKS_DIR,
    DEVICE,
    SAMPLE_RATE,
    USE_SMALL_MODELS,
    CPU_OFFLOAD
)

os.environ["SUNO_USE_SMALL_MODELS"] = "1" if USE_SMALL_MODELS else "0"
os.environ["SUNO_OFFLOAD_CPU"]      = "1" if CPU_OFFLOAD else "0"

# ── Patch torch.load so Bark checkpoints load without weights_only errors ──
import torch
import numpy as np

_original_torch_load = torch.load

def _patched_torch_load(*args, **kwargs):
    kwargs.setdefault("weights_only", False)
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load


from bark import generate_audio, preload_models

logger = logging.getLogger(__name__)

_models_loaded = False

def load_models():
    global _models_loaded

    if _models_loaded:
        logger.info("Bark models already loaded. Skipping.")
        return
    
    logger.info(f"Loading Bark models on device: {DEVICE}")
    logger.info(f"Using small models: {USE_SMALL_MODELS}")
    logger.info("This may take 10-30 seconds on first run...")
    
   
    #   1. Text model   → understands the meaning of words
    #   2. Coarse model → generates rough sound structure
    #   3. Fine model   → refines the sound into natural audio
    preload_models()
    
    _models_loaded = True
    logger.info("Bark models loaded successfully.")
    
def ensure_chunks_dir():
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Chunks directory ready: {CHUNKS_DIR}")
    
def get_chunk_path(chunk_index: int) -> Path:
    filename = f"chunk_{chunk_index:04d}.wav" #saving wav as "chunk_0001, chunk_0002, chunk_0010"
    return CHUNKS_DIR / filename

def generate_audio_chunk(text: str, chunk_index: int) -> Path:
    #make sure models are loaded first
    if not _models_loaded:
        raise RuntimeError(
            "Bark models are not loaded. Call load_models() before "
            "calling generate_audio_chunk()."
        )
    
    output_path = get_chunk_path(chunk_index)
    
    logger.debug(f"Generating audio for chunk {chunk_index}: '{text[:50]}...'")
    
    #BARK's voice preset
    
    audio_array = generate_audio(
        text,
        history_prompt=BARK_VOICE_PRESET
    )
    
    audio_int16 = (audio_array * 32767).astype(np.int16)
    wav.write(str(output_path), SAMPLE_RATE, audio_int16)

    logger.debug(f"Chunk {chunk_index} saved to {output_path}")
    return output_path

def process_chunks(chunks: list[str], tracker) -> list[Path]:
    ensure_chunks_dir()
    
    generated_files = []
    total = len(chunks)
    
    logger.info(f"Starting TTS generation for {total} chunks...")
    
    for index, text in enumerate(chunks):
        if tracker.is_complete(index):
            logger.debug(f"Chunk {index} already done. Skipping.")
            generated_files.append(get_chunk_path(index))
            continue   
        
        if index % 10 == 0:
            summary = tracker.get_summary()
            logger.info(
                f"Progress: {summary['completed']}/{total} chunks done "
                f"({summary['percent']}%)"
            )
            
        try:
            output_path = generate_audio_chunk(text, index)
            tracker.mark_complete(index)
            generated_files.append(output_path)

        except Exception as e:
            logger.error(f"Chunk {index} failed: {e}")
            tracker.mark_failed(index)
            
    summary = tracker.get_summary()
    logger.info(
        f"TTS generation complete. "
        f"Success: {summary['completed']} | "
        f"Failed: {summary['failed']} | "
        f"Total: {total}"
    )
    
    return generated_files

