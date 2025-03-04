from flask import Flask, request, jsonify, send_from_directory, send_file
from utils import (
    get_video_metadata,
    download_audio,
    summarize_text,
    transcribe_audio,
    get_word_frequency,
    get_youtube_player_data,
    get_video_captions,
    generate_srt_file
)
import asyncio
import os
import logging
from cachetools import TTLCache
from functools import lru_cache

# Initialize directories
for directory in ["exports", "downloads", "captions"]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Initialize cache with 1-hour timeout
cache = TTLCache(maxsize=100, ttl=3600)
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Global error handler: {str(e)}")
    return jsonify({
        "error": "An unexpected error occurred",
        "details": str(e)
    }), 500

@app.route("/")
def serve_index():
    return send_from_directory("../frontend", "index.html")

@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory("../frontend", filename)

@app.route("/process", methods=["POST"])
def process_video():
    try:
        video_url = request.json.get("url")

        if not video_url:
            return jsonify({"error": "No URL provided"}), 400

        # Check cache
        cached_result = cache.get(video_url)
        if cached_result:
            logging.info("Returning cached result")
            return jsonify(cached_result), 200

        logging.info(f"Processing video URL: {video_url}")

        async def process_async():
            # Get metadata and player data
            metadata = get_video_metadata(video_url)
            if not metadata:
                return jsonify({"error": "Video metadata not found"}), 404

            player_data = get_youtube_player_data(video_url)
            if player_data.get("error"):
                return jsonify({"error": player_data["error"]}), 400

            # Step 1: Always get transcription from Deepgram for the transcription tab
            downloaded_audio = await download_audio(video_url)
            if downloaded_audio["status"] == "error":
                logging.error(f"Error downloading audio: {downloaded_audio['message']}")
                return jsonify({"error": downloaded_audio["message"]}), 500

            transcription_response = await transcribe_audio(downloaded_audio["audio_file"])
            if transcription_response["status"] == "error":
                return jsonify({"error": transcription_response["message"]}), 500

            transcript = transcription_response["transcript"]
            deepgram_subtitles = transcription_response["subtitles"]

            # Step 2: Try to get official YouTube captions for the subtitles tab
            captions_response = await get_video_captions(video_url)
            
            # If official captions exist, use them for subtitles tab
            if captions_response:
                subtitles = captions_response["subtitles"]
                # Clean up captions file
                if "srt_path" in captions_response:
                    os.remove(captions_response["srt_path"])
                subtitles_source = "youtube_captions"
            else:
                # Step 3: If no official captions, use the Deepgram transcription with fake timestamps
                subtitles = deepgram_subtitles
                subtitles_source = "generated_from_transcription"

            # Generate SRT file
            srt_filename = await generate_srt_file(subtitles, metadata["title"])

            # Generate word frequency data
            word_frequency = get_word_frequency(transcript)

            # Generate summary
            summary = summarize_text(transcript)

            result = {
                "metadata": metadata,
                "player_data": player_data,
                "transcription": transcript,
                "subtitles": subtitles,
                "summary": summary,
                "word_frequency": word_frequency,
                "transcription_source": "deepgram",
                "subtitles_source": subtitles_source,
                "srt_filename": srt_filename
            }

            # Cache the result
            cache[video_url] = result

            return jsonify(result), 200

        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"An unexpected error occurred: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/exports/<filename>")
def serve_exports(filename):
    try:
        return send_from_directory("exports", filename, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/export-summary", methods=["POST"])
def export_summary():
    data = request.json
    format_type = data.get('format', 'txt')
    
    try:
        filename = f"summary_{datetime.now().strftime('%Y%m%d%H%M%S')}.{format_type}"
        filepath = os.path.join(EXPORTS_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(data['content'])
        
        return jsonify({"filename": filename})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)