import json
import logging
from pathlib import Path
from datetime import datetime

from config import PROGRESS_FILE, RESUME_ENABLED

logger = logging.getLogger(__name__)


class ProgressTracker:
    def __init__(self, pdf_name: str, total_chunks: int):
        self.pdf_name = pdf_name
        self.total_chunks = total_chunks  
        
        self.completed_chunks: set[int] = set()
        self.failed_chunks:    set[int] = set()
        
        self.started_at   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_updated = self.started_at 
        
        if RESUME_ENABLED:
            self._load()
  
    #Public methods
            
    def is_complete(self, chunk_index: int) -> bool:
        return chunk_index in self.completed_chunks
    
    def mark_complete(self, chunk_index: int):
        self.completed_chunks.add(chunk_index)
        self.failed_chunks.discard(chunk_index)
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        
        logger.debug(f"Chunk {chunk_index} marked complete. "
                     f"({len(self.completed_chunks)}/{self.total_chunks} done)")
        
    def mark_failed(self, chunk_index: int):
        self.failed_chunks.add(chunk_index)
        self.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        logger.warning(f"Chunk {chunk_index} marked as failed.")
        
    def get_remaining(self) -> list[int]:
        all_indexes = set(range(self.total_chunks))
        remaining = all_indexes - self.completed_chunks - self.failed_chunks
        return sorted(remaining)
    
    def get_summary(self) -> dict:
        completed = len(self.completed_chunks)
        failed    = len(self.failed_chunks)
        remaining = self.total_chunks - completed - failed
        percent   = (completed / self.total_chunks * 100) if self.total_chunks > 0 else 0
        
        return {
            "pdf_name":  self.pdf_name,
            "total":     self.total_chunks,
            "completed": completed,
            "failed":    failed,
            "remaining": remaining,
            "percent":   round(percent, 1),
            "started_at":    self.started_at,
            "last_updated":  self.last_updated
        }
        
    def reset(self):
        self.completed_chunks = set()
        self.failed_chunks    = set()
        self.started_at       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.last_updated     = self.started_at
        
        if PROGRESS_FILE.exists():
            PROGRESS_FILE.unlink()   # unlink() is Python's way of deleting a file
            logger.info("Progress file deleted. Starting fresh.")
            
    #Private Methods
    
    def _save(self):
        PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "pdf_name":        self.pdf_name,
            "total_chunks":    self.total_chunks,
            "completed_chunks": sorted(list(self.completed_chunks)),
            "failed_chunks":    sorted(list(self.failed_chunks)),
            "started_at":      self.started_at,
            "last_updated":    self.last_updated
        }
        
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def _load(self):
        if not PROGRESS_FILE.exists():
            logger.info("No existing progress found. Starting fresh.")
            return
        
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Safety check: is this progress for the SAME PDF?
            if data.get("pdf_name") != self.pdf_name:
                logger.warning(
                    f"Progress file is for '{data.get('pdf_name')}' "
                    f"but current PDF is '{self.pdf_name}'. "
                    f"Ignoring saved progress and starting fresh."
                )
                return
            self.completed_chunks = set(data.get("completed_chunks", []))
            self.failed_chunks    = set(data.get("failed_chunks", []))
            self.started_at       = data.get("started_at", self.started_at)
            
            logger.info(
                f"Resuming from saved progress: "
                f"{len(self.completed_chunks)}/{self.total_chunks} chunks already done."
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Could not read progress file: {e}. Starting fresh.")
