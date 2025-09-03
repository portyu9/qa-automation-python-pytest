"""
A simple Flask server that serves mock posts data.

I use this server in my API and contract tests to avoid reliance on third‑party
services.  The endpoints mirror a subset of the JSONPlaceholder API.  Start
this server with ``python mock/server.py`` and access it at
http://localhost:5000.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any

from flask import Flask, jsonify, abort


def load_posts() -> List[Dict[str, Any]]:
    """Load posts from the adjacent data.json file.

    Returns:
        A list of dictionaries representing posts.
    """
    data_path = Path(__file__).with_name("data.json")
    with data_path.open() as f:
        return json.load(f)


def create_app() -> Flask:
    """Factory to create the Flask application.

    Using a factory allows tests to create an app without launching a server.
    """
    app = Flask(__name__)
    posts = load_posts()

    @app.route("/posts")
    def get_posts() -> Any:
        """Return all posts as JSON."""
        return jsonify(posts)

    @app.route("/posts/<int:post_id>")
    def get_post(post_id: int) -> Any:
        """Return a single post by id or 404 if not found."""
        for post in posts:
            if post["id"] == post_id:
                return jsonify(post)
        abort(404)

    @app.route("/health")
    def health() -> str:
        """Simple health check endpoint."""
        return "ok"

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover
    # Run the server only when executed as a script.
    app.run(host="0.0.0.0", port=5000)
    # Minor note: added for commit message consistency
