import json

from flask import request
from flask_restful import Resource
from llama_stack.apis.agents import Document
from .llm import llm_client


class SummairizeApi(Resource):
    def post(self):

        documents = request.get_json()

        if not isinstance(documents, list):
            return {"error": "The request body must be a list of documents"}, 400

        context_documents: list[Document] = [
            Document(content=json.dumps(document), mime_type="text/plain")
            for document in documents
        ]

        response = llm_client.summarize(context_documents)

        return {"summary": response}, 200

class HealthCheckApi(Resource):
    def get(self):
        return {"message": "Summairize is running!"}, 200
