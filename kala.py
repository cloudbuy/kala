#!/usr/bin/python

import os
import json

import bottle
from bottle_mongo import MongoPlugin


app = bottle.Bottle()
app.config.update({
    'mongodb.uri': 'mongodb://localhost:27017/',
    'mongodb.db': 'kala'
})

app.config.load_config(os.environ.get('KALA_CONFIGFILE', 'settings.ini'))

app.install(MongoPlugin(
    uri=os.environ.get('KALA_MONGODB_URI', app.config['mongodb.uri']),
    db=os.environ.get('KALA_MONGODB_DB', app.config['mongodb.db']),
    json_mongo=True))


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

    return {'results': [document for document in cursor]}


def main():
    app.run()


if __name__ == '__main__':
    main()
