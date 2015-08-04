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


def _filter_write(dictionary, whitelist):
    if whitelist is None:
        return dictionary
    filtered = dict((key, dictionary[key]) for key in whitelist if key in dictionary)
    return filtered if filtered else None


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
    # We use a whitelist write setting to filter what is allowed to be written to the collection.
    # If the whitelist write setting is empty, then nothing is filtered.
    # If no whitelist write setting in configuration, then we are unable to write.
    if 'whitelist.write' in app.config:
        json_ = _filter_write(bottle.request.json, app.config['whitelist.write'])
        if json_:
            mongodb[collection].insert(json_)


def main():
    app.run()


if 'whitelist.write' in app.config:
    app.config['whitelist.write'] = app.config['whitelist.write'].split(',') \
        if app.config['whitelist.write'] else None
if 'whitelist.read' in app.config:
    app.config['whitelist.read'] = app.config['whitelist.read'].split(',') \
        if app.config['whitelist.read'] else None

if __name__ == '__main__':
    main()
