import os
import logging
import aiohttp
import cohere
from pytubefix import YouTube
from pytubefix.cli import on_progress
from deepgram import Deepgram
from dotenv import load_dotenv
from collections import Counter
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import json
import base64
from datetime import datetime, timedelta
import asyncio
from functools import lru_cache
from gtts import gTTS
import hashlib
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
import nltk
from collections import Counter
import urllib.request

# Load environment variables
load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

# Initialize clients
co = cohere.ClientV2(cohere_api_key)
youtube = build("youtube", "v3", developerKey=youtube_api_key)

# Constants - these will be overridden by app.py
# Keep them as fallbacks for direct module usage
EXPORTS_DIR = "exports"
DOWNLOADS_DIR = "downloads"
CAPTIONS_DIR = "captions"
CLEANUP_THRESHOLD = timedelta(hours=24)  # Clean files older than 24 hours

# Function to set directories from app.py
def set_directories(exports_dir, downloads_dir, captions_dir):
    global EXPORTS_DIR, DOWNLOADS_DIR, CAPTIONS_DIR
    EXPORTS_DIR = exports_dir
    DOWNLOADS_DIR = downloads_dir
    CAPTIONS_DIR = captions_dir
    
    # Ensure directories exist
    for directory in [EXPORTS_DIR, DOWNLOADS_DIR, CAPTIONS_DIR]:
        ensure_directory(directory)
    
    # Log the directory paths
    logging.info(f"Set EXPORTS_DIR to: {EXPORTS_DIR}")
    logging.info(f"Set DOWNLOADS_DIR to: {DOWNLOADS_DIR}")
    logging.info(f"Set CAPTIONS_DIR to: {CAPTIONS_DIR}")


@lru_cache(maxsize=128)
def on_download_progress(stream, chunk, bytes_remaining):
    """Callback function to monitor download progress."""
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = (bytes_downloaded / total_size) * 100
    logging.debug(f"Download Progress: {percentage:.1f}%")


def ensure_directory(directory):
    """Ensure a directory exists and create it if it doesn't."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")


def cleanup_old_files(directory, threshold=CLEANUP_THRESHOLD):
    """Clean up files older than the threshold in the specified directory."""
    ensure_directory(directory)  # Make sure the directory exists
    current_time = datetime.now()

    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))

        if current_time - file_modified > threshold:
            try:
                os.remove(file_path)
                logging.info(f"Cleaned up old file: {file_path}")
            except Exception as e:
                logging.error(f"Error cleaning up file {file_path}: {e}")


def get_youtube_player_data(video_url):
    """Get YouTube video data using the API."""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}

        request = youtube.videos().list(part="player,contentDetails", id=video_id)
        response = request.execute()

        if not response["items"]:
            return {"error": "Video not found"}

        return {
            "video_id": video_id,
            "embed_html": response["items"][0]["player"]["embedHtml"],
            "duration": response["items"][0]["contentDetails"]["duration"],
        }
    except Exception as e:
        logging.error(f"Error fetching YouTube data: {e}")
        return {"error": str(e)}


def extract_video_id(url):
    """Extract YouTube video ID from URL."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"(?:embed\/)([0-9A-Za-z_-]{11})",
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_word_frequency(text, min_length=4, top_n=50, additional_stop_words=None):
    try:
        if not text or not isinstance(text, str):
            logging.warning("Empty or invalid text for word frequency")
            return {}

        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            logging.info("Downloading NLTK stopwords corpus")
            nltk.download('stopwords', quiet=True)

        try:
            from nltk.corpus import stopwords
            nltk_stop_words = set(stopwords.words("english"))
        except (ImportError, LookupError):
            logging.warning("NLTK stopwords not available, using custom list")
            nltk_stop_words = set()

        custom_stop_words = {
            "like", "actually", "basically", "literally", "yeah", "okay", "um", "uh",
            "going", "getting", "think", "know", "mean", "just", "really", "very", 
            "kind", "sort", "thing", "things", "stuff", "way", "lot", "bit", "make", "made",
            "want", "need", "trying", "sure", "look", "looks", "looking",
            "dont", "cant", "wasnt", "isnt", "arent", "hasnt", "havent", "wouldnt",
            "ive", "youve", "weve", "theyre", "youre", "thats", "theres", 
            "today", "yesterday", "tomorrow", "time", "year", "month", "week", "day",
            "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
            "something", "someone", "everybody", "everyone", "anything", "everything",
            "back", "come", "goes", "around", "through"
        }
        
        stop_words = nltk_stop_words.union(custom_stop_words)
        
        if additional_stop_words:
            stop_words = stop_words.union(additional_stop_words)

        words = re.findall(r"\b\w+\b", text.lower())
        words = [word for word in words if len(word) >= min_length and word not in stop_words]
        
        word_counts = Counter(words)
        
        frequency_dict = dict(word_counts.most_common(top_n))

        if not frequency_dict:
            logging.info("No words found for word frequency")

        return frequency_dict

    except Exception as e:
        logging.error(f"Error generating word frequency: {e}", exc_info=True)
        return {}


async def download_audio(video_url):
    """Download audio from YouTube video."""
    ensure_directory(DOWNLOADS_DIR)
    cleanup_old_files(DOWNLOADS_DIR)

    try:
        yt = YouTube(video_url, on_progress_callback=on_download_progress, use_po_token=True)        audio_stream = yt.streams.get_audio_only()

        if not audio_stream:
            return {"status": "error", "message": "No audio stream available"}

        audio_file_name = sanitize_filename(yt.title)
        audio_file_path = os.path.join(DOWNLOADS_DIR, f"{audio_file_name}.m4a")

        audio_stream.download(
            output_path=DOWNLOADS_DIR, filename=f"{audio_file_name}.m4a"
        )

        if os.path.exists(audio_file_path):
            return {"status": "success", "audio_file": audio_file_path}
        else:
            return {"status": "error", "message": "Audio file download failed"}

    except Exception as e:
        logging.error(f"Failed to download audio from {video_url}: {e}")
        return {"status": "error", "message": str(e)}


def generate_fake_timestamps(transcript, words_per_second=2.5):
    sentences = re.split(r"(?<=[.!?])\s+", transcript)
    subtitles = []
    current_time = 0.0

    for sentence in sentences:
        if not sentence.strip():
            continue

        word_count = len(sentence.split())
        duration = max(1.5, (word_count / words_per_second))

        subtitles.append(
            {
                "start_seconds": round(current_time, 2),
                "end_seconds": round(current_time + duration, 2),
                "text": sentence.strip(),
            }
        )

        current_time += duration

    return subtitles


async def transcribe_audio(file_path):
    try:
        if not deepgram_api_key:
            return {"status": "error", "message": "Deepgram API key not provided"}

        deepgram = Deepgram(deepgram_api_key)

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio:
                source = {"buffer": audio.read(), "mimetype": "audio/m4a"}

                response = await deepgram.transcription.prerecorded(
                    source, {"smart_format": True, "model": "nova-2", "punctuate": True}
                )

        await delete_file(file_path)  # Clean up after transcription

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]

        # Generate fake timestamps for captions tab
        subtitles = generate_fake_timestamps(transcript)

        return {
            "status": "success",
            "transcript": transcript,  # Plain text for transcription tab
            "subtitles": subtitles,  # Fake timestamps for captions tab
            "source": "transcription",
        }

    except Exception as e:
        logging.error(f"Transcription error: {e}")
        await delete_file(file_path)
        return {"status": "error", "message": str(e)}


async def delete_file(file_path):
    """Safely delete a file."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Deleted file: {file_path}")
    except Exception as e:
        logging.error(f"Error deleting file {file_path}: {e}")


async def generate_srt_file(subtitles, video_title):
    ensure_directory(EXPORTS_DIR)  # Ensure exports directory exists

    srt_content = ""
    for i, sub in enumerate(subtitles, 1):
        start = format_timestamp_simple(sub.get("start_seconds", 0))
        end = format_timestamp_simple(sub.get("end_seconds", 0))
        text = sub.get("text", "")
        srt_content += f"{i}\n{start} --> {end}\n{text}\n\n"

    # Use more robust filename generation
    srt_filename = f"{sanitize_filename(video_title)}_captions.srt"
    srt_path = os.path.join(EXPORTS_DIR, srt_filename)

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)

    return srt_filename


async def process_batch(tasks):
    semaphore = asyncio.Semaphore(5)  # Limit concurrent API calls
    async with semaphore:
        return await asyncio.gather(*tasks)


def get_video_metadata(video_url):
    """Fetch metadata using YouTube API with enhanced error handling."""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            logging.error(f"Invalid YouTube URL: {video_url}")
            return {"error": "Invalid YouTube URL"}

        request = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=video_id
        )
        response = request.execute()

        if not response["items"]:
            logging.error(f"No video found for URL: {video_url}")
            return {"error": "Video not found"}

        video_data = response["items"][0]

        return {
            "title": video_data["snippet"].get("title", "Unknown Title"),
            "description": video_data["snippet"].get("description", ""),
            "thumbnail": video_data["snippet"]["thumbnails"]["high"]["url"],
            "author": video_data["snippet"].get("channelTitle", "Unknown Author"),
            "publish_date": video_data["snippet"].get("publishedAt", ""),
            "views": video_data["statistics"].get("viewCount", "N/A"),
            "duration": video_data["contentDetails"].get("duration", ""),
        }

    except Exception as e:
        logging.error(f"Detailed metadata fetch error: {e}")
        return {"error": str(e)}


def sanitize_filename(filename):
    """Sanitize the filename to avoid issues with invalid characters."""
    return "".join(
        char for char in filename if char.isalnum() or char in (" ", ".", "_")
    ).rstrip()


async def get_video_captions(video_url):
    try:
        headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
            }

        # Send a request to YouTube with the custom headers
        req = urllib.request.Request(video_url, headers=headers)
        urllib.request.urlopen(req)  # This ensures the request is made before pytubefix

        # Initialize YouTube object with po_token to bypass bot detection
        max_retries = 3
        for attempt in range(max_retries):
            try:
                yt = YouTube(video_url, use_po_token=True)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    raise e
        captions = yt.captions

        if not captions:
            return None

        caption_track = None
        for lang_code in ["a.en", "en"]:
            if lang_code in captions:
                caption_track = captions[lang_code]
                break

        if not caption_track:
            return None

        ensure_directory(CAPTIONS_DIR)
        srt_filename = f"{sanitize_filename(yt.title)}_captions.srt"
        srt_path = os.path.join(CAPTIONS_DIR, srt_filename)

        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(caption_track.generate_srt_captions())

        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()

        subtitles = parse_srt(srt_content)
        transcript = " ".join([sub["text"] for sub in subtitles])  # Remove timestamps

        return {
            "subtitles": subtitles,
            "transcript": transcript,  # New addition
            "srt_path": srt_path,
        }

    except Exception as e:
        logging.error(f"Error getting video captions: {e}")
        return None


def format_timestamp_simple(seconds):
    """Convert seconds to minutes:seconds format."""
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def parse_srt(srt_content):
    """Parse SRT format into structured subtitle data."""
    subtitles = []
    current_subtitle = {}
    lines = srt_content.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines
        if not line:
            i += 1
            continue

        # Try to parse as index number
        if line.isdigit():
            # Save previous subtitle if it exists
            if current_subtitle and "text" in current_subtitle:
                subtitles.append(current_subtitle)
            current_subtitle = {"index": int(line)}
            i += 1
            continue

        # Try to parse timestamp
        if "-->" in line:
            start, end = line.split("-->")
            seconds_start = parse_timestamp(start.strip())
            seconds_end = parse_timestamp(end.strip())

            # Store the seconds value for potential processing
            current_subtitle["start_seconds"] = seconds_start
            current_subtitle["end_seconds"] = seconds_end

            # Store the formatted MM:SS timestamp
            current_subtitle["start"] = format_timestamp_simple(seconds_start)
            current_subtitle["end"] = format_timestamp_simple(seconds_end)
            current_subtitle["text"] = ""
            i += 1
            continue

        # Must be subtitle text
        if "text" in current_subtitle:
            if current_subtitle["text"]:
                current_subtitle["text"] += " " + line
            else:
                current_subtitle["text"] = line
        i += 1

    # Add the last subtitle
    if current_subtitle and "text" in current_subtitle:
        subtitles.append(current_subtitle)

    return subtitles


def parse_timestamp(timestamp):
    """Convert SRT timestamp to seconds."""
    hours, minutes, seconds = timestamp.replace(",", ".").split(":")
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def parse_duration_to_seconds(duration_str):
    """Convert ISO 8601 duration string (PT1H30M15S) to seconds."""
    try:
        if not duration_str or not isinstance(duration_str, str):
            return None

        # Remove the 'PT' prefix
        duration = duration_str[2:]

        hours = 0
        minutes = 0
        seconds = 0

        # Extract hours if present
        if "H" in duration:
            hours_part = duration.split("H")[0]
            hours = int(hours_part)
            duration = duration.split("H")[1]

        # Extract minutes if present
        if "M" in duration:
            minutes_part = duration.split("M")[0]
            minutes = int(minutes_part)
            duration = duration.split("M")[1]

        # Extract seconds if present
        if "S" in duration:
            seconds_part = duration.split("S")[0]
            seconds = int(seconds_part)

        return hours * 3600 + minutes * 60 + seconds
    except Exception as e:
        logging.error(f"Error parsing duration: {e}")
        return None


def format_duration(seconds):
    """Format duration in seconds to human-readable format."""
    if not seconds:
        return "unknown duration"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        return f"{hours} hour{'s' if hours > 1 else ''} and {minutes} minute{'s' if minutes > 1 else ''}"
    else:
        return f"{minutes} minute{'s' if minutes > 1 else ''}"


def summarize_text(text, mode="short", duration_seconds=None):
    """Summarize text using Cohere's Chat endpoint based on selected mode and video duration."""
    try:
        # Default reading speed (words per minute)
        WPM = 150
        
        # Define target summary durations as percentages of original content
        summary_ratio = {
            "short": 0.07,    # ~7% of original duration
            "medium": 0.12,   # ~12% of original duration  
            "lengthy": 0.20,  # ~20% of original duration
        }
        
        # Determine approximate target word count based on duration
        if duration_seconds:
            hours = duration_seconds / 3600
            
            # Estimate original content word count (average speaking rate: ~150 words per minute)
            original_word_count = int(duration_seconds / 60 * WPM)
            
            # Calculate target summary word counts
            target_words = {
                "short": max(300, int(original_word_count * summary_ratio["short"])),
                "medium": max(500, int(original_word_count * summary_ratio["medium"])),
                "lengthy": max(800, int(original_word_count * summary_ratio["lengthy"]))
            }
            
            # Convert word counts to estimated paragraph counts (assuming ~100 words per paragraph)
            paragraph_counts = {
                "short": max(2, target_words["short"] // 100),
                "medium": max(3, target_words["medium"] // 100),
                "lengthy": max(5, target_words["lengthy"] // 100)
            }
            
            # Format length guidance in different ways to ensure clear communication
            length_guidance = {
                "short": f"approximately {paragraph_counts['short']} paragraphs (around {target_words['short']} words)",
                "medium": f"approximately {paragraph_counts['medium']} paragraphs (around {target_words['medium']} words)",
                "lengthy": f"approximately {paragraph_counts['lengthy']} paragraphs (around {target_words['lengthy']} words)"
            }
            
            # Add time estimates (assuming reading speed of ~150 words per minute)
            read_time = {
                "short": max(2, target_words["short"] // WPM),
                "medium": max(3, target_words["medium"] // WPM),
                "lengthy": max(5, target_words["lengthy"] // WPM)
            }
        else:
            # Default if no duration provided
            length_guidance = {
                "short": "2-3 paragraphs (around 300 words)",
                "medium": "4-5 paragraphs (around 500 words)",
                "lengthy": "7-8 paragraphs (around 800 words)",
            }
            
            read_time = {
                "short": 2,
                "medium": 3,
                "lengthy": 5
            }

        # Base prompts that explicitly state expected length
        if mode == "short":
            message = f"""Generate a comprehensive summary of this transcript in {length_guidance['short']}. 
This is from a video that's {format_duration(duration_seconds)} long.
Your summary should take approximately {read_time['short']} minutes to read aloud.
Focus on capturing the main topics, key arguments, and essential takeaways in chronological order.

TRANSCRIPT:
{text}"""

        elif mode == "medium":
            message = f"""Generate a detailed summary of {length_guidance['medium']} from this transcript.
This is from a video that's {format_duration(duration_seconds)} long.
Your summary should take approximately {read_time['medium']} minutes to read aloud.
Include all main points with supporting details while maintaining a clear narrative structure.

TRANSCRIPT:
{text}"""

        elif mode == "lengthy":
            message = f"""Generate a very comprehensive summary of {length_guidance['lengthy']} from this transcript.
This is from a video that's {format_duration(duration_seconds)} long.
Your summary should take approximately {read_time['lengthy']} minutes to read aloud.
Cover all important topics, key arguments, and conclusions in detail with a thorough exploration of the content.

TRANSCRIPT:
{text}"""

        else:
            # Default to medium if an invalid mode is provided
            message = f"""Generate a summary of this transcript in {length_guidance['medium']}.
This is from a video that's {format_duration(duration_seconds)} long.
Your summary should take approximately {read_time['medium']} minutes to read aloud.
Focus on key points and maintain chronological order.

TRANSCRIPT:
{text}"""

        # Special handling for very long videos
        if hours >= 2:
            message += f"\n\nIMPORTANT: Since this is a lengthy video (over 2 hours), ensure your summary is substantial enough to cover all key points. The summary should be AT LEAST {length_guidance[mode]}."

        response = co.chat(
            model="command-r-plus-08-2024",
            messages=[{"role": "user", "content": message}],
        )
        return response.message.content[0].text
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."


def generate_audio(summary_text, filename_prefix):
    """Convert summary text to audio using gTTS with improved settings"""
    try:
        if not summary_text:
            return None

        # Create unique filename
        hash_id = hashlib.md5(summary_text.encode()).hexdigest()[:8]
        filename = f"{filename_prefix}_{hash_id}.mp3"
        filepath = os.path.join(EXPORTS_DIR, filename)

        # Generate and save audio with improved settings
        tts = gTTS(text=summary_text, lang="en", slow=False, tld="com")
        tts.save(filepath)
        return filename
    except Exception as e:
        logging.error(f"Audio generation failed: {e}")
        return None


def export_summary_to_pdf(summary_text, filename):
    """Export summary text to a PDF file.

    Args:
        summary_text (str): The text content to export
        filename (str): Just the filename (not the full path)

    Returns:
        str: The filename if successful, None otherwise
    """
    try:
        ensure_directory(EXPORTS_DIR)
        filepath = os.path.join(EXPORTS_DIR, filename)

        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        story.append(Paragraph("Video Summary", styles["Heading1"]))

        # Split summary into paragraphs
        paragraphs = summary_text.split("\n")
        for para in paragraphs:
            if para.strip():
                story.append(Paragraph(para.strip(), styles["Normal"]))

        doc.build(story)
        return filename
    except Exception as e:
        logging.error(f"PDF export failed: {e}")
        return None
