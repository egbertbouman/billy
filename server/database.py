import os
import sys
import copy
import json
import time
import random
import binascii
import threading
import requests
import logging

from sources import *
from pymongo import MongoClient
from bson.objectid import ObjectId
from pymongo.son_manipulator import SONManipulator

SOURCES_CHECK_INTERVAL = 24*3600


class ObjectIdToString(SONManipulator):
    def transform_incoming(self, son, collection):
        son['_id'] = str(son.get('_id', ObjectId()))
        return son


class Database(threading.Thread):

    def __init__(self, config, db_name):
        threading.Thread.__init__(self)

        self.logger = logging.getLogger(__name__)

        self.config = config
        self.add_track_cb = None

        mongo_host = self.config.get('database', 'mongo_host')
        mongo_port = int(self.config.get('database', 'mongo_port'))
        self.client = MongoClient(mongo_host, mongo_port)
        self.db = self.client[db_name]
        self.db.add_son_manipulator(ObjectIdToString())

        self.sources = {}
        self.load_sources()

        self.setDaemon(True)

        self.info = {'num_tracks': {}, 'status': 'idle'}
        for track in self.db.tracks.find({}):
            link_type = track['link'].split(':')[0]
            self.info['num_tracks'][link_type] = self.info['num_tracks'].get(link_type, 0) + 1

    def set_track_callback(self, cb):
        self.add_track_cb = cb

    def add_source(self, source):
        # Add to database
        if not list(self.db.sources.find(source).limit(1)):
            id = self.db.sources.insert(source)

            # Create source object
            self.sources[id] = self.create_source(source)

    def create_source(self, source_dict):
        if not 'site' in source_dict or not 'type' in source_dict:
            return

        last_check = source_dict.get('last_check', 0)
        if source_dict['site'] == 'youtube':
            return YoutubeSource(source_dict['type'], source_dict['data'], self.config, last_check)
        elif source_dict['type'] == 'rss':
            return RSSSource(source_dict['data'], self.config, last_check)

    def load_sources(self):
        sources = list(self.db.sources.find({}))

        for source_dict in sources:
            source = self.create_source(source_dict)
            if source is None:
                self.logger.error('Incorrect source found in database, skipping')
            else:
                self.sources[source_dict['_id']] = source

    def check_sources(self):
        count = 0
        now = int(time.time())

        self.info['status'] = 'checking'

        for source_id, source in self.sources.iteritems():
            if now - source.last_check < SOURCES_CHECK_INTERVAL:
                continue

            tracks = source.fetch(source.last_check)
            self.logger.info('Got %s track(s) for source %s', len(tracks), source)

            for track in tracks:
                track['source'] = source_id
                track_id = self.add_track(track)
                if track_id:
                    count += 1

            self.db.sources.update({'_id': source_id}, {'$set': {'last_check': source.last_check}})

        self.info['status'] = 'idle'

        return count

    def run(self):
        while True:
            self.logger.info('Checking sources')
            count = self.check_sources()
            self.logger.info('Finished checking sources. Got %d new track(s)', count)
            time.sleep(SOURCES_CHECK_INTERVAL)

    def get_session(self, token, resolve_tracks=True):
        sessions = list(self.db.sessions.find({'_id': token}).limit(1))
        session = sessions[0] if sessions else None
        if resolve_tracks and session and 'playlists' in session:
            for playlist in session['playlists'].values():
                tracks = []
                for track_id in playlist['tracks']:
                    tracks.append(self.get_track(track_id))
                playlist['tracks'] = tracks
        return session

    def create_session(self):
        # Generate a token while avoiding collisions
        token = binascii.b2a_hex(os.urandom(20))
        while self.get_session(token) is not None:
            token = binascii.b2a_hex(os.urandom(20))

        self.db.sessions.insert({'_id': token,
                                 'playlists': {}})
        return token

    def update_session(self, token, playlists):
        self.db.sessions.update({'_id': token}, {'$set': {'playlists': playlists}})

    def add_track(self, track):
        if not list(self.db.tracks.find({'link': track['link']}).limit(1)):
            # Try to split the title into artist and name components
            if track['title'].count(' - ') == 1:
                track['artist_name'], track['track_name'] = track['title'].split(' - ', 1)

            if 'musicinfo' not in track:
                # Get tags from last.fm
                # Disabled, for now
                if False and 'artist_name' in track:
                    params = {'method': 'track.gettoptags',
                              'artist': track['artist_name'],
                              'track': track['track_name'],
                              'api_key': self.config.get('sources', 'lastfm_api_key'),
                              'format': 'json',
                              'limit': 20}
                    response = requests.get('https://ws.audioscrobbler.com/2.0', params=params).json()
                    top_tags = [item['name'] for item in response.get('toptags', {}).get('tag', []) if item['count'] > 20]
                else:
                    top_tags = []
                track['musicinfo'] = {'tags': {'vartags': top_tags}}

            track_id = self.db.tracks.insert(track)
            if track_id:
                # Update db stats
                link_type = track['link'].split(':')[0]
                self.info['num_tracks'][link_type] = self.info['num_tracks'].get(link_type, 0) + 1

                track['_id'] = track_id
                if self.add_track_cb is not None:
                    self.add_track_cb(track)
                return track_id
        return False

    def get_track(self, track_id):
        tracks = list(self.db.tracks.find({'_id': track_id}))
        return tracks[0] if tracks else None

    def get_random_tracks(self, limit=20):
        tracks = []
        for _ in range(limit):
            skip = int(random.random() * self.db.tracks.count())
            track = list(self.db.tracks.find().limit(-1).skip(skip))[0]
            tracks.append(track)
        return tracks

    def update_function_counter(self, track_id, function, delta):
        track = self.get_track(track_id)
        musicinfo = track['musicinfo']
        musicinfo['functions'] = musicinfo.get('functions', {})
        musicinfo['functions'][function] = musicinfo['functions'].get(function, 0) + delta
        self.db.tracks.update({'_id': track_id}, {'$set': {'musicinfo': musicinfo}})

    def add_clicklog(self, clicklog):
        return self.db.clicklog.insert(clicklog)

    def get_clicklog(self, limit=0):
        return list(self.db.clicklog.find({}, {'_id': False}).sort('_id', -1).limit(int(limit)))

    def add_user(self, name, password):
        user = {'name': name,
                'password': password}

        if not list(self.db.users.find(user).limit(1)):
            return self.db.users.insert(user)
        return False

    def get_users(self):
        return list(self.db.users.find({}))

    def add_waveform(self, track_id, waveform_data):
        waveform = {'_id': track_id,
                    'waveform': waveform_data}

        if not list(self.db.waveforms.find({'_id': track_id})):
            return self.db.waveforms.insert(waveform)
        return False

    def get_waveform(self, track_id):
        waveforms = list(self.db.waveforms.find({'_id': track_id}))
        return waveforms[0] if waveforms else None

    def get_info(self):
        info = copy.deepcopy(self.info)

        info['num_sources'] = self.db.sources.count()
        info['num_sessions'] = self.db.sessions.count()

        return info
