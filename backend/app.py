from flask import Flask, request, jsonify, send_from_directory, send_file
from utils import (
    get_video_metadata,
    download_audio,
    summarize_text,
    transcribe_audio,
    get_word_frequency,
    get_youtube_player_data,
    generate_srt_file,
)
import asyncio
import os
import logging
from cachetools import TTLCache

if not os.path.exists("exports"):
    os.makedirs("exports")

# Initialize cache with 1-hour timeout
cache = TTLCache(maxsize=100, ttl=3600)
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)


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
            logging.debug("Returning cached result")
            return jsonify(cached_result), 200

        logging.debug(f"Processing video URL: {video_url}")

        async def process_async():
            metadata = get_video_metadata(video_url)
            if not metadata:
                return jsonify({"error": "Video metadata not found"}), 404

            # Get YouTube player data
            player_data = get_youtube_player_data(video_url)
            if player_data.get("error"):
                return jsonify({"error": player_data["error"]}), 400

            downloaded_audio = await download_audio(video_url)
            if downloaded_audio["status"] == "error":
                logging.error(f"Error downloading audio: {downloaded_audio['message']}")
                return jsonify({"error": downloaded_audio["message"]}), 500

            transcription_response = await transcribe_audio(
                downloaded_audio["audio_file"]
            )
            logging.debug(f"Transcription response: {transcription_response}")

            if transcription_response["status"] == "error":
                return jsonify({"error": transcription_response["message"]}), 500

            transcript = (
                transcription_response.get("channel", {})
                .get("alternatives", [{}])[0]
                .get("transcript", "")
            )

            # Generate word frequency data
            word_frequency = get_word_frequency(transcript)

            # Generate summary
            summary = summarize_text(transcript)

            # Generate SRT file
            srt_filename = generate_srt_file(transcript, metadata["title"])

            result = {
                "metadata": metadata,
                "player_data": player_data,
                "transcription": transcript,
                "summary": summary,
                "word_frequency": word_frequency,
                "srt_filename": srt_filename,
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


if __name__ == "__main__":
    app.run(debug=True)
