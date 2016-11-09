import time
import hashlib
import isodate
import logging

from util import *
from twisted.internet import task
from twisted.internet.defer import inlineCallbacks, returnValue
from autobahn.websocket import WebSocketServerProtocol, WebSocketServerFactory
from autobahn.resource import WebSocketResource

SEND_REGISTRATIONS = 10

YOUTUBE_STATS_URL = 'https://www.googleapis.com/youtube/v3/videos?part=contentDetails,statistics&id={id}&key={api_key}'
SOUNDCLOUD_STATS_URL = 'http://api.soundcloud.com/tracks/{id}?client_id={api_key}'


class BillyRadioProtocol(WebSocketServerProtocol):

    def onConnect(self, request):
        self.factory.join(request.peer, self)

    def onMessage(self, payload, isBinary):
        if not isBinary:
            json_payload = json.loads(payload)
            type = json_payload.get('type', None)
            if type == 'register' and 'name' in json_payload and 'radio_id' in json_payload:
                reactor.callLater(0, self.factory.register, self.peer, json_payload['name'], json_payload['radio_id'])
            elif type == 'unregister' and 'radio_id' in json_payload:
                self.factory.unregister(self.peer, json_payload['radio_id'])

    def connectionLost(self, reason):
        WebSocketServerProtocol.connectionLost(self, reason)
        self.factory.leave(self.peer)


class BillyRadioFactory(WebSocketServerFactory):

    def __init__(self, *args, **kwargs):
        self.database = kwargs.pop('database')
        self.config = kwargs.pop('config')

        WebSocketServerFactory.__init__(self, *args, **kwargs)

        self.logger = logging.getLogger(__name__)

        self.connections = {}
        self.stations = {}

        task.LoopingCall(self.fetch_playlist).start(300, now=False)
        task.LoopingCall(self.send_status).start(30)

    def join(self, peer, connection):
        self.connections[peer] = connection
        self.logger.debug('Peer %s joined', peer)

    def leave(self, peer):
        if peer in self.connections:
            del self.connections[peer]
            self.logger.debug('Peer %s left', peer)

        for radio_id in self.stations.keys():
            self.unregister(peer, radio_id)

    def send(self, message, peers=None):
        if peers is not None:
            connections = [self.connections[peer] for peer in peers if peer in self.connections]
        else:
            connections = self.connections.values()

        for connection in connections:
            connection.sendMessage(json.dumps(message))

    def send_status(self, radio_id=None, peers=None):
        stations = {radio_id: self.stations[radio_id]} if radio_id != None else self.stations
        for radio_id, station in stations.iteritems():
            if station.start_time > 0:
                self.send({'type': 'status',
                           'radio_id': radio_id,
                           'position': station.get_play_position()}, peers or station.get_peers())

    def send_data(self, radio_id, peers=None):
        station = self.stations[radio_id]
        self.send({'type': 'data',
                   'radio_id': radio_id,
                   'tracks': station.get_tracks(),
                   'registrations': station.get_registrations()}, peers)

    @inlineCallbacks
    def register(self, peer, user_name, radio_id):
        if radio_id not in self.stations:
            self.stations[radio_id] = BillyRadioStation(radio_id, self.config, self.database)
            yield self.stations[radio_id].update_tracks()

        station = self.stations[radio_id]
        peers = station.get_peers()
        station.register(peer, user_name)
        self.send_data(radio_id, [peer])
        self.send_status(radio_id, [peer])

        registration = station.get_registration(peer)
        message = {'type': 'registered',
                   'user_id': registration['user_id'],
                   'user_name': registration['user_name'],
                   'radio_id': radio_id,
                   'time': registration['time']}
        self.send(message, peers=peers)

    def unregister(self, peer, radio_id):
        station = self.stations[radio_id]
        peers = station.get_peers()
        registration = station.unregister(peer)
        if registration:
            message = {'type': 'unregistered',
                       'user_id': registration['user_id'],
                       'radio_id': radio_id}
            self.send(message, peers=peers)

    @inlineCallbacks
    def fetch_playlist(self):
        self.logger.info('Checking tracks')

        for radio_id, station in self.stations.iteritems():
            updated = yield station.update_tracks()

            if updated:
                # Notify everyone
                self.send_data(radio_id)
                self.send_status(radio_id)

            self.logger.info('Done checking tracks')


class BillyRadioStation(object):
    def __init__(self, radio_id, config, database):
        self.logger = logging.getLogger(__name__)

        self.start_time = 0
        self.radio_id = radio_id
        self.config = config
        self.database = database
        self.listeners = {}
        self.tracks = []

        radio = self.database.get_radio(self.radio_id)
        self.session_id = radio['session_id']
        self.playlist_name = radio['playlist_name']

    def register(self, peer, user_name):
        self.listeners[peer] = {'user_id': hashlib.sha1(str(peer)).hexdigest(),
                                'user_name': user_name,
                                'time': int(time.time())}

    def unregister(self, peer):
        return self.listeners.pop(peer, None)

    def get_registration(self, peer):
        return self.listeners.get(peer, None)

    def get_registrations(self, limit=SEND_REGISTRATIONS):
        return sorted(self.listeners.values(), key=lambda x: x['time'])[:limit]

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
    def update_tracks(self):
        self.logger.info('Checking tracks for radio %s', self.radio_id)

        session = self.database.get_session(self.session_id)
        tracks = session['playlists'][self.playlist_name]['tracks']
        # Only allow youtube tracks for now
        tracks = [track for track in tracks if track['link'].startswith('youtube:')]

        # Have the tracks changed?
        if [t['link'] for t in self.tracks] != [t['link'] for t in tracks]:
            # Update stats
            yt_api_key = self.config.get('sources', 'youtube_api_key')
            sc_api_key = self.config.get('sources', 'soundcloud_api_key')

            for track in tracks:
                url = YOUTUBE_STATS_URL.format(api_key=yt_api_key, id=track['link'][8:])
                response = yield get_request(url)
                response_dict = response.json
                track['duration'] = int(isodate.parse_duration(response_dict['items'][0]['contentDetails']['duration']).total_seconds())
                track['musicinfo'] = track.get('musicinfo', {})
                track['musicinfo']['playback_count'] = response_dict['items'][0]['statistics']['viewCount']
                track['musicinfo']['comment_count'] = response_dict['items'][0]['statistics']['commentCount']

            # Update tracks
            self.tracks = tracks
            self.start_time = int(time.time())

            returnValue(True)
        returnValue(False)

    def get_tracks(self):
        return self.tracks

    def get_peers(self):
        return self.listeners.keys()

