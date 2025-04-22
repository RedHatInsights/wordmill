import logging

from flask import Flask
from flask_cors import CORS
from flask_restful import Api

from .resources.routes import initialize_routes
from .cache import cache


def create_app():
    app = Flask("summairizer")

    app_logger = logging.getLogger("werkzeug")
    app_logger.setLevel(logging.DEBUG)
    logging.basicConfig(level=logging.DEBUG)

    app.config["CORS_HEADER"] = "Content-Type"
    CORS(app)

    cache.init_app(app)

    api = Api(app)
    initialize_routes(api)

    return app
