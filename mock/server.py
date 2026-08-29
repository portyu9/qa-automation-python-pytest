"""Deterministic local API and UI fixture used by automated tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify


def load_posts() -> list[dict[str, Any]]:
    """Load version-controlled post fixtures from the adjacent data file."""
    data_path = Path(__file__).with_name("data.json")
    with data_path.open(encoding="utf-8") as file_handle:
        return json.load(file_handle)


def create_app() -> Flask:
    """Create the local test application without opening a network listener."""
    app = Flask(__name__)
    posts = load_posts()

    @app.get("/posts")
    def get_posts() -> Any:
        """Return all deterministic post fixtures."""
        return jsonify(posts)

    @app.get("/posts/<int:post_id>")
    def get_post(post_id: int) -> Any:
        """Return a post by identifier or an explicit 404 when absent."""
        for post in posts:
            if post["id"] == post_id:
                return jsonify(post)
        abort(404)

    @app.get("/health")
    def health() -> str:
        """Expose a lightweight readiness endpoint for process orchestration."""
        return "ok"

    @app.get("/ui")
    def ui_home() -> str:
        """Serve a stable browser fixture with test-specific semantic hooks."""
        return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Quality Engineering Fixture</title>
  </head>
  <body>
    <main>
      <h1 data-testid="page-title">Quality Engineering Fixture</h1>
      <p>Deterministic UI content served by the repository-local test application.</p>
      <a data-testid="details-link" href="/ui/details">Open fixture details</a>
    </main>
  </body>
</html>"""

    @app.get("/ui/details")
    def ui_details() -> str:
        """Serve the navigation destination used by the browser workflow test."""
        return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Fixture Details</title>
  </head>
  <body>
    <main>
      <h1 data-testid="details-title">Fixture Details</h1>
      <p>The browser reached the expected deterministic destination.</p>
    </main>
  </body>
</html>"""

    return app


app = create_app()

if __name__ == "__main__":  # pragma: no cover
    app.run(host="127.0.0.1", port=5000)
