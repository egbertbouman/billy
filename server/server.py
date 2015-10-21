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

from localsearch.localsearch import *
from pymongo import MongoClient

CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))


class API(object):

    jamendo_url = 'https://api.jamendo.com/v3.0/tracks/'
    client_id = '9d9f42e3'

    def __init__(self, dataset, waveforms, users):
        self.client = MongoClient('127.0.0.1', 27017)
        self.db = self.client['billy']

        self.index_dir = os.path.join(CURRENT_DIR, 'localsearch', 'index')

        self.dataset = dataset
        self.dataset_dict = {item['id']: item for item in dataset}
        self.waveforms = waveforms
        self.users = users

    def get_session(self, token):
        sessions = list(self.db.sessions.find({'_id': token}).limit(1))
        return sessions[0] if sessions else None

    def error(self, message, status_code):
        cherrypy.response.status = status_code
        return {'error': message}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def session(self, **kwargs):
        # Generate a token while avoiding collisions
        token = binascii.b2a_hex(os.urandom(20))
        while self.get_session(token) is not None:
            token = binascii.b2a_hex(os.urandom(20))

        self.db.sessions.insert({
            '_id': token,
            'playlists': {}
        })
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
                self.db.sessions.update({'_id': token}, {'$set': {'playlists': json_body}})
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
            if id in self.dataset_dict:
                return self.dataset_dict[id]
            return self.error('track does not exist', 404)

        results = search(self.index_dir, query)
        results.sort(key=lambda x: x['stats']['playlisted'], reverse=True)
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

        results = recommendForSongSet(playlist['tracks'], self.dataset, self.index_dir)
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
                cherrypy.lib.auth.digest_auth('server.py', self.users)
            except cherrypy.HTTPError, e:
                cherrypy.serving.response.headers['Access-Control-Expose-Headers'] = 'Www-Authenticate'
                raise e

            clicklog = list(self.db.clicklog.find({}, {'_id': False}).sort('_id', -1).limit(int(limit)))
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

            self.db.clicklog.insert(json_body)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def waveform(self, id, **kwargs):
        if id not in self.waveforms:
            return self.error('cannot find waveform', 404)

        return {'waveform': self.waveforms[id]}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def download(self, id, **kwargs):
        if id not in self.dataset_dict:
            return self.error('track does not exist', 404)

        raise cherrypy.HTTPRedirect('http://storage.jamendo.com/download/track/{id}/mp32/'.format(id=id))


class StaticContent(object):

    @cherrypy.expose
    def index(self, **args):
        raise cherrypy.HTTPRedirect("index.html")


def main(argv):
    parser = argparse.ArgumentParser(description='Billy API server')

    try:
        parser.add_argument('-p', '--port', help='Listen port', required=True)
        parser.add_argument('-d', '--data', help='JSON formatted dataset', required=True)
        parser.add_argument('-w', '--wave', help='JSON formatted waveforms', required=False)
        parser.add_argument('-s', '--static', help='Directory with static content (served from http://server/billy)', required=False)
        parser.add_argument('-u', '--users', help='Users that are allowed to view the clicklog (e.g. user1:pass1,user2:pass2)', required=False)
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    def CORS():
        cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
    cherrypy.tools.CORS = cherrypy.Tool('before_handler', CORS)

    dataset = json.loads(urllib.urlopen(args.data).read())
    waveforms = json.loads(urllib.urlopen(args.wave).read()) if args.wave else {}
    users = dict([user.split(':') for user in args.users.split(',')]) if args.users else {}
    api = API(dataset, waveforms, users)

    if args.static:
        html_dir = os.path.abspath(args.static)
        if not os.path.exists(html_dir):
            raise IOError('directory does not exist')
        config = {'/': {'tools.staticdir.root': os.path.abspath(args.static),
                        'tools.staticdir.on': True,
                        'tools.staticdir.dir': "",
                        'response.headers.connection': "close"}}
        app = cherrypy.tree.mount(StaticContent(), '/billy', config)

    config = {'/': {'tools.CORS.on': True,
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
