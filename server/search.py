import os
import json
import random
import logging

from util import *
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks


ES_BULK_URL = 'http://{host}:{port}/_bulk'
ES_SEARCH_URL = 'http://{host}:{port}/{index}/{type}/_search?size={size}&from={offset}'
ES_MAPPING_URL = 'http://{host}:{port}/{index}'

BULK_BATCH_SIZE = 1000


class Search(object):

    def __init__(self, database, config, alternative_spelling_dict={}):
        self.logger = logging.getLogger(__name__)

        self.database = database
        self.config = config
        self.host = self.config.get('elasticsearch', 'host')
        self.port = self.config.get('elasticsearch', 'port')
        self.alternative_spelling_dict = alternative_spelling_dict

    @inlineCallbacks
    def create(self):
        url = ES_MAPPING_URL.format(host=self.host, port=self.port, index=self.database.db.name)
        response = yield get_request(url)
        if response.json.get('error', {}).get('type', None) == 'index_not_found_exception':
            with open('es_track_mapping.json', 'rb') as fp:
                mapping = fp.read()
            content = {'settings': {'number_of_shards' : 1},
                       'mappings' : json.loads(mapping)}
            response = yield put_request(url, data=json.dumps(content))
            if response.json.get('acknowledged', False):
                self.logger.info('Created index %s', self.database.db.name)
            else:
                self.logger.info('Failed to create index %s', self.database.db.name)

    @inlineCallbacks
    def index(self, tracks):
        # Make sure the index exists
        self.create()

        url = ES_BULK_URL.format(host=self.host, port=self.port)
        count = 0
        for index in xrange(0, len(tracks), BULK_BATCH_SIZE):
            batch = tracks[index:index+BULK_BATCH_SIZE]
            data = ''
            for track in batch:
                data += json.dumps({'create': {'_index': self.database.db.name, '_type': 'track', '_id': track.pop('_id')}}) + '\n'
                if 'musicinfo' in track and 'listeners' in track['musicinfo']:
                    track['musicinfo']['listeners'] = [{'ts':ts, 'count':count} for ts, count in track['musicinfo']['listeners'].items()]
                if 'musicinfo' in track and 'playcount' in track['musicinfo']:
                    track['musicinfo']['playcount'] = [{'ts':ts, 'count':count} for ts, count in track['musicinfo']['playcount'].items()]
                track['sources'] = [{'id':source} for source in track['sources']]
                data += json.dumps(track) + '\n'
            response = yield post_request(url, data=data)
            for log in response.json.get('items', []):
                if log.get('create', {}).get('status', None) == 201:
                    count += 1
        self.logger.info('Indexed %s record(s)', count)

    @inlineCallbacks
    def search(self, query, field='title', sources=None, max_results=200):
        self.logger.info('Searching for query %s', query)

        url = ES_SEARCH_URL.format(host=self.host, port=self.port, index=self.database.db.name, type='track', size=max_results, offset=0)

        query_dict = build_bool_query('must', {})
        query_dict['query']['bool']['must'] = [build_query(query, field)]

        if sources:
            # Search within specific sources
            nested_query = build_bool_query('must', {'sources.id': ' '.join(sources)}, nested_path='sources')
            query_dict['query']['bool']['must'].append(nested_query)

        response = yield post_request(url, data=json.dumps(query_dict))

        results = []
        for hit in response.json.get('hits', {}).get('hits', []):
            result = hit['_source']
            result['_id'] = hit['_id']
            results.append(result)

        defer.returnValue(results)

    @inlineCallbacks
    def recommend(self, playlist):
        song_set = playlist['tracks']

        if len(song_set) > 0:
            song_set_ids = [song['_id'] for song in song_set]

            sources = set()
            artists = set()
            similar_artists = set()
            for track in playlist['tracks']:
                for source in track['sources']:
                    sources.add(source)
                if 'artist_name' in track.get('musicinfo', {}):
                    artists.add(track['musicinfo']['artist_name'])
                similar_artists |= set(track.get('musicinfo', {}).get('similar_artists', []))

            all_artists = list(artists) + list(similar_artists)
            query = ' '.join(map(lambda x: '\"' + x + '\"', all_artists))
            search_results = yield self.search(query, sources=sources)

            filtered_search_results = []
            for search_result in search_results:
                if not search_result['_id'] in song_set_ids:
                    filtered_search_results.append(search_result)

            if len(filtered_search_results) > 0:
                defer.returnValue(filtered_search_results)
        else:
            # Return recommendations based on playlist name + description
            query = playlist['name'] + ' ' + playlist['description']
            self.logger.info('Querying dataset for "%s"', query)
            defer.returnValue((yield self.search(query)))


def getFrequentTerms(music_json_data, num_suggestions=20, exclude_terms=[''], alternative_spelling_dict={}):
    # Suggest frequently occurring metadata info in a given set of JSON results

    all_tags = []

    for song in music_json_data:
        all_tags.extend(getIndexTerms(song, alternative_spelling_dict))

    frequencies = []
    for tag in set(all_tags):
        if not tag in exclude_terms:
          frequencies.append((tag, all_tags.count(tag)))

    sorted_frequencies = sorted(frequencies, key=lambda x : x[1], reverse=True)

    top_n = sorted_frequencies[0:num_suggestions]

    return [tuple_item[0] for tuple_item in top_n]


def getIndexTerms(song, alternative_spelling_dict):
    # Outputting song and artist name, plus several musicinfo fields now
    index_terms = ['']

    index_terms.append(getUnicodeString(song["title"]))

    music_info = song.get("musicinfo", {})

    index_terms.append(getUnicodeString(music_info.get("acousticelectric", "")))
    index_terms.append(getUnicodeString(music_info.get("vocalinstrumental", "")))

    index_terms.extend(expandSpeedTerms(music_info.get("speed", "")))
    index_terms.extend(getCombinedTags(song, alternative_spelling_dict))

    index_terms = [term.encode('utf-8') for term in index_terms]

    return filter(None, index_terms)


def getUnicodeString(input):
    if isinstance(input, unicode):
        return input
    else:
        return input.decode('utf-8')

def expandSpeedTerms(speed_qualifier):
    # Add 'fast' and 'slow'as alternatives for 'high speed' and 'low speed'
    speed_qualifiers = ['%s speed' % speed_qualifier]

    if speed_qualifier == 'high':
        speed_qualifiers.append('fast')
    elif speed_qualifier == 'low':
        speed_qualifiers.append('slow')

    return speed_qualifiers

def getCombinedTags(song_json_data, alternative_spelling_dict={}):
    combined_tags = []

    music_info = song_json_data.get('musicinfo', {})
    for category, tags in music_info.iteritems():
        for tag in tags:
            combined_tags.extend(expandAlternativeSpellings(getUnicodeString(tag), alternative_spelling_dict))

    return combined_tags

def expandAlternativeSpellings(search_term, alternative_spelling_dict):
    # Expands a search term with possible alternative spellings   
    expansion_list = [search_term]

    if alternative_spelling_dict.has_key(search_term):
        expansion_list.extend(alternative_spelling_dict[search_term])

    return expansion_list


def getAlternativeSpellingDict(path, delimiter=';'):
    f = open(path, 'r')
    tags = f.readlines()
    f.close()
    alternative_spelling_dict = {}

    for tag in tags:
        tag_spellings = filter(None, tag.strip().split(delimiter))
        if len(tag_spellings) > 1:
            alternative_spelling_dict[tag_spellings[0]] = tag_spellings[1:]

    return alternative_spelling_dict
