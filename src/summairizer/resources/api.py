import threading
import time
import uuid

from flask import request
from flask_restful import Resource

from summairizer.cache import cache
from summairizer.llm import LlmResponseHandler, llm_client


class PromptApi(Resource):
    def get(self):
        return {"prompt": cache.get("prompt")}, 200

    def post(self):
        data = request.get_json()
        if "prompt" not in data:
            return {"message": "prompt not provided"}, 400

        prompt = str(data["prompt"])

        if not prompt:
            return {"message": "prompt is empty"}, 400

        try:
            llm_client.validate_prompt(prompt)
        except ValueError as err:
            return {"message": str(err)}, 400

        cache.set("prompt", prompt)
        return {"message": "prompt set"}, 200


class SummaryApi(Resource):
    def get(self, id):
        summary_data = cache.get(id)
        if not summary_data:
            resp = {"message": "not found"}
            return resp, 404

        resp = {"id": id}
        if summary_data["exception"]:
            resp["status"] = "error"
        elif summary_data["done"]:
            resp["status"] = "done"
        else:
            resp["status"] = "inprogress"

        if summary_data["content"]:
            resp["bytes_received"] = len(summary_data["content"].encode("utf-8"))

        if summary_data["done"]:
            resp["content"] = summary_data["content"]

        return resp, 200


def _handler_watcher(key: str, handler: LlmResponseHandler):
    while not handler.done:
        cache.set(key, handler.to_dict())
        time.sleep(0.1)

    # set it one final time once done to store final status
    cache.set(key, handler.to_dict())


class SummarizeApi(Resource):
    def post(self):
        data = request.get_json()
        if "document" not in data:
            return {"message": "document not provided"}, 400

        document = str(data["document"])

        key = str(uuid.uuid4())
        handler = llm_client.summarize(document, prompt=cache.get("prompt"))

        thread = threading.Thread(target=_handler_watcher, args=(key, handler))
        thread.daemon = True
        thread.start()

        return {"message": "generating summary", "id": key}, 202


class HealthCheckApi(Resource):
    def get(self):
        return {"message": "summAIrize is running!"}, 200
