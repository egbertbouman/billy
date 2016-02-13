import json
import logging
import dateutil.tz

from datetime import datetime
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.protocol import Protocol
from twisted.internet import reactor, defer


def ts_to_rfc3339(ts):
    dt = datetime.utcfromtimestamp(ts)
    return dt.isoformat("T") + "Z"


def datetime_to_ts(dt):
    epoch_dt = datetime(1970, 1, 1, tzinfo=dateutil.tz.tzoffset(None, 0))
    return int((dt - epoch_dt).total_seconds())


class Response(object):

    def __init__(self, status_code, content):
        self.status_code = status_code
        self.content = content

    @property
    def json(self):
        return json.loads(self.content)


class BodyReceiver(Protocol):

    def __init__(self, status_code, finished):
        self.status_code = status_code
        self.finished = finished
        self.data = ''

    def dataReceived(self, bytes):
        self.data += bytes

    def connectionLost(self, reason):
        self.finished.callback(Response(self.status_code, self.data))


def get_request(url, headers={}, timeout=30, ignore_errors=True):
    url = url.encode('utf-8') if isinstance(url, unicode) else url
    agent = Agent(reactor, connectTimeout=timeout)
    d = agent.request('GET', url, Headers(headers), None)

    def handle_response(response):
        d = defer.Deferred()
        response.deliverBody(BodyReceiver(response.code, d))
        return d

    def handle_error(error):
        logger = logging.getLogger(__name__)
        logger.info('Failed to GET %s', url)
        return Response(0, '')

    d.addCallback(handle_response)
    if ignore_errors:
        d.addErrback(handle_error)
    return d
