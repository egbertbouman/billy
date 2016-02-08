import re
import json
import time
import urllib
import requests
import lxml.html
import feedparser
import datetime
import dateutil.tz
import logging
import threading

from datetime import datetime
from dateutil.parser import parse
from lxml.cssselect import CSSSelector
from lxml.etree import XMLSyntaxError
from urlparse import urlparse, parse_qs
from multiprocessing.dummy import Pool as ThreadPool

feedparser._HTMLSanitizer.acceptable_elements.update(['iframe'])

SOURCES_CHECK_INTERVAL = 24*3600

YOUTUBE_CHANNEL_URL = 'https://www.googleapis.com/youtube/v3/channels?part=contentDetails&id={id}&key={api_key}'
YOUTUBE_PLAYLISTITEMS_URL = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId={id}&page_token&pageToken={token}&maxResults=50&key={api_key}'
YOUTUBE_PLAYLIST_URL = 'https://www.googleapis.com/youtube/v3/playlistItems?key={api_key}&playlistId={id}&part=snippet&pageToken={token}&maxResults=50&order=date'
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
        return query['v'][0]
    else:
        path_split = o.path.split('/')
        if 'v' in path_split or 'e' in path_split or 'embed' in path_split:
            return o.path.split('/')[-1]


def extract_soundcloud_id(url):
    urls = [url, urllib.unquote(url)]
    for url in urls:
        index = url.find('/tracks/')
        if index > 0:
            return str(re.findall(r'\d+', url[index + 8:])[0])


def request_soundcloud_id(url, api_key):
    url = url.replace('https://w.soundcloud.com/player/?url=', '')

    response = requests.get(SOUNDCLOUD_RESOLVE_URL.format(url=url.encode('utf-8'), api_key=api_key))
    if response.status_code == 200:
        try:
            response_dict = response.json()
        except ValueError:
            logger = logging.getLogger(__name__)
            logger.error('Could not get soundcloud id for: %s', url)
        else:
            if isinstance(response_dict, dict) and response_dict.get('kind', '') == 'track':
                return str(response_dict['id'])


class SourceChecker(threading.Thread):

    def __init__(self, database, config):
        threading.Thread.__init__(self)

        self.logger = logging.getLogger(__name__)

        self.database = database
        self.config = config
        self.checking = False
        self.sources = {}
        self.load_sources()

        self.setDaemon(True)

    def load_sources(self):
        sources = self.database.get_all_sources()

        for source_dict in sources:
            source = self.create_source(source_dict)
            if source is None:
                self.logger.error('Incorrect source found in database, skipping')
            else:
                self.sources[source_dict['_id']] = source

    def create_source(self, source_dict):
        if not 'site' in source_dict or not 'type' in source_dict:
            return

        last_check = source_dict.get('last_check', 0)
        if source_dict['site'] == 'youtube':
            return YoutubeSource(source_dict['type'], source_dict['data'], self.config, last_check)
        elif source_dict['type'] == 'rss':
            return RSSSource(source_dict['data'], self.config, last_check)

    def check_sources(self):

        def callback(args):
            if args is None:
                return

            source_id, source, tracks, tname = args
            count = self.database.add_tracks(tracks)

            self.logger.info('Got %s track(s) for source %s (thread=%s; %s are new)', len(tracks), source, tname, count)

            self.database.set_source_last_check(source_id, source.last_check)

        self.checking = True

        pool = ThreadPool(4)
        for source_id, source in self.sources.iteritems():
            pool.apply_async(self.check_source, args=(source_id, source), callback=callback)
        pool.close()
        pool.join()

        self.checking = False

    def check_source(self, source_id, source):
        now = int(time.time())
        if now - source.last_check < SOURCES_CHECK_INTERVAL:
            return

        tracks = source.fetch(source.last_check)
        for track in tracks:
            track['sources'] = [source_id]
        return source_id, source, tracks, threading.current_thread().name

    def run(self):
        while True:
            self.logger.info('Checking sources')
            self.check_sources()
            self.logger.info('Finished checking sources')
            time.sleep(SOURCES_CHECK_INTERVAL)


class RSSSource(object):

    def __init__(self, url, config, last_check=0):
        self.logger = logging.getLogger(__name__)

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

            audio_links = []
            for link in entry['links']:
                if link['type'] == 'audio/mpeg':
                    audio_links.append(link['href'])
                else:
                    try:
                        response = requests.get(link['href'])
                    except:
                        self.logger.error('Failed to GET %s', link['href'])
                    else:
                        audio_links.extend(self.extract_audio_links(response.content))

            if 'description' in entry:
                audio_links.extend(self.extract_audio_links(entry['description']))

            for audio_link in audio_links:
                self.logger.debug('Found link in RSS source: %s - %s', entry['title'], audio_link)
                item = {'title': entry['title'],
                        'link': audio_link,
                        'ts': epoch_time}

                if 'image' in entry:
                    item['image'] = entry['image']['href']

                results.append(item)

        self.last_check = int(time.time())

        return results

    def extract_audio_links(self, text):
        # Extract Youtube/Soundcloud id's from iframes/anchors
        audio_links = []

        try:
            tree = lxml.html.fromstring(text)
        except:
            tree = None

        if tree is not None:
            urls = []

            # Find iframes/anchors urls
            iframe_sel = CSSSelector('iframe')
            for iframe in iframe_sel(tree):
                url = iframe.get('src')
                if url:
                    urls.append(url)
            anchor_sel = CSSSelector('a')
            for anchor in anchor_sel(tree):
                url = anchor.get('href')
                if url:
                    urls.append(url)

            # Process urls
            for url in urls:
                url_split = url.split('/')

                if len(url_split) < 3:
                    continue

                if url_split[2].endswith('youtube.com'):
                    youtube_id = extract_youtube_id(url)
                    if youtube_id:
                        audio_links.append('youtube:' + youtube_id)

                elif url_split[2].endswith('soundcloud.com'):
                    api_key = self.config.get('sources', 'soundcloud_api_key')
                    soundcloud_id = extract_soundcloud_id(url) or request_soundcloud_id(url, api_key)
                    if soundcloud_id:
                        audio_links.append('soundcloud:' + soundcloud_id)

        return audio_links

    def __str__(self):
        return "RSSSource_%s" % self.url


class YoutubeSource(object):

    def __init__(self, type, id, config, last_check=0):
        self.logger = logging.getLogger(__name__)

        self.type = type
        self.id = id
        self.config = config
        self.last_check = last_check

    def has_error(self, response_dict):
        if 'error' in response_dict:
            reason = response_dict['error']['errors'][0].get('reason', 'no reason given')
            self.logger.error('Error from Youtube %s : %s (%s)', self.type, response_dict['error']['message'], reason)
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
        api_key = self.config.get('sources', 'youtube_api_key')

        response = requests.get(YOUTUBE_CHANNEL_URL.format(api_key=api_key, id=self.id))
        response_dict = response.json()

        if self.has_error(response_dict):
            return results

        uploads = response_dict['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        page_token = ''

        while page_token is not None:
            response = requests.get(YOUTUBE_PLAYLISTITEMS_URL.format(api_key=api_key, id=uploads, token=page_token))
            response_dict = response.json()

            if self.has_error(response_dict):
                return results

            items = response_dict['items']

            for item in items:
                snippet = item['snippet']

                ts = datetime_to_ts(parse(snippet['publishedAt']))
                if ts < since:
                    # We don't care about anything older then this
                    return results

                results.append({'title': snippet['title'],
                                'link': 'youtube:' + snippet['resourceId']['videoId'],
                                'ts': ts,
                                'image': snippet['thumbnails']['default']['url']})

            page_token = response_dict.get('nextPageToken', None)

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

                ts = datetime_to_ts(parse(snippet['publishedAt']))
                if ts < since:
                    # We don't care about anything older then this
                    return results

                results.append({'title': snippet['title'],
                                'link': 'youtube:' + snippet['resourceId']['videoId'],
                                'ts': ts,
                                'image': snippet['thumbnails']['default']['url']})

            page_token = response_dict.get('nextPageToken', None)

        return results

    def __str__(self):
        return "YoutubeSource_%s_%s" % (self.type, self.id)
