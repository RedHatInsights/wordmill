import json
import uuid
import threading
import time

from flask import request, url_for
from flask_restful import Resource

from flask import current_app as app

from summairizer.llm import llm_client, LlmResponseHandler
from summairizer.cache import cache


class SummaryApi(Resource):
    def get(self, id):
        summary_data = cache.get(id)
        if not summary_data:
            return {"message": "not found"}, 404

        response = {"id": id}
        if summary_data["exception"]:
            response["status"] = "error"
        elif summary_data["done"]:
            response["status"] = "done"
        else:
            response["status"] = "inprogress"

        if summary_data["content"]:
            response["bytes_received"] = len(summary_data["content"].encode('utf-8'))

        if summary_data["done"]:
            response["content"] = summary_data["content"]

        return response, 200


def _handler_watcher(key: str, handler: LlmResponseHandler):
    while not handler.done:
        cache.set(key, handler.to_dict())
        time.sleep(0.1)

    # set it one final time once done
    cache.set(key, handler.to_dict())


class SummarizeApi(Resource):
    def post(self):
        document = request.get_json()

        key = str(uuid.uuid4())
        handler = llm_client.summarize(document)

        thread = threading.Thread(target=_handler_watcher, args=(key, handler))
        thread.daemon = True
        thread.start()

        return {"message": "generating summary", "id": key}, 202


class HealthCheckApi(Resource):
    def get(self):
        return {"message": "Summairize is running!"}, 200
