import json
import logging
import dateutil.tz

from datetime import datetime
from collections import OrderedDict
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.protocol import Protocol
from twisted.internet import reactor, defer


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


def parse_title(title):
    # Try to split the title into artist and name components
    if title.count(' - ') == 1:
        artist_name, track_name = title.split(' - ', 1)
        return artist_name, track_name
    return None


def ts_to_rfc3339(ts):
    dt = datetime.utcfromtimestamp(ts)
    return dt.isoformat("T") + "Z"


def datetime_to_ts(dt):
    epoch_dt = datetime(1970, 1, 1, tzinfo=dateutil.tz.tzoffset(None, 0))
    return int((dt - epoch_dt).total_seconds())

