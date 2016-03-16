import time
import logging

from util import *
from twisted.internet import reactor, defer
from twisted.internet.defer import inlineCallbacks

METADATA_CHECK_INTERVAL = 24*3600


class MetadataChecker(object):

    def __init__(self, database, config):
        self.logger = logging.getLogger(__name__)

        self.database = database
        self.config = config
        self.checking = False
        self.lastfm = LastFm(config)

        self.check_loop()

    @inlineCallbacks
    def check_all(self):
        self.checking = True
        self.logger.info('Checking for metadata')

        sources = set()
        sessions = self.database.get_all_sessions()
        for session in sessions:
            playlists = session.get('playlists', {})
            for pl_name, pl_dict in playlists.iteritems():

                # Skip regular playlists
                if pl_dict.get('type', 'user') != 'identity':
                    continue

                for track_id in pl_dict['tracks']:
                    track = self.database.get_track(track_id)
                    if track:
                        sources |= set(track.get('sources', []))
                    else:
                        self.logger.error('Track %s is in a playlist, but not in the database', track_id)

        tracks = []
        for source in sources:
            tracks.extend(self.database.get_tracks_from_source(source))

        now = int(time.time())
        tracks = [track for track in tracks if now - track.get('musicinfo', {}).get('last_check', 0) >= METADATA_CHECK_INTERVAL]

        self.logger.info('Checking for metadata (%s sources / %s tracks)', len(sources), len(tracks))

        for track in tracks:
            yield self.check_track(track)

        self.logger.info('Finished checking for metadata')
        self.checking = False

    @inlineCallbacks
    def check_track(self, track, add_sources=False):
        last_check = int(time.time()) - track.get('musicinfo', {}).get('last_check', 0)

        if last_check >= METADATA_CHECK_INTERVAL:
            musicinfo = yield self.lastfm.fetch(track)
            got_musicinfo = bool(musicinfo)

            # Even if we didn't get any metadata, we still need to remember the last_check time
            musicinfo = musicinfo or {}
            musicinfo['last_check'] = int(time.time())
            track['musicinfo'] = musicinfo

            self.database.set_track_musicinfo(track, musicinfo)
            if got_musicinfo:
                self.logger.info('Updated metadata for track %s', track['_id'])

                if add_sources:
                    for artist in musicinfo.get('similar_artists', []):
                        source_id = self.database.add_source({"data": artist, "type": "artist", "site": "lastfm"})
                        if source_id is not None:
                            self.logger.info('Added Lastfm similar artist source for: %s', artist)

    @inlineCallbacks
    def check_loop(self):
        yield self.check_all()
        reactor.callLater(METADATA_CHECK_INTERVAL, self.check_loop)


class LastFm(object):

    URL = 'https://ws.audioscrobbler.com/2.0?method={method}&artist={artist}&track={track}&api_key={api_key}&format=json&limit=20'

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.similar_artists_cache = LimitedSizeDict(size_limit=5000)

    @inlineCallbacks
    def call_api(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, unicode):
                kwargs[k] = urllib.quote(v.encode('utf-8'))
        kwargs['api_key'] = self.config.get('sources', 'lastfm_api_key')

        response = yield get_request(self.URL.format(**kwargs))
        try:
            response_dict = response.json
        except ValueError, e:
            response_dict = {}
        defer.returnValue(response_dict)

    @inlineCallbacks
    def similar_artists(self, artist):
        if artist in self.similar_artists_cache:
            defer.returnValue(self.similar_artists_cache[artist])

        response_dict = yield self.call_api(method='artist.getSimilar', artist=artist, track='')

        artists = response_dict.get('similarartists', {}).get('artist', [])

        if artists:
            artists_names = [a['name'] for a in artists]
            self.similar_artists_cache[artist] = artists_names
            defer.returnValue(artists_names)

    @inlineCallbacks
    def search_track(self, track):
        response_dict = yield self.call_api(method='track.search', artist='', track=track['title'])

        track_list = response_dict.get('results', {}).get('trackmatches', {}).get('track', [])

        if track_list:
            defer.returnValue((track_list[0]['artist'], track_list[0]['name']))

    @inlineCallbacks
    def fetch(self, track):
        parsed_title = parse_title(track['title']) or (yield self.search_track(track))

        if parsed_title:
            artist_name, track_name = parsed_title

            response_dict = yield self.call_api(method='track.getInfo', artist=artist_name, track=track_name)

            now = str(int(time.time()))

            musicinfo = track.get('musicinfo', {})
            if 'track' not in response_dict:
                self.logger.info('Could not update metadata for track %s (reason: %s)', track['_id'], response_dict.get('message', 'unknown'))
            elif musicinfo and 'artist_name' in musicinfo:
                musicinfo['playcount'][now] = response_dict['track']['playcount']
                musicinfo['listeners'][now] = response_dict['track']['listeners']
            else:
                musicinfo.update({'artist_name': artist_name,
                                  'track_name': track_name,
                                  'tags': {'vartags': [t['name'] for t in response_dict['track']['toptags']['tag']]},
                                  'playcount': {now: response_dict['track']['playcount']},
                                  'listeners': {now: response_dict['track']['listeners']}})

                similar_artists = yield self.similar_artists(artist_name)
                if similar_artists:
                    musicinfo['similar_artists'] = similar_artists

            defer.returnValue(musicinfo)
