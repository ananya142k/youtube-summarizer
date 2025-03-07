from flask import Flask, request, jsonify, send_from_directory, send_file
import os
import logging
from datetime import datetime 
from cachetools import TTLCache
from functools import lru_cache
import asyncio
import sys
from pathlib import Path

# Define base paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Gets the directory where app.py is located
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
CAPTIONS_DIR = os.path.join(BASE_DIR, "captions")

# Initialize directories with absolute paths
for directory in [EXPORTS_DIR, DOWNLOADS_DIR, CAPTIONS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logging.info(f"Created directory: {directory}")

# Import utils and set the directories
from utils import (
    get_video_metadata,
    download_audio,
    summarize_text,
    transcribe_audio,
    get_word_frequency,
    get_youtube_player_data,
    get_video_captions,
    generate_srt_file,
    generate_audio,
    export_summary_to_pdf,
    cleanup_old_files,
    sanitize_filename,
    parse_duration_to_seconds,  
    format_duration,
    set_directories,  # Import the new function
)

# Set directories in utils
set_directories(EXPORTS_DIR, DOWNLOADS_DIR, CAPTIONS_DIR)

# Initialize cache with 1-hour timeout
cache = TTLCache(maxsize=100, ttl=3600)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)


@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Global error handler: {str(e)}")
    return jsonify({"error": "An unexpected error occurred", "details": str(e)}), 500

# Determine if running in development or production
IS_PRODUCTION = os.environ.get('RENDER', False)

# Adjust frontend directory path
if IS_PRODUCTION:
    FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
else:
    FRONTEND_DIR = os.path.join(BASE_DIR, "../frontend")


@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(FRONTEND_DIR, filename)


@app.route("/process", methods=["POST"])
def process_video():
    try:
        video_url = request.json.get("url")

        if not video_url:
            return jsonify({"error": "No URL provided"}), 400

        summary_mode = request.json.get(
            "summary_mode", "short"
        )  # Get mode from request

        # Create composite cache key
        cache_key = f"{video_url}:{summary_mode}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return jsonify(cached_result), 200

        logging.info(f"Processing video URL: {video_url}")

        async def process_async():
            try:
                metadata = get_video_metadata(video_url)
                if not metadata:
                    logging.error(f"Metadata retrieval failed: {metadata}")
                    return jsonify({"error": "Video metadata not found"}), 404

                player_data = get_youtube_player_data(video_url)
                if player_data.get("error"):
                    return jsonify({"error": player_data["error"]}), 400
                duration_seconds = None
                if "duration" in metadata:
                    duration_seconds = parse_duration_to_seconds(metadata["duration"])
                    logging.info(f"Video duration: {format_duration(duration_seconds)}")
                # Step 1: Attempt to get official captions
                captions_response = await get_video_captions(video_url)

                if captions_response:
                    subtitles = captions_response["subtitles"]  # Use official captions
                    transcript = " ".join(
                        [sub["text"] for sub in subtitles]
                    )  # Remove timestamps
                    subtitles_source = "youtube_captions"
                else:
                    # Step 2: If no official captions, download audio and transcribe
                    downloaded_audio = await download_audio(video_url)
                    if downloaded_audio["status"] == "error":
                        return jsonify({"error": downloaded_audio["message"]}), 500

                    transcription_response = await transcribe_audio(
                        downloaded_audio["audio_file"]
                    )
                    if transcription_response["status"] == "error":
                        return (
                            jsonify({"error": transcription_response["message"]}),
                            500,
                        )

                    transcript = transcription_response["transcript"]
                    subtitles = transcription_response["subtitles"]  # Fake timestamps
                    subtitles_source = "generated_from_transcription"

                # Step 3: Generate SRT file for captions
                srt_filename = await generate_srt_file(subtitles, metadata["title"])

                # Step 4: Generate summary
                summary = summarize_text(transcript, mode=summary_mode, duration_seconds=duration_seconds)

                # Step 5: Generate audio summary
                audio_filename = generate_audio(summary, f"summary_{metadata['title']}")

                word_frequency = get_word_frequency(transcript)
                if not word_frequency:
                    logging.warning(f"No word frequency data generated for transcript")
                result = {
                    "metadata": metadata,
                    "player_data": player_data,
                    "transcription": transcript,
                    "subtitles": subtitles,
                    "summary": summary,
                    "transcription_source": (
                        "official_captions" if captions_response else "deepgram"
                    ),
                    "word_frequency": word_frequency or {},
                    "subtitles_source": subtitles_source,
                    "srt_filename": srt_filename,
                    "audio_filename": audio_filename,
                }

                cache[cache_key] = result
                return jsonify(result), 200
            except Exception as inner_e:
                logging.exception(f"Inner async processing error: {inner_e}")
                return jsonify({"error": str(inner_e)}), 500

        cleanup_old_files(EXPORTS_DIR)
        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/exports/<filename>")
def serve_exports(filename):
    try:
        return send_from_directory(EXPORTS_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/export-summary", methods=["POST"])
def export_summary():
    try:
        data = request.json
        format_type = data.get("format", "txt")
        content = data.get("content", "")
        title = sanitize_filename(data.get("title", "summary"))

        # Log information for debugging
        logging.info(f"Exporting summary: format={format_type}, title={title}")
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"{title}_{timestamp}.{format_type}"
        filepath = os.path.join(EXPORTS_DIR, filename)
        
        logging.info(f"Export path: {filepath}")

        if format_type == "pdf":
            # Just pass the filename, not the full path
            result = export_summary_to_pdf(content, filename)
            if not result:
                raise Exception("PDF generation failed")
            # The filepath should be where the function saved the file
            filepath = os.path.join(EXPORTS_DIR, result)
        else:
            # For text files, write directly to the path
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

        # Check if file exists before sending
        if not os.path.exists(filepath):
            logging.error(f"File not found after export: {filepath}")
            return jsonify({"error": "File not found after export"}), 500
            
        logging.info(f"File created successfully, sending file: {filepath}")
        return send_file(filepath, as_attachment=True, download_name=filename)

    except Exception as e:
        logging.exception(f"Export error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)