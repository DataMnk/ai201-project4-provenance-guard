"""
Provenance Guard — Flask API entry point.

M3 scope: skeleton routes only. Detection signals are NOT wired into /submit yet.
"""

import uuid

from flask import Flask, jsonify, request

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

    For now this returns hardcoded placeholder values — real detection comes in M4.
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

    # --- Placeholder response (will be replaced once signals are wired in) ---
    # content_id: unique ID for this submission (used later for appeals/audit log).
    # attribution: who wrote it — placeholder until real classification runs.
    # confidence: 0–1 probability the text is AI-generated (see planning.md).
    # label: human-readable transparency string (see planning.md).
    #
    # creator_id is accepted but not used yet — it will tie submissions to creators
    # when storage and appeals are added in M5.
    _ = creator_id  # intentionally unused for now

    return jsonify(
        {
            "content_id": str(uuid.uuid4()),
            "attribution": "uncertain",
            "confidence": 0.5,
            "label": (
                "We are uncertain about the origin of this content "
                "(Confidence: 50%). [placeholder]"
            ),
        }
    )


# Run the dev server when this file is executed directly: `python app.py`
if __name__ == "__main__":
    app.run(debug=True)
