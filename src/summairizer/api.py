import json

from flask import request
from flask_restful import Resource
from .llm import llm_client


class SummairizeApi(Resource):
    def post(self):
        document = request.get_json()

        response = llm_client.summarize(document)

        return {"summary": response}, 200


class HealthCheckApi(Resource):
    def get(self):
        return {"message": "Summairize is running!"}, 200
