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


def _filter_write(mongodb, document):
    if app.config['filter.json'] is None:
        return document
    staging = app.config.get('filter.staging', 'staging')
    object_id = mongodb[staging].insert(document)
    cursor = mongodb[staging].find(filter=app.config['filter.json'])
    # Delete from staging collection after cursor becomes a list otherwise, cursor will produce an empty list.
    documents = [doc for doc in cursor]
    mongodb[staging].remove({"_id": object_id}, "true")
    return documents


def _filter_read(var):
    """This is used to filter the JSON object."""
    whitelist = app.config['filter.read']
    if whitelist is None:
        return var
    # When var is a dictionary, deletes any keys which are not in the whitelist.
    # Unless they are an operator, in which case we apply the filter to the value.
    if isinstance(var, dict):
        for key in list(var.keys()):
            if key.startswith('$'):
                _filter_read(var[key])
            elif key not in whitelist:
                del var[key]
    # When var is a list, apply the filter on each item, thus returning a filtered list.
    elif isinstance(var, list):
        var[:] = [item for item in var if _filter_read(item)]
    # When var is a tuple, return whether first element is in the whitelist
    elif isinstance(var, tuple):
        return var[0] in whitelist
    # This is used for projection.
    # Note that a JSON object can not contain null values.
    elif var is None:
        var = dict((key, '1') for key in whitelist)
    return var


def _filter_aggregate(list_):
    """This is used to filter the aggregate JSON

    Keyword arguments:
    list_ -- The JSON should be a list of dictionaries.
    """
    # The idea is to insert a $project at the start of pipeline that only contains fields in the whitelist.
    # If $projects exists at the start, then we strip any fields not in the whitelist.
    # Once filtered, the user can do whatever they want and never touch sensitive data.
    if '$project' in list_[0]:
        list_[0] = {'$project':_filter_read(list_[0]['$project'])}
    else:
        project = {'$project': dict((field,1) for field in app.config['filter.read'])}
        list_ = [project] + list_
    return list_


@app.route('/aggregate/<collection>')
def get_aggregate(mongodb, collection):
    pipeline = _get_json('pipeline')
    # Should this go in the _filter_aggregate?
    # It's also probably overkill, since $out must be the last item in the pipeline.
    pipeline = list(dictionary for dictionary in pipeline if "$out" not in dictionary) if pipeline else None
    if 'filter.read' in app.config:
        pipeline = _filter_aggregate(pipeline) if pipeline else None
    limit = int(bottle.request.query.get('limit', 100))
    pipeline = pipeline + [{'$limit': limit}]
    cursor = mongodb[collection].aggregate(pipeline=pipeline)
    return {'results': [document for document in cursor]}


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

    # We use a whitelist read setting to filter what is allowed to be read from the collection.
    # If the whitelist read setting is empty or non existent, then nothing is filtered.
    if 'filter.read' in app.config:
        filter_ = _filter_read(filter_) if filter_ else filter_
        # Filter must be applied to projection, this is to prevent unrestricted reads.
        # If it is empty, we fill it with only whitelisted values.
        # Else we remove values which are not whitelisted.
        projection = _filter_read(projection)
        sort = _filter_read(sort) if sort else sort

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
        if _filter_write(mongodb, json_):
            mongodb[collection].insert(json_)


def main():
    app.run()


if 'filter.json' in app.config:
    with open(app.config['filter.json']) as data_file:
        app.config['filter.json'] = json.load(data_file)
if 'filter.read' in app.config:
    app.config['filter.read'] = app.config['filter.read'].split(',') \
        if app.config['filter.read'] else None

if __name__ == '__main__':
    main()
