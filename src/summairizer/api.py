import json

from flask import request
from flask_restful import Resource
from .llm import llm_client


class SummarizeApi(Resource):
    def post(self):
        document = request.get_json()

        handler = llm_client.summarize(document)

        while not handler.done:
            time.sleep(0.1)

        if handler.exception:
            return {"error": "error generating summary"}, 500

        return {"summary": handler.content}, 200


class HealthCheckApi(Resource):
    def get(self):
        return {"message": "Summairize is running!"}, 200
