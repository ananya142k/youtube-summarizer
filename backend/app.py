from flask import Flask, request, jsonify, send_from_directory
from backend.utils import (
    get_video_metadata,
    download_audio,
    summarize_text,
    transcribe_audio,
)
import asyncio
import os
import logging
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__, static_folder="frontend", static_url_path="/")
CORS(app)


@app.route("/")
def serve_index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)


# Route to process the YouTube video and return summary, transcript, etc.
@app.route("/process", methods=["POST"])
def process_video():
    # Log entire request details
    logging.debug(f"Received request headers: {request.headers}")
    logging.debug(f"Received request method: {request.method}")
    logging.debug(f"Received request content type: {request.content_type}")

    try:
        # Log raw request data
        request_data = request.get_json(force=True)
        logging.debug(f"Received JSON data: {request_data}")

        video_url = request_data.get("url")

        if not video_url:
            logging.error("No URL provided")
            return jsonify({"error": "No URL provided"}), 400

        logging.debug(f"Processing video URL: {video_url}")

        # Use asyncio to run coroutines
        async def process_async():
            # Directly use the video URL for fetching metadata
            metadata = get_video_metadata(video_url)

            if not metadata:
                logging.error(f"Failed to retrieve metadata for URL: {video_url}")
                return (
                    jsonify(
                        {
                            "error": "Video metadata could not be retrieved. Please check the URL."
                        }
                    ),
                    404,
                )

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
            logging.debug(f"Transcript: {transcript}")

            summary = summarize_text(transcript)
            logging.debug(f"Summary: {summary}")

            return (
                jsonify(
                    {
                        "metadata": metadata,
                        "transcription": transcript,
                        "summary": summary,
                    }
                ),
                200,
            )

        # Run the async function and get its result
        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"Unexpected error in processing: {e}")
        return jsonify({"error": str(e)}), 500


# Ensure downloads folder exists
os.makedirs(os.path.join(os.path.dirname(__file__), "downloads"), exist_ok=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
