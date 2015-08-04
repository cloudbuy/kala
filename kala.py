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


def _filter_write(mongodb, dictionary, filter_json):
    if filter_json is None:
        return dictionary
    staging = app.config.get('filter.staging', 'staging')
    object_id = mongodb[staging].insert(dictionary)
    cursor = mongodb[staging].find(filter=filter_json)
    documents = [document for document in cursor]
    mongodb[staging].remove({"_id":object_id}, "true")
    return documents


def _filter_read(dictionary, whitelist):
    if whitelist is None:
        return dictionary

    return dictionary


@app.route('/<collection>')
def get(mongodb, collection):
    filter_ = _get_json('filter')
    projection = _get_json('projection')
    skip = int(bottle.request.query.get('skip', 0))
    limit = int(bottle.request.query.get('limit', 100))
    sort = _get_json('sort')

    # We use a whitelist read setting to filter what is allowed to be read from the collection.
    # If the whitelist read setting is empty or non existent, then nothing is filtered.
    if 'whitelist.read' in app.config:
        filter_ = _filter_read(filter_)
        projection = _filter_read(projection)
        sort = _filter_read(sort)

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


@app.route('/<collection>', method='POST')
def post(mongodb, collection):
    # We insert the document into a staging collection and then apply a filter JSON.
    # If it returns a result, we can insert that into the actual collection.
    # If no filter JSON document is defined in the configuration setting, then write access is disabled.
    if 'filter.json' in app.config:
        json_ = bottle.request.json
        if _filter_write(mongodb, json_, app.config['filter.json']):
            mongodb[collection].insert(json_)


def main():
    app.run()


if 'filter.json' in app.config:
    with open(app.config['filter.json']) as data_file:
        app.config['filter.json'] = json.load(data_file)
if 'whitelist.read' in app.config:
    app.config['whitelist.read'] = app.config['whitelist.read'].split(',') \
        if app.config['whitelist.read'] else None

if __name__ == '__main__':
    main()
