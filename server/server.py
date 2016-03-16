#!/usr/bin/env python
import os
import sys
import json
import time
import argparse
import ConfigParser
import logging
import logging.config

from twisted.web import server
from twisted.web.server import Site
from twisted.web.resource import Resource
from twisted.internet import defer, reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.static import File

from search import Search
from database import Database
from pymongo import MongoClient

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


def json_out(f):
    def wrap(*args, **kwargs):
        self, request = args[:2]
        self.add_response_headers(request)
        response = f(*args, **kwargs)
        return json.dumps(response)
    return wrap


class APIResource(Resource):

    def __init__(self, *args):
        Resource.__init__(self)
        self.putChild('session', SessionHandler(*args))
        self.putChild('playlists', PlaylistsHandler(*args))
        self.putChild('tracks', TracksHandler(*args))
        self.putChild('recommend', RecommendHandler(*args))
        self.putChild('clicklog', ClicklogHandler(*args))
        self.putChild('waveform', WaveformHandler(*args))
        self.putChild('info', InfoHandler(*args))


class BaseHandler(Resource):
    isLeaf = True

    def __init__(self, config, database, search):
        Resource.__init__(self)
        self.config = config
        self.database = database
        self.search = search

    def error(self, request, message, status_code):
        request.setResponseCode(status_code)
        return {'error': message}

    def add_response_headers(self, request):
        request.responseHeaders.addRawHeader('content-type', 'application/json')
        # CORS headers
        request.responseHeaders.addRawHeader('Access-Control-Allow-Origin', '*')
        request.responseHeaders.addRawHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        request.responseHeaders.addRawHeader("Access-Control-Allow-Headers", "Authorization,X-Auth-Token,Content-Type,Accept")

    @json_out
    def render_OPTIONS(self, request):
        return {}

    def render_GET(self, request):
        def finish_req(res, request):
            request.write(json.dumps(res))
            if not request.finished:
                request.finish()

        self.add_response_headers(request)
        d = self._process_GET(request)
        d.addCallback(finish_req, request)
        return server.NOT_DONE_YET

    @inlineCallbacks
    def _process_GET(self, request):
        defer.returnValue(self.error(request, 'Method not allowed', 405))

    def render_POST(self, request):
        def finish_req(res, request):
            request.write(json.dumps(res))
            if not request.finished:
                request.finish()

        self.add_response_headers(request)
        d = self._process_POST(request)
        d.addCallback(finish_req, request)
        return server.NOT_DONE_YET

    @inlineCallbacks
    def _process_POST(self, request):
        defer.returnValue(self.error(request, 'Method not allowed', 405))


class SessionHandler(BaseHandler):

    @json_out
    def render_GET(self, request):
        token = self.database.create_session()
        return {'token': token}


class PlaylistsHandler(BaseHandler):

    @json_out
    def render_GET(self, request):
        token = request.args['token'][0] if 'token' in request.args else None
        if token:
            session = self.database.get_session(token)

            if session is None:
                return self.error(request, 'cannot find session', 404)

            playlists = session['playlists']
            return session['playlists']

    @json_out
    def render_POST(self, request):
        token = request.args['token'][0] if 'token' in request.args else None
        session = self.database.get_session(token)
        if session is None:
            return self.error(request, 'cannot find session', 404)

        body = request.content.read()

        playlists_new = json.loads(body)
        tracks_new = set((p['name'], track_id) for p in playlists_new.values() for track_id in p['tracks'])

        playlists_old = session['playlists']
        tracks_old = set((p['name'], t['_id']) for p in playlists_old.values() for t in p['tracks'])

        tracks_added = tracks_new - tracks_old
        tracks_removed = tracks_old - tracks_new

        check_metadata = False
        for playlist_name, track_id in tracks_added:
            for function in playlists_new[playlist_name].get('functions', []):
                self.database.update_function_counter(track_id, function, 1)

            # Check metadata for the new tracks in the identity playlist
            if  playlists_new[playlist_name].get('type', 'user') == 'identity':
                track = self.database.get_track(track_id)
                self.database.metadata_checker.check_track(track, add_sources=True)
                check_metadata = True

        for playlist_name, track_id in tracks_removed:
            for function in playlists_old[playlist_name].get('functions', []):
                self.database.update_function_counter(track_id, function, -1)

        self.database.update_session(token, playlists_new)

        # Run the metadata checker (needs to be called after update_session)
        if check_metadata and not self.database.metadata_checker.checking:
            self.database.metadata_checker.check_all()

        return {}


class TracksHandler(BaseHandler):

    @inlineCallbacks
    def _process_GET(self, request):
        query = request.args['query'][0] if 'query' in request.args else None
        id = request.args['id'][0] if 'id' in request.args else None
        offset = request.args['offset'][0] if 'offset' in request.args else 0

        if bool(query) == bool(id):
            defer.returnValue(self.error(request, 'please use either the query or the id param', 400))

        if id:
            track = self.database.get_track(id)
            if track is None:
                defer.returnValue(self.error(request, 'track does not exist', 404))
            defer.returnValue(track)

        results = yield self.search.search(query)
        results.sort(key=lambda x: x.get('stats', {}).get('playlisted', 0), reverse=True)

        offset = int(offset)
        page_size = int(self.config.get('api', 'page_size'))

        if offset > len(results):
            defer.returnValue(self.error(request, 'offset is larger then result-set', 404))
        else:
            defer.returnValue({'offset': offset,
                               'page_size': page_size,
                               'total': len(results),
                               'results': results[offset:offset+page_size]})


class RecommendHandler(BaseHandler):

    @inlineCallbacks
    def _process_GET(self, request):
        token = request.args['token'][0] if 'token' in request.args else None
        name = request.args['name'][0] if 'name' in request.args else None
        offset = request.args['offset'][0] if 'offset' in request.args else 0

        session = self.database.get_session(token)
        if session is None:
            defer.returnValue(self.error(request, 'cannot find session', 404))

        playlists = session['playlists']

        ident_playlist = None
        for p in playlists.itervalues():
            if p.get('type', 'user') == 'identity':
                ident_playlist = p

        page_size = int(self.config.get('api', 'page_size'))

        # Get the recommendations
        results = None
        if ident_playlist:
            offset = int(offset)
            results = yield self.search.recommend(ident_playlist)
        if results is None:
            offset = 0
            results = self.database.get_random_tracks(page_size)

        # Return the recommendations
        if offset > len(results):
            response = self.error(request, 'offset is larger then result-set', 404)
        else:
            response = {'offset': offset,
                        'page_size': page_size,
                        'total': len(results),
                        'results': results[offset:offset+page_size]}

        defer.returnValue(response)


class ClicklogHandler(BaseHandler):

    @json_out
    def render_GET(self, request):
        limit = request.args['limit'][0] if 'limit' in request.args else 0

        # Make sure the user is authorized (HTTP basic authentication)
        authorized = any([user['name'] == request.getUser() and user['password'] == request.getPassword() for user in self.database.get_users()])
        if not authorized:
            request.responseHeaders.addRawHeader('WWW-Authenticate', 'Basic realm="Billy"')
            return self.error(request, 'authentication failed', 401)

        clicklog = list(self.database.get_clicklog(int(limit)))
        return clicklog

    @json_out
    def render_POST(self, request):
        token = request.args['token'][0] if 'token' in request.args else None
        session = self.database.get_session(token)
        if session is None:
            return self.error(request, 'cannot find session', 404)

        body = request.content.read()
        json_body = json.loads(body)

        json_body['token'] = token
        json_body['user-agent'] = request.getAllHeaders().get('user-agent', '')
        json_body['ip'] = request.getClientIP()
        json_body['time'] = int(time.time())

        self.database.add_clicklog(json_body)


class WaveformHandler(BaseHandler):

    @json_out
    def render_GET(self, request):
        id = request.args['id'][0] if 'id' in request.args else None
        waveform = self.database.get_waveform(id)
        if waveform is None:
            return self.error(request, 'cannot find waveform', 404)

        return {'waveform': waveform['waveform']}


class InfoHandler(BaseHandler):

    @json_out
    def render_GET(self, request):
        return {'info': self.database.get_info()}


def main(argv):
    parser = argparse.ArgumentParser(description='Billy API server')

    try:
        parser.add_argument('-p', '--port', help='Listen port', required=True)
        parser.add_argument('-t', '--tracks', help='JSON formatted tracks to be imported into the database', required=False)
        parser.add_argument('-s', '--sources', help='JSON formatted sources to be imported into the database', required=False)
        parser.add_argument('-u', '--users', help='JSON formatted admin users to be imported into the database', required=False)
        parser.add_argument('-d', '--dir', help='Directory with static content (served from http://server/billy)', required=False)
        parser.add_argument('-n', '--dbname', help='Name of the MongoDB database (default: billy)', required=False)
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    logging.config.fileConfig(os.path.join(CURRENT_DIR, 'logger.conf'))
    logger = logging.getLogger(__name__)

    config = ConfigParser.ConfigParser()
    config.read(os.path.join(CURRENT_DIR, 'billy.conf'))

    database = Database(config, (args.dbname or 'billy'))
    search = Search(database, config)
    database.set_track_callbacks(search.index, search.update)

    # Import tracks
    if args.tracks:
        with open(args.tracks, 'rb') as fp:
            logger.info('Importing tracks')
            tracks = json.load(fp)
            for track in tracks:
                waveform = track.pop('waveform', None)

                track_id = database.add_track(track)

                if track_id and waveform is not None:
                    database.add_waveform(track_id, waveform)
            logger.info('Finished importing tracks')

    # Import sources
    if args.sources:
        with open(args.sources, 'rb') as fp:
            logger.info('Importing sources')
            sources = json.load(fp)
            for source in sources:
                track_id = database.add_source(source)
            logger.info('Finished importing sources')

    # Import users
    if args.users:
        with open(args.users, 'rb') as fp:
            logger.info('Importing users')
            users = json.load(fp)
            for user in users:
                database.add_user(user['name'], user['password'])
            logger.info('Finished importing users')

    database.start_checking()
    root = Resource()

    if args.dir:
        html_dir = os.path.abspath(args.dir)
        if not os.path.exists(html_dir):
            raise IOError('directory does not exist')
        root.putChild('billy', File(html_dir))

    root.putChild('api', APIResource(config, database, search))

    factory = Site(root)
    reactor.listenTCP(int(args.port), factory)
    reactor.run()


if __name__ == "__main__":
    main(sys.argv[1:])
