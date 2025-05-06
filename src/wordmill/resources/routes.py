from flask_restful import Api

from .api import HealthCheckApi, PromptApi, SummarizeApi, SummaryApi


def initialize_routes(api: Api):
    api.add_resource(SummarizeApi, "/summarize", methods=["POST"])
    api.add_resource(SummaryApi, "/summary/<id>", methods=["GET"])
    api.add_resource(PromptApi, "/prompt", methods=["POST", "GET"])
    api.add_resource(HealthCheckApi, "/health", methods=["GET"])
