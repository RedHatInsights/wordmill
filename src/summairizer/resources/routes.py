from flask_restful import Api
from .api import SummarizeApi, SummaryApi, HealthCheckApi


def initialize_routes(api: Api):
    api.add_resource(SummarizeApi, "/summarize", methods=["POST"])
    api.add_resource(SummaryApi, "/summary/<id>", methods=["GET"])
    api.add_resource(HealthCheckApi, "/health", methods=["GET"])
