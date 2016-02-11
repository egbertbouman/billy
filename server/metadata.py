import json
import time
import requests
import threading
import logging

from collections import OrderedDict

METADATA_CHECK_INTERVAL = 24*3600


def parse_title(title):
    # Try to split the title into artist and name components
    if title.count(' - ') == 1:
        artist_name, track_name = title.split(' - ', 1)
        return artist_name, track_name
    return None


# From: http://stackoverflow.com/questions/2437617/limiting-the-size-of-a-python-dictionary
class LimitedSizeDict(OrderedDict):
  def __init__(self, *args, **kwds):
    self.size_limit = kwds.pop("size_limit", None)
    OrderedDict.__init__(self, *args, **kwds)
    self._check_size_limit()

  def __setitem__(self, key, value):
    OrderedDict.__setitem__(self, key, value)
    self._check_size_limit()

  def _check_size_limit(self):
    if self.size_limit is not None:
      while len(self) > self.size_limit:
        self.popitem(last=False)


class MetadataChecker(threading.Thread):

    def __init__(self, database, config):
        threading.Thread.__init__(self)

        self.logger = logging.getLogger(__name__)

        self.database = database
        self.config = config
        self.checking = False
        self.lastfm = LastFm(config)

        self.setDaemon(True)

    def check(self):
        # TODO: move to database
        #tracks = [self.database.db.tracks.find_one({'_id': '56b88724ee43991360949ae3'})]
        #tracks = [self.database.db.tracks.find_one({'_id': '56b88b04ee4399179ed7c539'})]

        sources = set()
        sessions = self.database.get_all_sessions()
        for session in sessions:
            playlists = session.get('playlists', {})
            for pl_name, pl_dict in playlists.iteritems():
                for track_id in pl_dict['tracks']:
                    track = self.database.get_track(track_id)
                    sources |= set(track.get('sources', []))

        tracks = []
        for source in sources:
            tracks.extend(self.database.get_tracks_from_source(source))
        self.logger.info('Checking for metadata (%s sources / %s tracks)', len(sources), len(tracks))

        self.checking = True

        for track in tracks:
            musicinfo = self.lastfm.fetch(track)

            # TODO: move to database
            if musicinfo:
                self.database.db.tracks.update({'_id': track['_id']}, {'$set': {'musicinfo': musicinfo}})
                self.logger.info('Updated metadata for track %s', track['_id'])

        self.checking = False

    def run(self):
        while True:
            self.logger.info('Checking for metadata')
            self.check()
            self.logger.info('Finished checking for metadata')
            time.sleep(METADATA_CHECK_INTERVAL)


class LastFm(object):

    URL = 'https://ws.audioscrobbler.com/2.0?method={method}&artist={artist}&track={track}&api_key={api_key}&format=json&limit=20'

    def __init__(self, config):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.similar_artists_cache = LimitedSizeDict(size_limit=5000)

    def call_api(self, **kwargs):
        kwargs['api_key'] = self.config.get('sources', 'lastfm_api_key')
        response = requests.get(self.URL.format(**kwargs))
        try:
            response_dict = response.json()
        except:
            response_dict = {}
        return response_dict

    def similar_artists(self, artist):
        if artist in self.similar_artists_cache:
            return self.similar_artists_cache[artist]

        response_dict = self.call_api(method='artist.getSimilar', artist=artist.encode('utf-8'), track='')

        artists = response_dict.get('similarartists', {}).get('artist', [])

        if artists:
            artists_names = [a['name'] for a in artists]
            self.similar_artists_cache[artist] = artists_names
            return artists_names

    def search_track(self, track):
        response_dict = self.call_api(method='track.search', artist='', track=track['title'].encode('utf-8'))

        track_list = response_dict.get('results', {}).get('trackmatches', {}).get('track', [])

        if track_list:
            return track_list[0]['artist'], track_list[0]['name']

    def fetch(self, track):
        parsed_title = parse_title(track['title']) or self.search_track(track)
        if parsed_title:
            artist_name, track_name = parsed_title

            response_dict = self.call_api(method='track.getInfo', artist=artist_name.encode('utf-8'), track=track_name.encode('utf-8'))

            now = str(int(time.time()))

            musicinfo = track.get('musicinfo', {})
            if musicinfo and 'artist_name' in musicinfo:
                musicinfo['playcount'][now] = response_dict['track']['playcount']
                musicinfo['listeners'][now] = response_dict['track']['listeners']
            else:
                if 'track' in response_dict:
                    musicinfo.update({'artist_name': artist_name,
                                      'track_name': track_name,
                                      'tags': {'vartags': [t['name'] for t in response_dict['track']['toptags']['tag']]},
                                      'playcount': {now: response_dict['track']['playcount']},
                                      'listeners': {now: response_dict['track']['listeners']}})

                    similar_artists = self.similar_artists(artist_name)
                    if similar_artists:
                        musicinfo['similar_artists'] = similar_artists
                else:
                    self.logger.info('Could not update metadata for track %s', track['_id'])

            return musicinfo
