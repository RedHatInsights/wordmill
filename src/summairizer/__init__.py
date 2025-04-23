import logging

from flask import Flask
from flask_cors import CORS
from flask_restful import Api

from .cache import cache
from .resources.routes import initialize_routes

DEFAULT_PROMPT = (
    "You are a helpful assistant. Write a summary for the following document using "
    "markdown syntax:\n\n{document}"
)


def create_app():
    app = Flask("summairizer")

    app_logger = logging.getLogger("werkzeug")
    app_logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)

    app.config["CORS_HEADER"] = "Content-Type"
    CORS(app)

    cache.init_app(app)
    cache.set("prompt", DEFAULT_PROMPT)

    api = Api(app)
    initialize_routes(api)

    return app
