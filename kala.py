#!/usr/bin/python

import json

import bottle
from bottle_mongo import MongoPlugin


app = bottle.Bottle()

app.config.load_config('settings.ini')

bottle.install(MongoPlugin(
    uri=app.config('mongodb.uri'),
    db=app.config('mongodb.db'),
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

    cursor = mongodb[collection].find(
        filter=filter_, projection=projection, skip=skip, limit=limit,
        sort=sort
    )

    return {'results': [document for document in cursor]}


def main():
    app.run()


if __name__ == '__main__':
    main()
