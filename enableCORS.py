import bottle;
from bottle import response;

# Code from stackoverflow.com
# Question at http://stackoverflow.com/questions/17262170/bottle-py-enabling-cors-for-jquery-ajax-requests
# Thanks to asker http://stackoverflow.com/users/552894/joern
# Thanks to answerer http://stackoverflow.com/users/593047/ron-rothman

class EnableCors(object):
    name = 'enable_cors'
    api = 2

    def apply(self, fn, context):
        def _enable_cors(*args, **kwargs):
            # set CORS headers
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

            if bottle.request.method != 'OPTIONS':
                # actual request; reply with the actual response
                return fn(*args, **kwargs)

        return _enable_cors
