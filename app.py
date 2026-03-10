import os
import json
import time
import queue
import shutil
import logging
import subprocess
import threading
from pathlib  import Path
from datetime import datetime

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    Response,
    send_file
)

from dotenv import load_dotenv

#load .env file
load_dotenv()

#pipeline module import
from src.pdf_extractor   import setup_logging, extract_text_from_pdf, get_pdf_metadata
from src.text_processor  import process_pages
from src.progress_tracker import ProgressTracker
from src.tts_engine      import load_models, process_chunks
from src.audio_merger    import merge_chunks, merge_all_chunks_from_dir

#import config variables
from config import (
   INPUT_DIR,
    CHUNKS_DIR,
    FINAL_DIR,
    FINAL_OUTPUT_FILENAME,
    BARK_VOICE_PRESET,
    RESUME_ENABLED,
    PROGRESS_FILE
)

#setup

app = Flask(__name__)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
setup_logging()

logger = logging.getLogger(__name__)

#global state

progress_queue = queue.Queue()

is_running = False
stop_event = threading.Event()

last_result = {
    "status": "idle",
    "output_path": None,
    "error": None
}

#sending progress updates to the frontend via SSE
def send_progress(message: str, percent: int = None, eta: str = None, status: str = None):
    update = {
        "message": message,
        "percent": percent,
        "eta": eta,
        "status": status,
        "time": datetime.now().strftime("%H:%M:%S")
    }
    
    
    progress_queue.put(json.dumps(update))
    logger.info(f"[UI] {message}")
    
#eta calculation

def calculate_eta(completed: int, total: int, start_time: float) -> str:
    if completed < 3:
        return "Calculating..."
    
    elapsed = time.time() - start_time
    per_chunk = elapsed / completed
    remaining = (total - completed) * per_chunk
     
    if remaining < 60:
        return f"~{int(remaining)} seconds remaining"
    elif remaining < 3600:
        minutes = int(remaining / 60)
        return f"~{minutes} minutes remaining"
    else:
        hours   = int(remaining / 3600)
        minutes = int((remaining % 3600) / 60)
        return f"~{hours}h {minutes}m remaining"


#pipeline thread

def run_pipeline(pdf_path: Path, voice: str, reset: bool):
    
    global is_running, last_result

    is_running = True
    stop_event.clear()
    last_result = {
        "status": "running",
        "output_path": None,
        "error": None
    }
    
    try:
        #extract
        send_progress("Extracting text from PDF...", percent =5)

        metadata = get_pdf_metadata(pdf_path)
        
        send_progress(
            f"Found: '{metadata['title']}' — {metadata['pages']} pages",
            percent=8
        )
        
        pages = extract_text_from_pdf(pdf_path)
        send_progress(
            f" Extracted text from {len(pages)} pages.",
            percent=12
        )
        
        #process
        send_progress("Processing text into chunks...", percent=15)
        chunks = process_pages(pages)   
        
        total_chunks = len(chunks)
        send_progress(f"Processed text into {total_chunks} chunks.", percent=20)

        if not chunks:
            send_progress(
                "No text found. PDF may be image-based and require OCR.",
                status="error"
            )
            return 
            
        #TTS
        send_progress("Loading Bark AI Model...", percent=22)
        
        import src.tts_engine as tts_module
        original_voice = tts_module.BARK_VOICE_PRESET
        
         #monkey patching
        import bark
        original_generate = tts_module.generate_audio 
        
        def generate_with_voice(text, history_prompt=None):
            return bark.generate_audio(text, history_prompt=voice)

        tts_module.generate_audio = generate_with_voice
        
        #loading model
        load_models()
        send_progress("Model loaded. Generating audio...", percent=30)
        
        #rpogress tracker
        tracker = ProgressTracker(
            pdf_name = pdf_path.name,
            total_chunks = total_chunks,
        )
        
        if reset:
            tracker.reset()
            send_progress("Progress reset. Starting from chunk 0.", percent=25)

        elif tracker.get_summary()['completed'] > 0:
            done = tracker.get_summary()['completed']
            send_progress(
                f"Resuming from chunk {done}/{total_chunks}...",
                percent=25
            )

        #chunk woth live progress
        CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
        
        generated_files = []
        tts_start_time = time.time()
        
        for index, text in enumerate(chunks):
            if stop_event.is_set():
                break

            if tracker.is_complete(index):
                chunk_path = CHUNKS_DIR / f"chunk_{index:04d}.wav"
                generated_files.append(chunk_path)
                continue
            
            try:
                from src.tts_engine import generate_audio_chunk
                output_path = generate_audio_chunk(text, index)
                tracker.mark_complete(index)
                generated_files.append(output_path)
            except Exception as e:
                logger.error(f"Chunk {index} failed: {e}")
                tracker.mark_failed(index)
                continue        
                
            # Calculate progress
            completed = len(tracker.completed_chunks)
            percent   = 25 + int((completed / total_chunks) * 60)
            
            eta = calculate_eta(completed, total_chunks, tts_start_time)
            
            send_progress(
                f" Generating chunk {completed}/{total_chunks}...",
                percent=percent,
                eta=eta
            )
            
        tts_module.generate_audio = original_generate

        if stop_event.is_set():
            last_result = {"status": "stopped", "output_path": None, "error": None}
            send_progress("Generation stopped by user.", status="stopped")
            return

        summary = tracker.get_summary()
        send_progress(
            f"Audio generation complete. "
            f"{summary['completed']} succeeded, {summary['failed']} failed.",
            percent=87
        )
        
        #merge
        
        send_progress("Merging audio chunks...", percent=90)
        
        final_path = merge_chunks(generated_files)
        
        #final Audio Book generation
        import numpy as np
        import scipy.io.wavfile as wav_reader
        sample_rate, audio_data = wav_reader.read(str(final_path))
        duration_seconds = len(audio_data) / sample_rate
        duration_minutes = int(duration_seconds / 60)
        
        last_result = {
            "status":      "complete",
            "output_path": str(final_path),
            "error":       None
        }

        send_progress(
            f"Audiobook complete! Duration: {duration_minutes} minutes.",
            percent=100,
            eta="Done!",
            status="complete"
        )
        
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        last_result = {"status": "error", "output_path": None, "error": str(e)}
        send_progress(
            f"Error: {str(e)}. Check logs/run.log for details.",
            status="error"
        )

    finally:
        #release the running lock when done
        is_running = False
        stop_event.clear()
        
        
#Routes

@app.route("/")
def index():
    return render_template("index.html", default_voice=BARK_VOICE_PRESET)
    
@app.route("/upload", methods=["POST"])
def upload():
    global is_running
    
    if is_running:
        return jsonify({
            "success": False,
            "error": "Have patience! The current book is still being processed. You can check the progress on the homepage."
        }), 409 
        
    if "pdf" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400 
    
    file = request.files["pdf"]
    
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400
        
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"success": False, "error": "File must be a PDF."}), 400

    #save the uploaded pdf
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = INPUT_DIR / file.filename
    file.save(str(pdf_path))
    logger.info(f"PDF uploaded: {pdf_path}")
    
    #read the users selected voice preset
    voice_preset = request.form.get("voice", BARK_VOICE_PRESET)
    reset = request.form.get("reset", "false").lower() == "true" #

        #start the pipeline in a separate thread
        
    # daemon=True means the thread dies automatically if Flask shuts down
    thread = threading.Thread(
        target=run_pipeline,
        args=(pdf_path, voice_preset, reset),
        daemon=True
    )
    thread.start()
    
    return jsonify({"success": True, "filename": file.filename})
    
@app.route("/stream")
def stream():

    def event_stream():
        while True:
            try:
                update = progress_queue.get(timeout=30) 
                yield f"data: {update}\n\n"

                parsed = json.loads(update)
                if parsed.get("status") in ("complete", "error", "stopped"):
                    break
                
            except queue.Empty:
                yield "data: {\"type\": \"heartbeat\"}\n\n" #kkeps the connection alive

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers ={
            # Disable caching, SSE must always be fresh
            "Cache-Control": "no-cache",
            # Keep connection open
            "X-Accel-Buffering": "no"
        }
    )
    
@app.route("/status")
def status():
    return jsonify({
        "is_running": is_running,
        "last_result": last_result
    })

@app.route("/download")
def download():
    #Only available after a successful pipeline run.
    if last_result["status"] != "complete":
        return jsonify({"error": "No audiobook available yet."}), 404
        
    output_path = Path(last_result["output_path"])

    if not output_path.exists():
        return jsonify({"error": "Audiobook file not found on disk."}), 404
        
    return send_file(
        str(output_path),
        as_attachment=True,
        download_name="audiobook.wav",
        mimetype="audio/wav"
    )
    
@app.route("/merge", methods=["POST"])
def merge_only():
    #allows merging of chunks without re-running the entire pipeline

    global is_running
    
    if is_running:
        return jsonify({
            "success": False,
            "error": "Cannot merge while another job is running."
        }), 409
        
    def run_merge():
        global is_running, last_result
        
        is_running = True
        last_result = {"status": "running", "output_path": None, "error": None}
        
        try:
            send_progress("Merging existing audio chunks...", percent=10)
            final_path = merge_all_chunks_from_dir()
            
            last_result = {
                "status": "complete",
                "output_path": str(final_path),
                "error": None
            }
            
            send_progress("Merge complete!", percent=100, status="complete")
            
        except Exception as e:
            logger.error(f"Merge error: {e}", exc_info=True)
            last_result = {"status": "error", "output_path": None, "error": str(e)}
            send_progress(
                f"Error during merge: {str(e)}",
                status="error"
            )
            
        finally:
            is_running = False
            
    threading.Thread(target=run_merge, daemon=True).start()
    return jsonify({"success": True})

@app.route("/stop", methods=["POST"])
def stop():
    stop_event.set()
    return jsonify({"success": True})

@app.route("/clear", methods=["POST"])
def clear_output():
    global is_running
    if is_running:
        return jsonify({"success": False, "error": "Cannot clear while a job is running."}), 409

    # Delete all chunk wav files
    if CHUNKS_DIR.exists():
        for f in CHUNKS_DIR.glob("*.wav"):
            f.unlink()

    # Delete final output wav files
    if FINAL_DIR.exists():
        for f in FINAL_DIR.glob("*.wav"):
            f.unlink()

    # Delete progress file
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()

    return jsonify({"success": True})

@app.route("/gpu_stats")
def gpu_stats():
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits"
            ],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return jsonify({"available": False})

        line = result.stdout.strip().split("\n")[0]
        parts = [p.strip() for p in line.split(",")]
        name, temp, util, mem_used, mem_total = parts

        return jsonify({
            "available":    True,
            "name":         name,
            "temperature":  int(temp),
            "utilization":  int(util),
            "memory_used":  int(mem_used),
            "memory_total": int(mem_total)
        })
    except Exception:
        return jsonify({"available": False})


#final entry point
if __name__ == "__main__":
    
    print("Go to http://localhost:5000")
    
    app.run(
        host="0.0.0.0",    # accessible on local network too
        port=5000,
        debug=False,
        threaded=True
    )
    
    