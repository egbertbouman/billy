#!/usr/bin/env python
import sys
import json
import urllib
import argparse
import requests
import cherrypy


class WebAPI(object):

    jamendo_url = 'https://api.jamendo.com/v3.0/tracks/'
    client_id = '9d9f42e3'

    def __init__(self, dataset):
        self.dataset = dataset
        self.dataset_dict = {item['id']: item for item in dataset}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def tracks(self, namesearch=None, fuzzytags=None):
        params = {'client_id': self.client_id,
                  'limit': 200,
                  'include': 'musicinfo',
                  'groupby': 'artist_id'}

        if namesearch:
            params['namesearch'] = namesearch
        elif fuzzytags:
            params['fuzzytags'] = fuzzytags
        else:
            return {'Error': 'Please provide a namesearch or fuzzytags value'}

        response = requests.get(self.jamendo_url, params=params).json()
        if 'headers' in response and response['headers'].get('status', 'error') == 'success':
            response['results'] = [item for item in response['results'] if item['id'] in self.dataset_dict]
            response['headers']['results_count'] = len(response['results'])
        return response

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def recommend(self, description, tracks):
        genres = set()
        for track_id in json.loads(tracks):
            track_id = unicode(track_id)
            if track_id in self.dataset_dict:
                track = self.dataset_dict[track_id]
                for genre in track['musicinfo']['tags'].get('genres', []):
                    genres.add(genre)

        params = {'client_id': self.client_id,
                  'limit': 200,
                  'include': 'musicinfo',
                  'tags': list(genres)}

        response = requests.get(self.jamendo_url, params=params).json()
        if 'headers' in response and response['headers'].get('status', 'error') == 'success':
            response['results'] = [item for item in response['results'] if item['id'] in self.dataset_dict and item['id'] not in tracks]
            response['headers']['results_count'] = len(response['results'])
        return response


def main(argv):
    parser = argparse.ArgumentParser(description='Serve a Jamendo-like web API')

    try:
        parser.add_argument('-p', '--port', help='Listen port', required=True)
        parser.add_argument('-d', '--data', help='JSON formatted dataset', required=True)
        parser.add_help = True
        args = parser.parse_args(sys.argv[1:])

    except argparse.ArgumentError:
        parser.print_help()
        sys.exit(2)

    def CORS():
        cherrypy.response.headers["Access-Control-Allow-Origin"] = "*"
    cherrypy.tools.CORS = cherrypy.Tool('before_handler', CORS)

    dataset = json.loads(urllib.urlopen(args.data).read())
    api = WebAPI(dataset)

    config = {'/': {'server.thread_pool': 1,
                    'tools.CORS.on': True,
                    'tools.sessions.on': True,
                    'tools.response_headers.on': True,
                    'tools.response_headers.headers': [('Content-Type', 'text/plain')]}}
    cherrypy.config.update({'server.socket_host': '0.0.0.0',
                            'server.socket_port': int(args.port)})
    cherrypy.quickstart(api, '/', config)


if __name__ == "__main__":
    main(sys.argv[1:])
