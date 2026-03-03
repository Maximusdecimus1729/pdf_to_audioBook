import re
import logging
import nltk

from config import MAX_CHUNK_CHARS, MIN_CHUNK_CHARS

logger = logging.getLogger(__name__)

def ensure_nltk_data():
    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        logger.info("Downloading NLTK punkt_tab tokenizer data...")
        nltk.download('punkt_tab', quiet=True)
        logger.info("NLTK data downloaded successfully.")
        
def pages_to_sentences(pages: list[str]) -> list[str]:
    
    ensure_nltk_data()
    
    all_sentences = []
    
    for page_number, page_text in enumerate(pages):
        
        if not page_text.strip():
            continue

        sentences = nltk.sent_tokenize(page_text)

        logger.debug(f"Page {page_number + 1}: "
                     f"{len(sentences)} sentences found")

        all_sentences.extend(sentences)
        
    logger.info(f"Total sentences extracted: {len(all_sentences)}")
    return all_sentences

def sentences_to_chunks(sentences: list[str]) -> list[str]:
    
    chunks = []
    
    for sentence in sentences:
        
        sentence = sentence.strip()
        
        if len(sentence) < MIN_CHUNK_CHARS:
            logger.debug(f"Skipping short chunk: '{sentence}'") 
            continue

        if len(sentence) <= MAX_CHUNK_CHARS:
            chunks.append(sentence)

        else:
            # Sentence is too long — we need to split it
            sub_chunks = split_long_sentence(sentence)
            chunks.extend(sub_chunks)

    logger.info(f"Total chunks ready for TTS: {len(chunks)}")
    return chunks

def split_long_sentence(sentence: str) -> list[str]:
    
    parts = re.split(r'(?<=[,;:])\s+', sentence)
    
    result = []
    current_chunk = ""
    
    for part in parts:
        if len(current_chunk) + len(part) + 1 <= MAX_CHUNK_CHARS:
            current_chunk = (current_chunk + " "+ part).strip()
        else:
            if current_chunk:
                result.append(current_chunk)
            current_chunk = part
    
    if current_chunk:
        result.append(current_chunk)

    final_result = []
    for chunk in result:
        if len(chunk) > MAX_CHUNK_CHARS:
            word_chunks = force_split_at_words(chunk)
            final_result.extend(word_chunks)
        else:
            final_result.append(chunk)

    return final_result

def force_split_at_words(text: str) -> list[str]:
    
    words = text.split()
    chunks = []
    current = ""
    
    for word in words:
        test = (current + " " + word).strip()

        if len(test) <= MAX_CHUNK_CHARS:
            current = test
        else:
            if current:
                chunks.append(current)
            current = word
            
    if current:
            chunks.append(current)
            
    return chunks
    
def process_pages(pages: list[str]) -> list[str]:
    
    """
    Pipeline:
        pages (list of page strings)
            ↓ pages_to_sentences()
        flat list of sentences
            ↓ sentences_to_chunks()
        list of Bark-safe chunks 
        
    """
    
    logger.info("Starting text processing pipeline...")

    sentences = pages_to_sentences(pages)
    chunks = sentences_to_chunks(sentences)
    
    logger.info(f"Text processing complete. {len(chunks)} chunks ready.")
    return chunks
    
    