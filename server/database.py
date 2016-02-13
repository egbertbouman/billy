import os
import sys
import copy
import json
import time
import random
import binascii
import requests
import logging

from sources import *
from metadata import *
from pymongo import MongoClient
from bson.objectid import ObjectId
from pymongo.son_manipulator import SONManipulator
from twisted.internet.defer import inlineCallbacks
from twisted.internet import reactor, defer


class ObjectIdToString(SONManipulator):
    def transform_incoming(self, son, collection):
        son['_id'] = str(son.get('_id', ObjectId()))
        return son


class Database(object):

    def __init__(self, config, db_name):
        self.logger = logging.getLogger(__name__)

        self.config = config
        self.add_track_cb = None

        mongo_host = self.config.get('database', 'mongo_host')
        mongo_port = int(self.config.get('database', 'mongo_port'))
        self.client = MongoClient(mongo_host, mongo_port)
        self.db = self.client[db_name]
        self.db.add_son_manipulator(ObjectIdToString())
        self.db.tracks.ensure_index('link')

        self.info = {'num_tracks': {}, 'status': 'idle'}
        for track in self.db.tracks.find({}):
            link_type = track['link'].split(':')[0]
            self.info['num_tracks'][link_type] = self.info['num_tracks'].get(link_type, 0) + 1

        self.source_checker = None
        self.metadata_checker = None

    def start(self):
        self.source_checker = SourceChecker(self, self.config)
        self.metadata_checker = MetadataChecker(self, self.config)

    def set_track_callback(self, cb):
        self.add_track_cb = cb

    def add_source(self, source):
        # Add to database
        if not list(self.db.sources.find(source).limit(1)):
            id = self.db.sources.insert(source)

    def get_all_sources(self):
        return list(self.db.sources.find({}))

    def set_source_last_check(self, source_id, last_check):
        self.db.sources.update({'_id': source_id}, {'$set': {'last_check': last_check}})

    def get_all_sessions(self):
        return list(self.db.sessions.find({}))

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

    def add_tracks(self, tracks):
        existing_tracks = list(self.db.tracks.find({'link': {'$in': [track['link'] for track in tracks]}}, {'link': 1, 'sources': 1, '_id': 1}))
        existing_links = [track['link'] for track in existing_tracks]

        to_insert = [track for track in tracks if track['link'] not in existing_links]

        if to_insert:
            self.db.tracks.insert(to_insert)

            # Update db stats
            for track in to_insert:
                link_type = track['link'].split(':')[0]
                self.info['num_tracks'][link_type] = self.info['num_tracks'].get(link_type, 0) + 1

            if self.add_track_cb:
                self.add_track_cb(to_insert)

        # Merge sources
        for track in existing_tracks:
            for t in tracks:
                if t['link'] == track['link']:
                    self.db.tracks.update({'_id': track['_id']},{'$addToSet': {'sources': {'$each': t['sources']}}})
                    self.logger.debug('Merged sources for track %s', track['_id'])

        return len(to_insert)

    def add_track(self, track):
        if self.add_tracks([track]) == 1:
            return list(self.db.tracks.find({'link': track['link']}).limit(1))[0]
        return False

    def get_track(self, track_id):
        tracks = list(self.db.tracks.find({'_id': track_id}))
        return tracks[0] if tracks else None

    def get_tracks_from_source(self, source_id):
        return list(self.db.tracks.find({'sources': {'$elemMatch': {'$eq': source_id}}}))

    def get_random_tracks(self, limit=20):
        tracks = []
        for _ in range(limit):
            skip = int(random.random() * self.db.tracks.count())
            track = list(self.db.tracks.find().limit(-1).skip(skip))[0]
            tracks.append(track)
        return tracks

    def update_function_counter(self, track_id, function, delta):
        track = self.get_track(track_id)
        musicinfo = track.get('musicinfo', {})
        musicinfo['functions'] = musicinfo.get('functions', {})
        musicinfo['functions'][function] = musicinfo['functions'].get(function, 0) + delta
        track['musicinfo'] = musicinfo
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
        info['status'] = 'checking' if self.source_checker.checking else 'idle'

        return info
