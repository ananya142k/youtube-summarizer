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
from functools import wraps
from collections import defaultdict
import time
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)

# Create Flask app
app = Flask(__name__, static_folder="frontend", static_url_path="/")
CORS(app, resources={r"/*": {"origins": "*"}})

# Rate limiting configuration
RATE_LIMIT = 10  # requests
TIME_WINDOW = 600  # seconds (10 minutes)
request_counts = defaultdict(list)
request_lock = threading.Lock()

def clean_old_requests():
    """Remove requests older than the time window"""
    current_time = time.time()
    with request_lock:
        for ip in list(request_counts.keys()):
            request_counts[ip] = [timestamp for timestamp in request_counts[ip] 
                                if current_time - timestamp < TIME_WINDOW]
            if not request_counts[ip]:
                del request_counts[ip]

def rate_limit(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        ip = request.remote_addr
        current_time = time.time()
        
        # Clean old requests first
        clean_old_requests()
        
        with request_lock:
            # Add current request timestamp
            request_counts[ip].append(current_time)
            
            # Check if too many requests
            if len(request_counts[ip]) > RATE_LIMIT:
                logging.warning(f"Rate limit exceeded for IP: {ip}")
                return jsonify({
                    "error": "Too many requests. Please try again later.",
                    "retry_after": int(TIME_WINDOW - (current_time - request_counts[ip][0]))
                }), 429

        return f(*args, **kwargs)
    return decorated_function

# Ensure downloads folder exists
os.makedirs(os.path.join(os.path.dirname(__file__), "downloads"), exist_ok=True)

@app.route("/")
def serve_index():
    logging.info("Serving index.html")
    return send_from_directory("frontend", "index.html")

@app.route("/<path:path>")
def serve_static(path):
    logging.info(f"Serving static file: {path}")
    return send_from_directory("frontend", path)

@app.route("/process", methods=["POST"])
@rate_limit
def process_video():
    logging.info("Received request to /process")
    logging.debug(f"Request headers: {request.headers}")

    try:
        request_data = request.get_json(force=True)
        logging.debug(f"Parsed request data: {request_data}")

        video_url = request_data.get("url")
        if not video_url:
            logging.error("No URL provided")
            return jsonify({"error": "No URL provided"}), 400

        logging.info(f"Processing video URL: {video_url}")

        async def process_async():
            try:
                # Fetch metadata
                metadata = get_video_metadata(video_url)
                logging.debug(f"Retrieved metadata: {metadata}")

                if not metadata:
                    logging.error(f"Failed to retrieve metadata for URL: {video_url}")
                    return jsonify({
                        "error": "Video metadata could not be retrieved. Please check the URL."
                    }), 404

                if isinstance(metadata, dict) and metadata.get('status') == 'bot_detection':
                    logging.warning("YouTube bot detection triggered")
                    return jsonify({
                        "error": metadata['error']
                    }), 429

                if isinstance(metadata, dict) and metadata.get('status') == 'error':
                    logging.error(f"Metadata error: {metadata['error']}")
                    return jsonify({
                        "error": metadata['error']
                    }), 400

                # Download audio
                downloaded_audio = await download_audio(video_url)
                if downloaded_audio["status"] == "error":
                    logging.error(f"Audio download error: {downloaded_audio['message']}")
                    return jsonify({"error": downloaded_audio["message"]}), 500

                # Transcribe audio
                transcription_response = await transcribe_audio(downloaded_audio["audio_file"])
                if transcription_response["status"] == "error":
                    logging.error(f"Transcription error: {transcription_response['message']}")
                    return jsonify({"error": transcription_response["message"]}), 500

                transcript = (
                    transcription_response.get("channel", {})
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )

                # Generate summary
                summary = summarize_text(transcript)
                if not summary:
                    logging.warning("Summary generation failed")
                    summary = "Summary could not be generated. Please try again."

                return jsonify({
                    "metadata": metadata,
                    "transcription": transcript,
                    "summary": summary,
                }), 200

            except Exception as async_error:
                logging.exception(f"Async processing error: {async_error}")
                return jsonify({"error": str(async_error)}), 500

        return asyncio.run(process_async())

    except Exception as e:
        logging.exception(f"Unexpected error in processing: {e}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({
        "error": "Too many requests. Please try again later.",
        "retry_after": TIME_WINDOW
    }), 429

@app.errorhandler(500)
def internal_error(e):
    logging.exception("Internal server error")
    return jsonify({
        "error": "An internal server error occurred. Please try again later."
    }), 500

@app.errorhandler(404)
def not_found_error(e):
    return jsonify({
        "error": "The requested resource was not found."
    }), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)