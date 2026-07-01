"""
Provenance Guard — Flask API entry point.

M4 scope: /submit combines both signals via compute_confidence.
"""

import uuid

from flask import Flask, jsonify, request

from signals import compute_confidence, llm_detector, stylometry_signal
from storage import get_log, log_submission

# Create the Flask application instance.
# __name__ tells Flask where to look for templates/static files (not used yet).
app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Liveness check for deploy scripts and load balancers."""
    return jsonify({"status": "ok"})


@app.route("/submit", methods=["POST"])
def submit():
    """
    Accept creator text for classification.

    Expected JSON body:
        {
            "text": "<the content to classify>",
            "creator_id": "<who submitted it>"
        }

    Runs both detection signals and returns combined classification results.
    """
    # request.get_json() parses the POST body as JSON (returns None if missing/invalid).
    body = request.get_json(silent=True)

    if body is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    # Pull fields out of the parsed dict; .get() returns None if the key is absent.
    text = body.get("text")
    creator_id = body.get("creator_id")

    # Validate both required fields are present and non-empty strings.
    missing = []
    if not text or not isinstance(text, str):
        missing.append("text")
    if not creator_id or not isinstance(creator_id, str):
        missing.append("creator_id")

    if missing:
        return (
            jsonify({"error": f"Missing or invalid required fields: {', '.join(missing)}"}),
            400,
        )

    llm_score = llm_detector(text)
    stylometry_score = stylometry_signal(text)
    confidence = compute_confidence(llm_score, stylometry_score)

    if confidence >= 0.70:
        attribution = "likely_ai"
    elif confidence <= 0.30:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    content_id = str(uuid.uuid4())
    log_submission(
        content_id=content_id,
        creator_id=creator_id,
        attribution=attribution,
        confidence=confidence,
        llm_score=llm_score,
        stylometry_score=stylometry_score,
    )

    return jsonify(
        {
            "content_id": content_id,
            "attribution": attribution,
            "confidence": confidence,
            "label": f"Confidence this is AI-generated: {confidence:.0%}",
        }
    )


@app.route("/log", methods=["GET"])
def log():
    """Return recent audit log entries (newest first)."""
    return jsonify({"entries": get_log()})


# Run the dev server when this file is executed directly: `python app.py`
if __name__ == "__main__":
    app.run(debug=True)
