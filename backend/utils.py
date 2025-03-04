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

# Load environment variables
load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

# Initialize clients
co = cohere.ClientV2(cohere_api_key)
youtube = build("youtube", "v3", developerKey=youtube_api_key)

# Constants
EXPORTS_DIR = "exports"
DOWNLOADS_DIR = "downloads"
CAPTIONS_DIR = "captions"
CLEANUP_THRESHOLD = timedelta(hours=24)  # Clean files older than 24 hours
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
    ensure_directory(directory)
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


# Run cleanup on startup
for directory in [EXPORTS_DIR, DOWNLOADS_DIR, CAPTIONS_DIR]:
    cleanup_old_files(directory)


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


def get_word_frequency(text, min_length=4, top_n=50):
    """Generate word frequency data for visualization."""
    words = re.findall(r"\b\w+\b", text.lower())
    words = [word for word in words if len(word) >= min_length]
    word_counts = Counter(words)

    # Remove common stop words
    stop_words = {"this", "that", "have", "what", "with", "from", "they"}
    for word in stop_words:
        word_counts.pop(word, None)

    return dict(word_counts.most_common(top_n))


async def get_video_captions(video_url):
    """Get video captions using PyTubeFix."""
    try:
        yt = YouTube(video_url)
        captions = yt.captions

        if not captions:
            return None

        # Try to get English captions first, fall back to any available captions
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

        # Generate and save SRT captions
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(caption_track.generate_srt_captions())

        # Parse the SRT content to create the subtitles structure
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        
        subtitles = parse_srt(srt_content)
        
        return {
            "subtitles": subtitles,
            "srt_path": srt_path
        }

    except Exception as e:
        logging.error(f"Error getting video captions: {e}")
        return None

async def download_audio(video_url):
    """Download audio from YouTube video."""
    ensure_directory(DOWNLOADS_DIR)
    cleanup_old_files(DOWNLOADS_DIR)

    try:
        yt = YouTube(video_url, on_progress_callback=on_download_progress)
        audio_stream = yt.streams.get_audio_only()

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


# In utils.py, improve generate_fake_timestamps
def generate_fake_timestamps(transcript, words_per_second=2.5):
    """Generate more precise fake timestamps for a transcript."""
    sentences = re.split(r'(?<=[.!?])\s+', transcript)
    subtitles = []
    current_time = 0.0
    
    for sentence in sentences:
        if not sentence.strip():
            continue
            
        word_count = len(sentence.split())
        # More precise duration calculation
        duration = max(2.0, (word_count / words_per_second))
        
        subtitles.append({
            "start_seconds": round(current_time, 2),
            "end_seconds": round(current_time + duration, 2),
            "text": sentence.strip()
        })
        
        current_time += duration
        
    return subtitles



async def transcribe_audio(file_path):
    """Transcribe audio using Deepgram."""
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

        # Delete the audio file after transcription
        await delete_file(file_path)

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        
        # Generate fake timestamps for the transcript
        subtitles = generate_fake_timestamps(transcript)
        
        return {
            "status": "success",
            "transcript": transcript,
            "subtitles": subtitles,
            "source": "transcription"
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
    srt_content = ""
    for i, sub in enumerate(subtitles, 1):
        # Use format_timestamp_simple which returns minutes:seconds format
        start = format_timestamp_simple(sub["start_seconds"])
        end = format_timestamp_simple(sub["end_seconds"])
        srt_content += f"{i}\n{start} --> {end}\n{sub['text']}\n\n"
    
    srt_filename = f"{sanitize_filename(video_title)}.srt"
    srt_path = os.path.join(EXPORTS_DIR, srt_filename)
    
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    return srt_filename

async def process_batch(tasks):
    semaphore = asyncio.Semaphore(5)  # Limit concurrent API calls
    async with semaphore:
        return await asyncio.gather(*tasks)
    
def get_video_metadata(video_url):
    """Fetch metadata using YouTube API instead of pytubefix."""
    try:
        video_id = extract_video_id(video_url)
        if not video_id:
            return {"error": "Invalid YouTube URL"}

        request = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=video_id
        )
        response = request.execute()

        if not response["items"]:
            return {"error": "Video not found"}

        video_data = response["items"][0]

        return {
            "title": video_data["snippet"]["title"],
            "description": video_data["snippet"]["description"],
            "thumbnail": video_data["snippet"]["thumbnails"]["high"]["url"],
            "author": video_data["snippet"]["channelTitle"],
            "publish_date": video_data["snippet"]["publishedAt"],
            "views": video_data["statistics"].get("viewCount", "N/A"),
            "duration": video_data["contentDetails"]["duration"],
        }

    except Exception as e:
        logging.error(f"Error fetching YouTube metadata: {e}")
        return {"error": str(e)}

def sanitize_filename(filename):
    """Sanitize the filename to avoid issues with invalid characters."""
    return "".join(
        char for char in filename if char.isalnum() or char in (" ", ".", "_")
    ).rstrip()

async def get_video_captions(video_url):
    """Get video captions using PyTubeFix."""
    try:
        yt = YouTube(video_url)
        captions = yt.captions

        if not captions:
            return None

        # Try to get English captions first, fall back to any available captions
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

        # Generate and save SRT captions
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(caption_track.generate_srt_captions())

        # Parse the SRT content to create the subtitles structure
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        
        subtitles = parse_srt(srt_content)
        
        return {
            "subtitles": subtitles,
            "srt_path": srt_path
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
            if current_subtitle and 'text' in current_subtitle:
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
    if current_subtitle and 'text' in current_subtitle:
        subtitles.append(current_subtitle)

    return subtitles


def parse_timestamp(timestamp):
    """Convert SRT timestamp to seconds."""
    hours, minutes, seconds = timestamp.replace(",", ".").split(":")
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)

    async def _get_captions(self, video_url: str) -> dict[str, any]:
        """Get and parse video captions."""
        try:
            yt = YouTube(video_url)
            captions = yt.captions

            if not captions:
                return None

            # Try to get English captions first, fall back to any available
            caption_track = None
            for lang_code in ["a.en", "en"]:
                if lang_code in captions:
                    caption_track = captions[lang_code]
                    break

            if not caption_track and captions:
                caption_track = list(captions.values())[0]

            if caption_track:
                srt_content = caption_track.generate_srt_captions()
                subtitles = self._parse_srt(srt_content)

                # Create clean transcript (text only)
                transcript = " ".join(sub["text"] for sub in subtitles)

                return {
                    "transcript": transcript,
                    "subtitles": subtitles,
                    "source": "captions",
                }

            return None

        except Exception as e:
            self.logger.error(f"Error getting video captions: {e}")
            return None

    async def process_video(self, video_url: str) -> dict[str, any]:
        try:
            video_id = self.extract_video_id(video_url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            # Parallel fetch of metadata and captions
            metadata_task = asyncio.create_task(self._get_metadata(video_id))
            captions_task = asyncio.create_task(self._get_captions(video_url))

            metadata = await metadata_task
            captions_data = await captions_task

            if not captions_data:
                # Fall back to audio transcription if no captions
                audio_file = await self._download_audio(video_url)
                transcript_data = await self._transcribe_audio(audio_file)
                transcript = transcript_data["transcript"]
                subtitles = None  # No subtitles available for audio transcription
            else:
                transcript = captions_data["transcript"]
                subtitles = captions_data["subtitles"]

            # Process transcript
            word_frequency = self._get_word_frequency(transcript)
            summary = await self._generate_summary(transcript)

            return {
                "metadata": metadata,
                "transcription": transcript,
                "subtitles": subtitles,
                "summary": summary,
                "word_frequency": word_frequency,
            }

        except Exception as e:
            self.logger.error(f"Error processing video: {e}")
            raise


def summarize_text(text):
    """Summarize text using Cohere's Chat endpoint."""
    try:
        message = f"Generate a concise summary of this text as a single paragraph. Focus on key points and maintain chronological order.\n\n{text}"
        response = co.chat(
            model="command-r-plus-08-2024",
            messages=[{"role": "user", "content": message}],
        )
        return response.message.content[0].text
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."
