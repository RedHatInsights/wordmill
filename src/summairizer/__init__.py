from .api import SummairizeApi, HealthCheckApi
from flask import Flask
from flask_cors import CORS
from flask_restful import Api


def create_app():
    app = Flask("summairize")
    app.config["CORS_HEADER"] = "Content-Type"
    CORS(app)

    api = Api(app)
    _initialize_routes(api)

    return app


def _initialize_routes(api: Api):
    api.add_resource(SummairizeApi, "/", methods=["POST"])
    api.add_resource(HealthCheckApi, "/health", methods=["GET"])
