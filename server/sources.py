import re
import json
import time
import urllib
import datetime
import requests
import lxml.html
import feedparser
import dateutil.tz

from datetime import datetime
from dateutil.parser import parse
from lxml.cssselect import CSSSelector
from lxml.etree import XMLSyntaxError
from urlparse import urlparse, parse_qs

feedparser._HTMLSanitizer.acceptable_elements.update(['iframe'])

YOUTUBE_CHANNEL_URL = 'https://www.googleapis.com/youtube/v3/search?key={api_key}&channelId={id}&part=snippet&order=date&type=video&publishedBefore={before}&publishedAfter={after}&pageToken={token}&maxResults=50'
YOUTUBE_PLAYLIST_URL = 'https://www.googleapis.com/youtube/v3/playlistItems?key={api_key}&playlistId={id}&part=snippet&pageToken={token}&maxResults=50'
SOUNDCLOUD_RESOLVE_URL = 'https://api.soundcloud.com/resolve.json?url={url}&client_id={api_key}'


def ts_to_rfc3339(ts):
    dt = datetime.utcfromtimestamp(ts)
    return dt.isoformat("T") + "Z"


def datetime_to_ts(dt):
    epoch_dt = datetime(1970, 1, 1, tzinfo=dateutil.tz.tzoffset(None, 0))
    return int((dt - epoch_dt).total_seconds())


def extract_youtube_id(url):
    o = urlparse(url)
    query = parse_qs(o.query)
    if 'v' in query:
        return query['v']
    else:
        path_split = o.path.split('/')
        if 'v' in path_split or 'e' in path_split or 'embed' in path_split:
            return o.path.split('/')[-1]


def extract_soundcloud_id(url):
    urls = [url, urllib.unquote(url)]
    for url in urls:
        index = url.find('/tracks/')
        if index > 0:
            return re.findall(r'\d+', url[index + 8:])[0]


def request_soundcloud_id(url, api_key):
    response = requests.get(SOUNDCLOUD_RESOLVE_URL.format(url=url, api_key=api_key))
    if response.status_code == 200:
        try:
            response_dict = response.json()
        except ValueError:
            print 'Error: could not get soundcloud id for:', url
        else:
            if response_dict.get('kind', '') == 'track':
                return response_dict['id']


class RSSSource(object):

    def __init__(self, url, config, last_check=0):
        self.url = url
        self.config = config
        self.last_check = last_check

    def fetch(self, since=0):
        results = []

        feed = feedparser.parse(self.url)

        for entry in feed.get('entries', []):
            epoch_time = int(time.mktime(entry['published_parsed'])) if 'published_parsed' in entry else -1
            if epoch_time < since:
                continue

            links = [link['href'] for link in entry['links'] if link['type'] == 'audio/mpeg']

            # Extract Youtube/Soundcloud id's from iframes in description
            try:
                tree = lxml.html.fromstring(entry['description'])
            except (XMLSyntaxError, KeyError):
                tree = None

            if tree:
                iframe_sel = CSSSelector('iframe')
                for iframe in iframe_sel(tree):
                    url = iframe.get('src')
                    url_split = url.split('/')

                    if url_split[2].endswith('youtube.com'):
                        youtube_id = extract_youtube_id(url)
                        if youtube_id:
                            links.append('youtube:' + youtube_id)

                    elif url_split[2].endswith('soundcloud.com'):
                        api_key = self.config.get('sources', 'soundcloud_api_key')
                        soundcloud_id = extract_soundcloud_id(url) or request_soundcloud_id(url, api_key)
                        if soundcloud_id:
                            links.append('soundcloud:' + soundcloud_id)

            for link in links:
                print entry['title']
                item = {'title': entry['title'],
                        'link': link,
                        'ts': epoch_time}

                if 'image' in entry:
                    item['image'] = entry['image']['href']

                results.append(item)

        self.last_check = int(time.time())

        return results

    def __str__(self):
        return "RSSSource_%s" % self.url


class YoutubeSource(object):

    def __init__(self, type, id, config, last_check=0):
        self.type = type
        self.id = id
        self.config = config
        self.last_check = last_check

    def has_error(self, response_dict):
        if 'error' in response_dict:
            reason = response_dict['error']['errors'][0].get('reason', 'no reason given')
            print 'Error from Youtube', self.type, ':', response_dict['error']['message'], ('(%s)' % reason)
            return True
        return False

    def fetch(self, since=0):
        results = None
        if self.type == 'channel':
            results = self._fetch_channel(since)
        elif self.type == 'playlist':
            results = self._fetch_playlist(since)

        if results is not None:
            self.last_check = int(time.time())
            return results

    def _fetch_channel(self, since=0):
        results = []

        published_before = ts_to_rfc3339(time.time())
        published_after = ts_to_rfc3339(since)
        page_token = ''
        api_key = self.config.get('sources', 'youtube_api_key')

        while page_token is not None:
            url = YOUTUBE_CHANNEL_URL.format(api_key=api_key, id=self.id, before=published_before, after=published_after, token=page_token)
            response = requests.get(url)
            response_dict = response.json()

            if self.has_error(response_dict):
                return results

            items = response_dict['items']
            for item in items:
                snippet = item['snippet']
                results.append({'title': snippet['title'],
                                'link': 'youtube:' + item['id']['videoId'],
                                'ts': datetime_to_ts(parse(snippet['publishedAt'])),
                                'image': snippet['thumbnails']['default']['url']})

            page_token = response_dict.get('nextPageToken', None)

            # Did we hit the 500 results limit?
            if items and page_token is None and len(results) % 500 == 0:
                page_token = ''

                # Offset time by 1s to ensure to don't get the same video twice
                published_before = ts_to_rfc3339(time.mktime(parse(items[-1]['snippet']['publishedAt']).utctimetuple()) - 1)

        return results

    def _fetch_playlist(self, since=0):
        results = []

        page_token = ''
        api_key = self.config.get('sources', 'youtube_api_key')

        while page_token is not None:
            url = YOUTUBE_PLAYLIST_URL.format(api_key=api_key, id=self.id, token=page_token)
            response = requests.get(url)
            response_dict = response.json()

            if self.has_error(response_dict):
                return results

            items = response_dict['items']
            for item in items:
                snippet = item['snippet']
                if snippet['title'] in ['Deleted video', 'Private video']:
                    continue
                results.append({'title': snippet['title'],
                                'link': 'youtube:' + snippet['resourceId']['videoId'],
                                'ts': datetime_to_ts(parse(snippet['publishedAt'])),
                                'image': snippet['thumbnails']['default']['url']})

            page_token = response_dict.get('nextPageToken', None)

        return results

    def __str__(self):
        return "YoutubeSource_%s_%s" % (self.type, self.id)
