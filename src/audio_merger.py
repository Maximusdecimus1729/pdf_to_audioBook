import logging
import numpy as np
import scipy.io.wavfile as wav
from pathlib import Path

from config import (
    CHUNKS_DIR,
    FINAL_DIR,
    FINAL_OUTPUT_FILENAME,
    PAUSE_BETWEEN_CHUNKS_MS,
    SAMPLE_RATE
)

logger = logging.getLogger(__name__)

def ensure_final_dir():
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Final output directory ready: {FINAL_DIR}")
    
def create_silence(duration_ms: int) -> np.ndarray:
    num_samples = int((duration_ms / 1000) * SAMPLE_RATE)

    return np.zeros(num_samples, dtype=np.int16)

def load_chunk(chunk_path: Path) -> np.ndarray | None:
    #does the file actually exists
    if not chunk_path.exists():
        logger.warning(f"Chunk file not found, skipping: {chunk_path}")
        return None
    try:
        sample_rate, audio_data = wav.read(str(chunk_path))

        if sample_rate != SAMPLE_RATE:
            logger.warning(
                f"Unexpected sample rate {sample_rate}Hz in {chunk_path.name}. "
                f"Expected {SAMPLE_RATE}Hz. Audio may sound distorted."
            )
        
        if audio_data.dtype != np.int16:
            logger.debug(f"Converting {chunk_path.name} from "
                         f"{audio_data.dtype} to int16")
            audio_data = audio_data.astype(np.int16)

        return audio_data
    except Exception as e:
        logger.error(f"Failed to load chunk {chunk_path.name}: {e}")
        return None
    
def get_sorted_chunk_paths(chunk_files: list[Path]) -> list[Path]:
    return sorted(chunk_files, key=lambda p: p.name)

#core merge function

def merge_chunks(chunk_files: list[Path]) -> Path:
    if not chunk_files:
        raise ValueError("No chunk files provided for merging.")
    
    ensure_final_dir()
    
    sorted_chunks = get_sorted_chunk_paths(chunk_files)
    
    logger.info(f"Merging {len(sorted_chunks)} chunks into final audiobook...")
    
    audio_segments = []
    
    silence = create_silence(PAUSE_BETWEEN_CHUNKS_MS)
    
    for i, chunk_path in enumerate(sorted_chunks):
        audio_data = load_chunk(chunk_path)
        
        if audio_data is None:
            continue

        audio_segments.append(audio_data)
        
        if i<len(sorted_chunks) - 1:
            audio_segments.append(silence)
            
        if (i + 1) % 50 == 0:
            logger.info(f"Merged {i + 1}/{len(sorted_chunks)} chunks...")
         
    if not audio_segments:
        raise ValueError("No audio segments could be loaded. "
                         "All chunk files may be corrupted or missing.")   

    logger.info("Concatenating all audio segments...")
    final_audio = np.concatenate(audio_segments, axis=0)
    
    #save the final audiobook
    
    output_path = FINAL_DIR / FINAL_OUTPUT_FILENAME

    wav.write(str(output_path), SAMPLE_RATE, final_audio)
    
    # Calculate and log the duration of the final audiobook
    duration_seconds = len(final_audio) / SAMPLE_RATE
    duration_minutes = duration_seconds / 60
    
    logger.info(
        f"Audiobook saved to: {output_path}\n"
        f"Total duration: {duration_minutes:.1f} minutes "
        f"({duration_seconds:.0f} seconds)\n"
        f"File size: {output_path.stat().st_size / (1024*1024):.1f} MB"
    )

    return output_path

def merge_all_chunks_from_dir() -> Path:

    """
    When would you use this instead of merge_chunks()?
        → If you ran tts_engine separately and already have chunk files
          sitting in output/chunks/ from a previous session
        → If you just want to re-merge without re-running Bark
        → Useful for quickly testing different pause durations
    """
    
    logger.info(f"Scanning for chunk files in: {CHUNKS_DIR}")
    
    chunk_files = list(CHUNKS_DIR.glob("*.wav"))

    if not chunk_files:
        raise FileNotFoundError(
            f"No .wav chunk files found in {CHUNKS_DIR}. "
            f"Make sure tts_engine has run first."
        )
    
    logger.info(f"Found {len(chunk_files)} chunk files.")
    return merge_chunks(chunk_files)


        



 
