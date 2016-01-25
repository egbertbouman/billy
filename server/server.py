#!/usr/bin/env python
import os
import sys
import json
import time
import urllib
import argparse
import requests
import cherrypy
import binascii
import ConfigParser
import logging
import logging.config

from database import *
from search import *
from pymongo import MongoClient

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


class API(object):

    def __init__(self, database, search):
        self.database = database
        self.search = search

    def get_session(self, token):
        return self.database.get_session(token)

    def error(self, message, status_code):
        cherrypy.response.status = status_code
        return {'error': message}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def session(self, **kwargs):
        token = self.database.create_session()
        return {'token': token}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def playlists(self, token=None, search=None, **kwargs):
        if cherrypy.request.method == 'OPTIONS':
            cherrypy.response.headers['Connection'] = 'keep-alive'
            cherrypy.response.headers['Access-Control-Max-Age'] = '1440'
            cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Authorization,X-Auth-Token,Content-Type,Accept'
            return {}

        if bool(token) == bool(search):
            return self.error('please use either the token or the search param', 400)

        if token:
            session = self.get_session(token)

            if session is None:
                return self.error('cannot find session', 404)

            if cherrypy.request.method == 'GET':
                return session['playlists']

            elif cherrypy.request.method == 'POST':
                length = int(cherrypy.request.headers['Content-Length'])
                body = cherrypy.request.body.read(length)
                json_body = json.loads(body)
                self.database.update_session(token, json_body)
                return {}
        else:
            if cherrypy.request.method == 'GET':
                return self.error('not implemented yet', 404)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def tracks(self, query=None, id=None, **kwargs):
        if bool(query) == bool(id):
            return self.error('please use either the query or the id param', 400)

        if id:
            track = self.database.get_track(id)
            if track is None:
                return self.error('track does not exist', 404)
            return track

        results = self.search.search(query)
        results.sort(key=lambda x: x.get('stats', {}).get('playlisted', 0), reverse=True)
        return {'results': results}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def recommend(self, token, name, **kwargs):
        session = self.get_session(token)
        if session is None:
            return self.error('cannot find session', 404)

        playlists = session['playlists']
        playlist = playlists.get(name, None)
        if playlist is None:
            return self.error('cannot find playlist', 404)

        results = self.search.recommend(playlist['tracks'])

        if results is None:
            results = self.database.get_random_tracks(20)

        return {'results': results}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def clicklog(self, token=None, limit=0, **kwargs):
        if cherrypy.request.method == 'OPTIONS':
            cherrypy.response.headers['Connection'] = 'keep-alive'
            cherrypy.response.headers['Access-Control-Max-Age'] = '1440'
            cherrypy.response.headers['Access-Control-Allow-Headers'] = 'Authorization,X-Auth-Token,Content-Type,Accept'
            return {}

        elif cherrypy.request.method == 'GET':
            # Make sure the user is authorized (HTTP digest authentication)
            try:
                users = {user['name']: user['password'] for user in self.database.get_users()}
                cherrypy.lib.auth.digest_auth('server.py', users)
            except cherrypy.HTTPError, e:
                cherrypy.serving.response.headers['Access-Control-Expose-Headers'] = 'Www-Authenticate'
                raise e

            clicklog = list(self.database.get_clicklog(int(limit)))
            return clicklog

        elif cherrypy.request.method == 'POST':
            session = self.get_session(token)
            if session is None:
                return self.error('cannot find session', 404)

            length = int(cherrypy.request.headers['Content-Length'])
            body = cherrypy.request.body.read(length)
            json_body = json.loads(body)

            json_body['token'] = token
            json_body['user-agent'] = cherrypy.request.headers.get('User-Agent', '')
            json_body['ip'] = cherrypy.request.remote.ip
            json_body['time'] = int(time.time())

            self.database.add_clicklog(json_body)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def waveform(self, id, **kwargs):
        waveform = self.database.get_waveform(id)
        if waveform is None:
            return self.error('cannot find waveform', 404)

        return {'waveform': waveform['waveform']}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def info(self, **kwargs):
        return {'info': self.database.get_info()}


class StaticContent(object):

    @cherrypy.expose
    def index(self, **args):
        raise cherrypy.HTTPRedirect("index.html")


def main(argv):
    parser = argparse.ArgumentParser(description='Billy API server')

    try:
        parser.add_argument('-p', '--port', help='Listen port', required=True)
        parser.add_argument('-t', '--tracks', help='JSON formatted tracks to be imported into the database', required=False)
        parser.add_argument('-s', '--sources', help='JSON formatted sources to be imported into the database', required=False)
        parser.add_argument('-u', '--users', help='JSON formatted admin users to be imported into the database', required=False)
        parser.add_argument('-d', '--dir', help='Directory with static content (served from http://server/billy)', required=False)
        parser.add_argument('-i', '--index', help='Directory with the search index (default: data/index)', required=False)
        parser.add_argument('-n', '--dbname', help='Name of the MongoDB database (default: billy)', required=False)
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    def CORS():
        cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
    cherrypy.tools.CORS = cherrypy.Tool('before_handler', CORS)

    logging.config.fileConfig(os.path.join(CURRENT_DIR, 'logger.conf'))
    logger = logging.getLogger(__name__)

    config = ConfigParser.ConfigParser()
    config.read(os.path.join(CURRENT_DIR, 'billy.conf'))

    search = Search(args.index or (os.path.join(CURRENT_DIR, 'data', 'index')))
    db = Database(config, (args.dbname or 'billy'), search.index)

    # Import tracks
    if args.tracks:
        with open(args.tracks, 'rb') as fp:
            logger.info('Importing tracks')
            tracks = json.load(fp)
            for track in tracks:
                waveform = track.pop('waveform', None)

                track_id = db.add_track(track)

                if track_id and waveform is not None:
                    db.add_waveform(track_id, waveform)
            logger.info('Finished importing tracks')

    # Import sources
    if args.sources:
        with open(args.sources, 'rb') as fp:
            logger.info('Importing sources')
            sources = json.load(fp)
            for source in sources:
                track_id = db.add_source(source)
            logger.info('Finished importing sources')

    # Import users
    if args.users:
        with open(args.users, 'rb') as fp:
            logger.info('Importing users')
            users = json.load(fp)
            for user in users:
                db.add_user(user['name'], user['password'])
            logger.info('Finished importing users')

    db.start()
    api = API(db, search)

    if args.dir:
        html_dir = os.path.abspath(args.dir)
        if not os.path.exists(html_dir):
            raise IOError('directory does not exist')
        config = {'/': {'tools.staticdir.root': os.path.abspath(args.dir),
                        'tools.staticdir.on': True,
                        'tools.staticdir.dir': "",
                        'response.headers.connection': "close"}}
        app = cherrypy.tree.mount(StaticContent(), '/billy', config)

    config = {'/': {'log.screen': False,
                    'log.access_file': '',
                    'log.error_file': '',
                    'tools.CORS.on': True,
                    'tools.response_headers.on': True,
                    'tools.response_headers.headers': [('Content-Type', 'text/plain')]}}

    app = cherrypy.tree.mount(api, '/api', config)

    server = cherrypy._cpserver.Server()
    server.socket_port = int(args.port)
    server.max_request_body_size = 10485760
    server._socket_host = '0.0.0.0'
    server.thread_pool = 5
    server.subscribe()
    server.start()


if __name__ == "__main__":
    main(sys.argv[1:])
