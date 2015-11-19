import os
import json
import random

# We make use of the Pylucene libraries (see http://lucene.apache.org/pylucene/)
import lucene
try:
    from java.io import File
    from org.apache.lucene.document import Document, Field, FieldType
    from org.apache.lucene.store import SimpleFSDirectory
    from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, DirectoryReader
    from org.apache.lucene.queryparser.classic import QueryParser
    from org.apache.lucene.analysis.standard import StandardAnalyzer
    from org.apache.lucene.search import IndexSearcher
    from org.apache.lucene.util import Version
    LUCENE3 = False
except ImportError:
    # PyLucene 3
    from lucene import SimpleFSDirectory, System, File, Document, Field, StandardAnalyzer, IndexWriter, \
                       Version, IndexSearcher, QueryParser, FieldInfo, IndexWriterConfig
    LUCENE3 = True

lucene.initVM()


class Search(object):

    def __init__(self, index_dir, alternative_spelling_dict={}):
        self.index_dir = index_dir
        self.alternative_spelling_dict = alternative_spelling_dict
        self.analyzer = StandardAnalyzer(Version.LUCENE_CURRENT)

    def index(self, music_json_data):
        # Builds Lucene index for given dataset.
        # Currently, we will just stack info from multiple metadata together as 'documents' (see getIndexTerms), and consider the raw json as 'keys'.
        # Alternative spellings are optional.        
        if not os.path.exists(self.index_dir):
            os.makedirs(self.index_dir)

        lucene.getVMEnv().attachCurrentThread()

        dir = SimpleFSDirectory(File(self.index_dir))

        config = IndexWriterConfig(Version.LUCENE_CURRENT, self.analyzer)
        config.setOpenMode(IndexWriterConfig.OpenMode.CREATE_OR_APPEND)

        writer = IndexWriter(dir, config)

        if not LUCENE3:
            index_terms_field = FieldType()
            index_terms_field.setIndexed(True)
            index_terms_field.setStored(False)

            key_field = FieldType()
            key_field.setIndexed(False)
            key_field.setStored(True)
            key_field.setIndexOptions(FieldInfo.IndexOptions.DOCS_AND_FREQS)

        music_json_data = music_json_data if isinstance(music_json_data, list) else [music_json_data]

        for song in music_json_data:
            doc = Document()

            index_terms = ' '.join(getIndexTerms(song, self.alternative_spelling_dict))
            print 'Indexing song ''%s'' with terms: %s\n' % (song['title'].encode('utf-8'), index_terms)

            if not LUCENE3:
                doc.add(Field("index_terms", index_terms, index_terms_field))
                doc.add(Field("json", json.dumps(song), key_field))
            else:
                field1 = Field("index_terms", index_terms, Field.Store.NO, Field.Index.ANALYZED)
                field2 = Field("json", json.dumps(song), Field.Store.YES, Field.Index.NO)
                field2.setIndexOptions(FieldInfo.IndexOptions.DOCS_AND_FREQS)

                doc.add(field1)
                doc.add(field2)

            writer.addDocument(doc)

        writer.close()
        return

    def search(self, query, max_results=200):
        if not os.path.exists(self.index_dir) or not os.listdir(self.index_dir):
            return []

        lucene.getVMEnv().attachCurrentThread()

        dir = SimpleFSDirectory(File(self.index_dir)) if LUCENE3 else DirectoryReader.open(SimpleFSDirectory(File(self.index_dir)))
        searcher = IndexSearcher(dir)

        query = QueryParser(Version.LUCENE_CURRENT, "index_terms", self.analyzer).parse(QueryParser.escape(query.lower()))

        search_results = searcher.search(query, max_results).scoreDocs

        result = []

        for search_result in search_results:
            document = searcher.doc(search_result.doc)
            result.append(document.get("json"))

        dir.close()

        # The result to be returned is a list of JSON dictionaries (one per song)
        return json.loads('[%s]' % ', '.join(result))


    def recommend(self, song_set):
        if len(song_set) > 0:
            song_set_ids = [song['id'] for song in song_set]
            frequent_terms_in_set = getFrequentTerms(song_set)
            query_from_frequent_terms = ' '.join(frequent_terms_in_set)
            print 'querying dataset for "%s"' % query_from_frequent_terms
            search_results = self.search(self.index_dir, query_from_frequent_terms)

            filtered_search_results = []
            for search_result in search_results:
                if not search_result['id'] in song_set_ids:
                    filtered_search_results.append(search_result)

            if len(filtered_search_results) > 0:
                return filtered_search_results


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

    index_terms.append(getUnicodeString(song["musicinfo"].get("acousticelectric", "")))
    index_terms.append(getUnicodeString(song["musicinfo"].get("vocalinstrumental", "")))

    index_terms.extend(expandSpeedTerms((song["musicinfo"].get("speed", ""))))
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

    for category in song_json_data['musicinfo']['tags'].keys():
        for tag in song_json_data['musicinfo']['tags'][category]:
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
