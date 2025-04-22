from flask_caching import Cache

# simple cache used for POC, move to something more robust later
cache = Cache(config={"CACHE_TYPE": "SimpleCache"})
