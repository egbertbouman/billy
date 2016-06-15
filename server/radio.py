import time
import hashlib
import isodate
import logging

from util import *
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks
from autobahn.websocket import WebSocketServerProtocol, WebSocketServerFactory
from autobahn.resource import WebSocketResource

SEND_REGISTRATIONS = 10
SEND_SUGGESTIONS = 10

YOUTUBE_STATS_URL = 'https://www.googleapis.com/youtube/v3/videos?part=contentDetails,statistics&id={id}&key={api_key}'
SOUNDCLOUD_STATS_URL = 'http://api.soundcloud.com/tracks/{id}?client_id={api_key}'


class BillyRadioProtocol(WebSocketServerProtocol):

    def onConnect(self, request):
        self.factory.join(request.peer, self)

    def onOpen(self):
        self.factory.send_data(self.peer)
        self.factory.send_status(self.peer)

    def onMessage(self, payload, isBinary):
        if not isBinary:
            json_payload = json.loads(payload)
            type = json_payload.get('type', None)
            if type == 'register' and 'name' in json_payload:
                self.factory.register(self.peer, json_payload['name'])
            elif type == 'suggest' and 'content' in json_payload:
                self.factory.suggest(self.peer, json_payload['content'])

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.leave(self.peer)


class BillyRadioFactory(WebSocketServerFactory):

    def __init__(self, *args, **kwargs):
        self.database = kwargs.pop('database')
        self.config = kwargs.pop('config')
        self.token = kwargs.pop('token')
        self.playlist_name = kwargs.pop('playlist_name')

        WebSocketServerFactory.__init__(self, *args, **kwargs)

        self.logger = logging.getLogger(__name__)
        self.connections = {}

        self.start_time = 0
        self.tracks = []
        self.registrations = {}
        self.suggestions = []

        task.LoopingCall(self.fetch_playlist).start(300)
        task.LoopingCall(self.send_status).start(30)

    def join(self, peer, connection):
        self.connections[peer] = connection
        self.logger.debug('Peer %s joined', peer)

    def leave(self, peer):
        if peer in self.connections:
            del self.connections[peer]
            self.logger.debug('Peer %s left', peer)
        self.unregister(peer)

    def send(self, message, peer=None):
        if peer is not None:
            connections = [self.connections[peer]] if peer in self.connections else []
        else:
            connections = self.connections.values()

        for connection in connections:
            connection.sendMessage(json.dumps(message))

    def send_status(self, peer=None):
        if self.start_time > 0:
            self.send({'type': 'status',
                       'position': self.get_play_position()}, peer)

    def send_data(self, peer=None):
        registrations = sorted(self.registrations.values(), key=lambda x: x['time'])[:SEND_REGISTRATIONS]
        suggestions = self.suggestions[:SEND_SUGGESTIONS]

        self.send({'type': 'data',
                   'tracks': self.tracks,
                   'registrations': registrations,
                   'suggestions': suggestions}, peer)

    def register(self, peer, name):
        self.registrations[peer] = {'user_id': hashlib.sha1(str(peer)).hexdigest(),
                                    'user_name': name,
                                    'time': int(time.time())}

        message = {'type': 'registered'}
        message.update(self.registrations[peer])
        self.send(message)

    def unregister(self, peer):
        registration = self.registrations.pop(peer, None)

        if registration:
            message = {'type': 'unregistered'}
            message['user_id'] = registration['user_id']
            self.send(message)

    def suggest(self, peer, content):
        registration = self.registrations.get(peer, None)

        if registration:
            self.suggestions.append({'user_id': registration['user_id'],
                                     'user_name': registration['user_name'],
                                     'content': content})

            message = {'type': 'suggested'}
            message.update(self.suggestions[-1])
            self.send(message)
        else:
            self.logger.warning('Ignoring suggestion from unregistred user')

    def get_play_position(self):
        play_position = int((time.time() - self.start_time))

        track_index = 0
        track = self.tracks[0]
        while play_position > track['duration']:
            play_position -= track['duration']
            track_index += 1
            track_index = track_index % len(self.tracks)
            track = self.tracks[track_index]

        return (track_index, play_position)

    @inlineCallbacks
    def fetch_playlist(self):
        self.logger.info('Checking tracks')
        session = self.database.get_session(self.token)
        tracks = session['playlists'][self.playlist_name]['tracks']

        # Have the tracks changed?
        if [t['link'] for t in self.tracks] != [t['link'] for t in tracks]:
            # Update stats
            yt_api_key = self.config.get('sources', 'youtube_api_key')
            sc_api_key = self.config.get('sources', 'soundcloud_api_key')

            for track in tracks:
                if track['link'].startswith('youtube:'):
                    url = YOUTUBE_STATS_URL.format(api_key=yt_api_key, id=track['link'][8:])
                    response = yield get_request(url)
                    response_dict = response.json
                    track['duration'] = int(isodate.parse_duration(response_dict['items'][0]['contentDetails']['duration']).total_seconds())
                    track['musicinfo'] = track.get('musicinfo', {})
                    track['musicinfo']['playback_count'] = response_dict['items'][0]['statistics']['viewCount']
                    track['musicinfo']['comment_count'] = response_dict['items'][0]['statistics']['commentCount']

                elif track['link'].startswith('soundcloud:'):
                    url = SOUNDCLOUD_STATS_URL.format(api_key=sc_api_key, id=track['link'][11:])
                    response = yield get_request(url)
                    response_dict = response.json
                    track['duration'] = response_dict['duration'] / 1000
                    track['musicinfo'] = track.get('musicinfo', {})
                    track['musicinfo']['playback_count'] = response_dict['playback_count']
                    track['musicinfo']['comment_count'] = response_dict['comment_count']
                    track['musicinfo']['favorite_count'] = response_dict['favoritings_count']

            # Update tracks
            self.tracks = tracks
            self.start_time = int(time.time())

            # Notify everyone
            self.send_data()
            self.send_status()

            self.logger.info('Tracks updated')

