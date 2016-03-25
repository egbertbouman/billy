import os
import sys
import json
import time
import logging
import ConfigParser

from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks

# Ugly import hack
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
PARENT_DIR = os.path.realpath(os.path.join(CURRENT_DIR, os.pardir))
sys.path.append(PARENT_DIR)

from util import *
from search import *
from database import *

logging.basicConfig(stream=sys.stdout, level=logging.INFO)

config = ConfigParser.ConfigParser()
config.read(os.path.join(CURRENT_DIR, 'billy.conf'))

database = Database(config, sys.argv[1])
search = Search(database, config)
index_name = database.db.name

@inlineCallbacks
def rebuild_index():
    yield delete_request('http://{host}:{port}/{index}'.format(host=search.host,
                                                               port=search.port,
                                                               index=index_name))
    print 'Deleted index', index_name, 'from Elasticsearch server'

    chunk_size = 10000
    index = 0
    while True:
        tracks = list(database.db.tracks.find({}).skip(index * chunk_size).limit(chunk_size))
        if not tracks:
            break
        yield search.index(tracks)
        index += 1
    print 'Done'
    reactor.stop()

rebuild_index()
reactor.run()
