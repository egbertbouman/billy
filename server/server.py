#!/usr/bin/env python
import sys
import json
import urllib
import argparse
import cherrypy


class WebAPI(object):

    def __init__(self, dataset):
        self.dataset = dataset

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def tracks(self, namesearch=None, fuzzytags=None):
        return {'Test': 'Got namesearch=%s, fuzzytags=%s' % (namesearch, fuzzytags)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def recommend(self, description, tracks):
        return {'Test': 'Got description=%s, tracks=%s' % (description, tracks)}


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
