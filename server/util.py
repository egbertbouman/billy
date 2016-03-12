import json
import urllib
import urlparse
import logging
import cookielib
import dateutil.tz

from datetime import datetime
from StringIO import StringIO
from collections import OrderedDict
from twisted.web.client import Agent, CookieAgent, FileBodyProducer
from twisted.web.http_headers import Headers
from twisted.internet.protocol import Protocol
from twisted.internet import reactor, defer
from twisted.web._newclient import _WrapperException
from requests.cookies import create_cookie


class Response(object):

    def __init__(self, status_code, cookiejar, content):
        self.status_code = status_code
        self.cookiejar = cookiejar
        self.content = content

    @property
    def json(self):
        return json.loads(self.content)

    @property
    def cookies(self):
        return {cookie.name: cookie.value for cookie in self.cookiejar}


class BodyReceiver(Protocol):

    def __init__(self, status_code, cookiejar, finished):
        self.status_code = status_code
        self.cookiejar = cookiejar
        self.finished = finished
        self.data = ''

    def dataReceived(self, bytes):
        self.data += bytes

    def connectionLost(self, reason):
        self.finished.callback(Response(self.status_code, self.cookiejar, self.data))


def http_request(method, url, params={}, data=None, headers={}, cookies=None, timeout=30, ignore_errors=True):
    # Urlencode does not accept unicode, so convert to str first
    url = url.encode('utf-8') if isinstance(url, unicode) else url
    for k, v in params.items():
        params[k] = v.encode('utf-8') if isinstance(v, unicode) else v

    # Add any additional params to the url
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4]))
    query.update(params)
    url_parts[4] = urllib.urlencode(query, doseq=True)
    url = urlparse.urlunparse(url_parts)

    # Handle cookies
    if isinstance(cookies, cookielib.CookieJar):
        cookiejar = cookies
    else:
        cookiejar = cookielib.CookieJar()
        for name, value in (cookies or {}).iteritems():
            cookiejar.set_cookie(create_cookie(name=name, value=value))

    # Urlencode the data, if needed
    if isinstance(data, dict):
        data = urllib.urlencode(data)
        headers['Content-Type'] = 'application/x-www-form-urlencoded'

    agent = Agent(reactor, connectTimeout=timeout)
    cookie_agent = CookieAgent(agent, cookiejar)
    body = FileBodyProducer(StringIO(data)) if data else None
    d = cookie_agent.request(method, url, Headers({k: [v] for k, v in headers.iteritems()}), body)

    def handle_response(response, cookiejar):
        if 'audio/mpeg' in response.headers.getRawHeaders('content-type')[-1]:
            # Don't download any multimedia files
            raise Exception('reponse contains a multimedia file')
        d = defer.Deferred()
        response.deliverBody(BodyReceiver(response.code, cookiejar, d))
        return d

    def handle_error(error):
        if isinstance(error, _WrapperException):
            reason = ', '.join(error.reasons)
        else:
            reason = error.getErrorMessage()
        logger = logging.getLogger(__name__)
        logger.error('Failed to GET %s (reason: %s)', url, reason)
        return Response(0, cookielib.CookieJar(), '')

    d.addCallback(handle_response, cookiejar)
    if ignore_errors:
        d.addErrback(handle_error)
    return d


def get_request(url, **kwargs):
    return  http_request('GET', url, **kwargs)


def post_request(url, **kwargs):
    return  http_request('POST', url, **kwargs)


def put_request(url, **kwargs):
    return  http_request('PUT', url, **kwargs)


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


def build_bool_query(bool_type, match_dict, nested_path=None):
    query = {'query': {'bool': {bool_type: []}}}

    for key, value in match_dict.iteritems():
        query['query']['bool'][bool_type].append({'match': {key: value}})

    if nested_path:
        query = {'nested': query}
        query['nested']['path'] = nested_path

    return query


def build_simple_query(query, fields=['_all']):
    return {'query': {'simple_query_string': {'query': query, 'fields': fields}}}


def build_query(query, field='_all'):
    return {'query': {'query_string': {'query': query, 'default_field': field}}}

