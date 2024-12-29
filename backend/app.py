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

# Configure logging to be more verbose
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Outputs to console
        logging.FileHandler("app.log"),  # Optional: log to file
    ],
)

# Create Flask app with correct static file handling
app = Flask(__name__, static_folder="frontend", static_url_path="/")
CORS(app, resources={r"/*": {"origins": "*"}})


@app.route("/")
def serve_index():
    logging.info("Serving index.html")
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    logging.info(f"Serving static file: {path}")
    return send_from_directory("frontend", path)


# Detailed logging for the process route
@app.route("/process", methods=["POST"])
def process_video():
    logging.info("Received request to /process")
    logging.debug(f"Request method: {request.method}")
    logging.debug(f"Request headers: {request.headers}")

    try:
        # Force JSON parsing with detailed logging
        request_data = request.get_json(force=True)
        logging.debug(f"Parsed request data: {request_data}")

        video_url = request_data.get("url")
        logging.info(f"Processing video URL: {video_url}")

        if not video_url:
            logging.error("No URL provided")
            return jsonify({"error": "No URL provided"}), 400

        # Async processing with more detailed error handling
        async def process_async():
            try:
                # Fetch metadata with enhanced logging
                metadata = get_video_metadata(video_url)
                logging.debug(f"Retrieved metadata: {metadata}")

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

                # Continue with existing async processing
                downloaded_audio = await download_audio(video_url)
                if downloaded_audio["status"] == "error":
                    logging.error(
                        f"Audio download error: {downloaded_audio['message']}"
                    )
                    return jsonify({"error": downloaded_audio["message"]}), 500

                transcription_response = await transcribe_audio(
                    downloaded_audio["audio_file"]
                )

                if transcription_response["status"] == "error":
                    logging.error(
                        f"Transcription error: {transcription_response['message']}"
                    )
                    return jsonify({"error": transcription_response["message"]}), 500

                transcript = (
                    transcription_response.get("channel", {})
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )

                summary = summarize_text(transcript)

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

            except Exception as async_error:
                logging.exception(f"Async processing error: {async_error}")
                return jsonify({"error": str(async_error)}), 500

        # Run the async function and get its result
        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"Unexpected error in processing: {e}")
        return jsonify({"error": str(e)}), 500


# Ensure downloads folder exists
os.makedirs(os.path.join(os.path.dirname(__file__), "downloads"), exist_ok=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
