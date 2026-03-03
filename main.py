import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

#import our modules
from src.pdf_extractor  import setup_logging, extract_text_from_pdf, get_pdf_metadata
from src.text_processor import process_pages
from src.progress_tracker import ProgressTracker
from src.tts_engine     import load_models, process_chunks
from src.audio_merger   import merge_chunks, merge_all_chunks_from_dir

from config import (
    DEFAULT_PDF,
    BARK_VOICE_PRESET,
    RESUME_ENABLED,
    CHUNKS_DIR
)

logger = logging.getLogger(__name__)

def parse_arguments():
    """
    Parses command line arguments so we can customize
    the run without editing any code or config files.
    
    To run the project:
    python main.py
    python main.py --pdf input/mybook.pdf
    python main.py --pdf input/mybook.pdf --voice v2/en_speaker_3
    python main.py --merge-only    #to merge whatever the chunks you have made
    python main.py --pdf input/book.pdf --reset
    
    """
    
    parser = argparse.ArgumentParser(
        description = "PDF to Audiobook using TTS",
        
        #this is shown when we type --help
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            "  python main.py --pdf input/mybook.pdf\n"
            "  python main.py --pdf input/mybook.pdf --voice v2/en_speaker_3\n"
            "  python main.py --merge-only\n"
            "  python main.py --reset\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter

    )
    
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Path to the PDF file (default: {DEFAULT_PDF})"
    )
    
    parser.add_argument(
        "--voice",
        type=str,
        default=BARK_VOICE_PRESET,  # falls back to config value if not provided
        help=f"Bark voice preset (default: {BARK_VOICE_PRESET})"
    )
    
    parser.add_argument(
        "--merge-only",
        action="store_true",        # flag — True if present, False if absent
        help="Skip TTS generation and only merge existing chunk files"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset progress tracker and start fresh from chunk 0"
    )
    
    return parser.parse_args()

#pipeline stages

def stage_extract(pdf_path: Path) -> tuple[list[str], dict]:
    logger.info("Extracting text from PDF...")
    
    metadata = get_pdf_metadata(pdf_path)
    logger.info(f"Title:  {metadata['title']}")
    logger.info(f"Author: {metadata['author']}")
    logger.info(f"Pages:  {metadata['pages']}")
    
    pages = extract_text_from_pdf(pdf_path)
    
    logger.info(f"Extraction complete: {len(pages)} pages with text.")
    return pages, metadata

def stage_process(pages: list[str]) -> list[str]:
    logger.info("Processing text into chunks...")
    
    chunks = process_pages(pages)

    logger.info(f"Processing complete: {len(chunks)} chunks ready for TTS.")
    return chunks

def stage_tts(chunks: list[str], pdf_name: str) -> list[Path]:
    logger.info("Generating audio...have patience!")

    load_models()
    
    tracker = ProgressTracker(
        pdf_name = pdf_name,
        total_chunks = len(chunks)
    )
    
    #handle --reset flag | We wipe all saved progress and start fresh

    if "--reset" in sys.argv:
        logger.info("Reset flag detected. Wiping saved progress...")
        tracker.reset()
    
    #resume status
    summary = tracker.get_summary()
    if summary['completed'] > 0:
        logger.info(
            f"Resuming from previous run: "
            f"{summary['completed']}/{summary['total']} chunks already done."
        )
    else:
        logger.info("Starting fresh TTS generation.")
        
    generated_files = process_chunks(chunks, tracker)
    
    summary = tracker.get_summary()
    logger.info(
        f"TTS complete: {summary['completed']} succeeded, "
        f"{summary['failed']} failed."
    )
    
    if summary['failed'] > 0:
        logger.warning(
            f"{summary['failed']} chunks failed to generate. "
            f"The audiobook will have small gaps where these chunks would be. "
            f"Check run.log for details on which chunks failed."
        )
        
    return generated_files

def stage_merge(generated_files: list[Path]) -> Path:
    logger.info("Merging chunks into final audiobook...")

    final_path = merge_chunks(generated_files)
    
    logger.info(f"Audiobook saved to: {final_path}")
    return final_path

#main function

def main():
    start_time = datetime.now()

    args = parse_arguments()

    setup_logging()

    logger.info(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")   

    if args.merge_only:
        logger.info("--merge-only flag detected. Skipping TTS generation.")
        final_path = merge_all_chunks_from_dir()
        logger.info(f"Done! Audiobook saved to: {final_path}")
        return

    if not args.pdf.exists():
        logger.error(f"PDF file not found: {args.pdf}")
        logger.error("Please check the path and try again.")
        logger.error(f"Example: python main.py --pdf input/mybook.pdf")
        sys.exit(1)

    logger.info(f"PDF:   {args.pdf}")
    logger.info(f"Voice: {args.voice}")
    logger.info(f"Resume enabled: {RESUME_ENABLED}")

    #run the pipeline
    try:
        pages, metadata = stage_extract(args.pdf)
        
        chunks = stage_process(pages)
        
        if not chunks:
            logger.error(
                "No text chunks were produced from the PDF. "
                "The PDF may be image-based (scanned) and require OCR, "
                "or it may be empty/corrupted."
            )
            sys.exit(1)  
            
        pdf_name = args.pdf.name
        generated_files = stage_tts(chunks, pdf_name) 
            
        if not generated_files:
            logger.error(
                "No audio files were generated."
                "Check run.log for erros from Bark."
            )
            sys.exit(1)
            
        final_path = stage_merge(generated_files)
        
        #completed
        end_time   = datetime.now()
        duration   = end_time - start_time
        hours      = int(duration.total_seconds() // 3600)
        minutes    = int((duration.total_seconds() % 3600) // 60)
        seconds    = int(duration.total_seconds() % 60)
        
        logger.info("")
        logger.info("AUDIOBOOK COMPLETE!")
        logger.info("")
        logger.info(f"  PDF:       {args.pdf.name}")
        logger.info(f"  Voice:     {args.voice}")
        logger.info(f"  Chunks:    {len(chunks)} total")
        logger.info(f"  Output:    {final_path}")
        logger.info(f"  Duration:  {hours}h {minutes}m {seconds}s")

    except KeyboardInterrupt:
        logger.info("  Run interrupted")
        logger.info("  Progress has been saved automatically.")
        logger.info("  Run again to resume.")    
        
    except Exception as e:
        logger.error(f"Unexpected err occured...benchod: {e}") 
        logger.error("  Check logs/run.log for full details.")
        raise

#main entry point

if __name__ == "__main__":
    main()
        
        