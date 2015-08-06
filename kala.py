#!/usr/bin/python

import os
import json

import bottle
from bottle_mongo import MongoPlugin


CORS_HEADERS = {
    'Authorization',
    'Content-Type',
    'Accept',
    'Origin',
    'User-Agent',
    'DNT',
    'Cache-Control',
    'X-Mx-ReqToken',
    'Keep-Alive',
    'X-Request',
    'X-Requested-With',
    'If-Modified-Since'
}


app = bottle.Bottle()
app.config.update({
    'mongodb.uri': 'mongodb://localhost:27017/',
    'mongodb.db': 'kala',
    'cors.enable': False
})

app.config.load_config(os.environ.get('KALA_CONFIGFILE', 'settings.ini'))

app.install(MongoPlugin(
    uri=os.environ.get('KALA_MONGODB_URI', app.config['mongodb.uri']),
    db=os.environ.get('KALA_MONGODB_DB', app.config['mongodb.db']),
    json_mongo=True))


if os.environ.get('KALA_CORS_ENABLE', app.config['cors.enable']):
    @app.hook('after_request')
    def add_cors_response_headers():
        if bottle.request.method in ('GET', 'OPTIONS'):
            bottle.response.set_header('Access-Control-Allow-Origin', '*')
            bottle.response.set_header('Access-Control-Allow-Headers', ','.join(CORS_HEADERS))


def _get_json(name):
    result = bottle.request.query.get(name)
    return json.loads(result) if result else None


@app.route('/<collection>')
def get(mongodb, collection):
    filter_ = _get_json('filter')
    projection = _get_json('projection')
    skip = int(bottle.request.query.get('skip', 0))
    limit = int(bottle.request.query.get('limit', 100))
    sort = _get_json('sort')
    # Turns a list of lists to a list of tuples.
    # This is necessary because JSON has no concept of "tuple" but pymongo
    # takes a list of tuples for the sort order.
    sort = [tuple(field) for field in sort] if sort else None

    cursor = mongodb[collection].find(
        filter=filter_, projection=projection, skip=skip, limit=limit,
        sort=sort
    )

    distinct = bottle.request.query.get('distinct')

    if distinct:
        return {'values': cursor.distinct(distinct)}

    return {'results': [document for document in cursor]}


def main():
    app.run()


if __name__ == '__main__':
    main()
