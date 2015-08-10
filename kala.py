#!/usr/bin/python

import bson
import datetime
import os
import json
import uuid

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
    'cors.enable': False,
    'filter.staging': 'staging'
})

app.config.load_config(os.environ.get('KALA_CONFIGFILE', 'settings.ini'))

app.install(MongoPlugin(
    uri=os.environ.get('KALA_MONGODB_URI', app.config['mongodb.uri']),
    db=os.environ.get('KALA_MONGODB_DB', app.config['mongodb.db']),
    json_mongo=True))

if os.environ.get('KALA_CORS_ENABLE', app.config['cors.enable']):
    @app.hook('after_request')
    def add_cors_response_headers():
        if bottle.request.method in ('GET', 'OPTIONS', 'POST'):
            bottle.response.set_header('Access-Control-Allow-Origin', '*')
            bottle.response.set_header('Access-Control-Allow-Headers', ','.join(CORS_HEADERS))

if os.environ.get('KALA_FILTER_JSON'):
    app.config['filter.json'] = os.environ.get('KALA_FILTER_JSON')

if os.environ.get('KALA_FILTER_READ'):
    app.config['filter.read'] = os.environ.get('KALA_FILTER_READ')

app.config['filter.staging'] = os.environ.get('KALA_FILTER_STAGING', app.config['filter.staging'])

if 'filter.json' in app.config:
    with open(app.config['filter.json']) as data_file:
        app.config['filter.json'] = json.load(data_file)
if 'filter.read' in app.config:
    app.config['filter.read'] = app.config['filter.read'].split(',')


def _get_json(name):
    result = bottle.request.query.get(name)
    return json.loads(result) if result else None


def _filter_write(mongodb, document):
    # This will throw if setting isn't found in config.
    # Expected as your filter won't work without filter JSON path.
    if app.config['filter.json'] is None:
        return document
    object_id = mongodb[app.config['filter.staging']].insert(document)
    cursor = mongodb[app.config['filter.staging']].find(filter=app.config['filter.json'])
    # Delete from staging collection after cursor becomes a list, otherwise cursor will produce an empty list.
    documents = [doc for doc in cursor]
    mongodb[app.config['filter.staging']].remove({'_id': object_id}, 'true')
    return any(doc['_id'] == object_id for doc in documents)


def _filter_read(document):
    """This is used to filter the JSON object."""
    # This will throw if setting isn't found in config.
    # Expected as without setting you have nothing to filter.
    whitelist = app.config['filter.read']
    if whitelist is None:
        return document
    # When document is a dictionary, deletes any keys which are not in the whitelist.
    # Unless they are an operator, in which case we apply the filter to the value.
    if isinstance(document, dict):
        document = dict((key, value) for (key, value) in document.items() if key not in whitelist)
        for key in document.keys():
            if key.startswith('$'):
                _filter_read(document[key])
    # When document is a list, apply the filter on each item, thus returning a filtered list.
    elif isinstance(document, list):
        document = [item for item in document if _filter_read(item)]
    # When document is a tuple, return whether first element is in the whitelist.
    # This is used for sort
    elif isinstance(document, tuple):
        return document[0] in whitelist
    # This is used for projection.
    # Note that a JSON object can not contain null values.
    elif document is None:
        document = dict((key, '1') for key in whitelist)
    return document


def _filter_aggregate(list_):
    """This is used to filter the aggregate JSON

    Keyword arguments:
    list_ -- The JSON should be a list of dictionaries.
    """
    # The idea is to insert a $project at the start of pipeline that only contains fields in the whitelist.
    # Once filtered, the user can do whatever they want and never touch sensitive data.
    project = {'$project': dict((field, 1) for field in app.config['filter.read'])}
    list_ = [project] + list_
    return list_


def _convert_object_type(document, type_):
    """This is used to convert strings to the correct object type

    :param document:
    document -- The json
    type_ -- The target object type
    """
    if isinstance(document, dict):
        for k, v in document.items():
            document[k] = _convert_object_type(v, type_)
    if isinstance(document, list):
        document = [_convert_object_type(item, type_) for item in document]
    elif isinstance(document, (str, bytes)):
        try:
            if type_ == 'ISODate':
                return datetime.datetime.strptime(document, '%Y-%m-%dT%H:%M:%S.%fZ')
            elif type_ == 'UUID':
                return bson.Binary(uuid.UUID(document).bytes, 4)
        except ValueError:
            # We pass as we don't need to do anything with the value.
            pass
    return document


def _convert_object(document):
    """This is a wrapper for _convert_object_type()

    :param document:
    document -- This should either be a JSON document or a list of JSON documents.
    """
    document = _convert_object_type(document, 'ISODate')
    document = _convert_object_type(document, 'UUID')
    return document


@app.route('/aggregate/<collection>', method=['GET'])
def get_aggregate(mongodb, collection):
    pipeline = _get_json('pipeline')
    # Should this go in the _filter_aggregate?
    # It's also probably overkill, since $out must be the last item in the pipeline.
    pipeline = list(dictionary for dictionary in pipeline if "$out" not in dictionary) if pipeline else None
    if 'filter.read' in app.config:
        pipeline = _filter_aggregate(pipeline) if pipeline else None
    pipeline = _convert_object(pipeline) if pipeline else None
    limit = int(bottle.request.query.get('limit', 100))
    pipeline = pipeline + [{'$limit': limit}] if pipeline else None
    cursor = mongodb[collection].aggregate(pipeline=pipeline)
    return {'results': [document for document in cursor]}


@app.route('/<collection>', method=['GET'])
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

    filter_ = _convert_object(filter_) if filter_ else None

    # We use a whitelist read setting to filter what is allowed to be read from the collection.
    # If the whitelist read setting is empty or non existent, then nothing is filtered.
    if 'filter.read' in app.config:
        filter_ = _filter_read(filter_) if filter_ else None
        # Filter must be applied to projection, this is to prevent unrestricted reads.
        # If it is empty, we fill it with only whitelisted values.
        # Else we remove values which are not whitelisted.
        projection = _filter_read(projection)
        sort = _filter_read(sort) if sort else None

    cursor = mongodb[collection].find(
        filter=filter_, projection=projection, skip=skip, limit=limit,
        sort=sort
    )

    distinct = bottle.request.query.get('distinct')

    if distinct:
        return {'values': cursor.distinct(distinct)}

    return {'results': [document for document in cursor]}


@app.route('/<collection>', method=['POST'])
def post(mongodb, collection):
    # We insert the document into a staging collection and then apply a filter JSON.
    # If it returns a result, we can insert that into the actual collection.
    # If no filter JSON document is defined in the configuration setting, then write access is disabled. (It will throw)
    if 'filter.json' in app.config:
        # Need to convert BSON datatypes
        json_ = _convert_object(bottle.request.json)
        if _filter_write(mongodb, json_):
            object_id = mongodb[collection].insert(json_)
            return {'success': list(mongodb[collection].find({"_id": object_id}))}


def main():
    app.run()


if __name__ == '__main__':
    main()
