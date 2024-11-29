import os
import logging
import aiohttp
import cohere
import re
import yt_dlp  # Using yt-dlp as a more reliable alternative to pytubefix
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()
deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
cohere_api_key = os.getenv("COHERE_API_KEY")

# Initialize Cohere client
co = cohere.Client(cohere_api_key)


async def download_audio(video_url):
    """Download audio from YouTube video using yt-dlp."""

    downloads_folder = "downloads"
    if not os.path.exists(downloads_folder):
        os.makedirs(downloads_folder)

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "outtmpl": os.path.join(downloads_folder, "%(title)s.%(ext)s"),
            "nooverwrites": True,
            "no_color": True,
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            audio_file_name = ydl.prepare_filename(info_dict)
            audio_file_path = audio_file_name.rsplit(".", 1)[0] + ".mp3"

        if os.path.exists(audio_file_path):
            return {"status": "success", "audio_file": audio_file_path}
        else:
            return {"status": "error", "message": "Audio file download failed."}

    except Exception as e:
        logging.error(f"Failed to download audio from {video_url}: {e}")
        return {"status": "error", "message": str(e)}


async def transcribe_audio(file_path):
    """Transcribe audio using Deepgram."""
    try:
        if not deepgram_api_key:
            return {"status": "error", "message": "Deepgram API key not provided"}

        deepgram = Deepgram(deepgram_api_key)

        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as audio:
                source = {"buffer": audio.read(), "mimetype": "audio/mp3"}

                response = await deepgram.transcription.prerecorded(
                    source, {"smart_format": True, "model": "nova-2", "punctuate": True}
                )

        # Delete the audio file after transcription
        await delete_file(file_path)

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        return {
            "status": "success",
            "channel": {"alternatives": [{"transcript": transcript}]},
        }

    except Exception as e:
        logging.error(f"Transcription error: {e}")
        # Attempt to delete file even if transcription fails
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


def get_video_metadata(video_url):
    """Fetch metadata for a YouTube video using yt-dlp."""
    try:
        ydl_opts = {
            "quiet": True,
            "no_color": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Validate and standardize URL
            video_url = standardize_youtube_url(video_url)

            # Extract video info
            info_dict = ydl.extract_info(video_url, download=False)

            # Prepare metadata
            metadata = {
                "title": info_dict.get("title", "Unknown Title"),
                "description": info_dict.get("description", "No description available"),
                "thumbnail": info_dict.get("thumbnail", ""),
            }

        return metadata

    except Exception as e:
        logging.error(f"Error fetching metadata for {video_url}: {e}")
        return None


def standardize_youtube_url(url):
    """
    Standardize YouTube URL to ensure consistent parsing.
    Supports various YouTube URL formats.
    """
    # List of possible YouTube URL patterns
    youtube_patterns = [
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)",
        r"(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^?&]+)",
        r"(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?&]+)",
    ]

    # Try to match and extract video ID
    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"

    # If no match found, return original URL
    return url


def sanitize_filename(filename):
    """Sanitize the filename to avoid issues with invalid characters."""
    return "".join(
        char for char in filename if char.isalnum() or char in (" ", ".", "_")
    ).rstrip()


def summarize_text(text):
    """Summarize text using Cohere's free tier."""
    try:
        response = co.summarize(
            text=text, length="medium", format="paragraph", temperature=0.3
        )
        return response.summary
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return "Summary could not be generated."
