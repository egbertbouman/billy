import os
import json

# We make use of the Pylucene libraries (see http://lucene.apache.org/pylucene/)
import lucene
from java.io import File
from org.apache.lucene.document import Document, Field, FieldType
from org.apache.lucene.store import SimpleFSDirectory
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, DirectoryReader
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.search import IndexSearcher
from org.apache.lucene.util import Version

lucene.initVM()

# Builds Lucene index for given dataset.
# Currently, we will just stack info from multiple metadata together as 'documents' (see getIndexTerms), and consider the raw json as 'keys'.
# Alternative spellings are optional.
def index(music_json_data,index_dir,alternative_spelling_dict={},analyzer=StandardAnalyzer(Version.LUCENE_CURRENT)):
    if not os.path.exists(index_dir):
        os.mkdir(index_dir)
  
    index_dir = SimpleFSDirectory(File(index_dir))
  
    config = IndexWriterConfig(Version.LUCENE_CURRENT, analyzer)
    config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
  
    writer = IndexWriter(index_dir, config)

    index_terms_field = FieldType()
    index_terms_field.setIndexed(True)
    index_terms_field.setStored(False)

    key_field = FieldType()
    key_field.setIndexed(False)
    key_field.setStored(True)
    key_field.setIndexOptions(FieldInfo.IndexOptions.DOCS_AND_FREQS)

    for song in music_json_data:
        doc = Document()
      
        index_terms = getIndexTerms(song, alternative_spelling_dict)
        print 'Indexing song ''%s'' with terms: %s\n' % (song['name'], index_terms)
              
        doc.add(Field("index_terms", index_terms, index_terms_field))
        doc.add(Field("json", json.dumps(song), key_field))

        writer.addDocument(doc)

    writer.close()
  
    return


def search(index_dir, query, analyzer=StandardAnalyzer(Version.LUCENE_CURRENT), max_results=200):
    lucene.getVMEnv().attachCurrentThread()

    reader = DirectoryReader.open(SimpleFSDirectory(File(index_dir)))
    searcher = IndexSearcher(reader)
    
    query = QueryParser(Version.LUCENE_CURRENT, "index_terms", analyzer).parse(QueryParser.escape(query.lower()))
    
    search_results = searcher.search(query, max_results).scoreDocs
    
    result = []
    
    for search_result in search_results:
        document = searcher.doc(search_result.doc)
        result.append(document.get("json"))
        
    reader.close()
    
    # the result to be returned is a dump of JSON-formatted song data
    return '[%s]' % ', '.join(result)

# Suggest frequently occurring metadata info in a given set of JSON results
def whatShouldIHaveSearchedFor(music_json_data, num_suggestions=5, exclude_terms =[''], alternative_spelling_dict = {}):
    all_tags = []
    
    for song in music_json_data:
        all_tags.extend(getIndexTerms(song, alternative_spelling_dict))
        
    frequencies = []
    for tag in set(all_tags):
        if not tag in exclude_terms:
          frequencies.append((tag, all_tags.count(tag)))
        
    sorted_frequencies = sorted(frequencies, key = lambda x : x[1], reverse = True)
    
    return sorted_frequencies[0:num_suggestions]

# Outputting song and artist name, plus several musicinfo fields now
def getIndexTerms(song, alternative_spelling_dict):
    index_terms = ['']
    
    index_terms.append(song["artist_name"].decode("utf-8"))
    index_terms.append(song["name"].decode("utf-8"))
    
    index_terms.append(song["musicinfo"]["acousticelectric"])
    index_terms.append(song["musicinfo"]["vocalinstrumental"])
    
    index_terms.extend(expandSpeedTerms((song["musicinfo"]["speed"])))
    index_terms.extend(getCombinedTags(song, alternative_spelling_dict))
    
    print index_terms
    
    index_terms = [term.encode("utf-8") for term in index_terms]
    
    return ' '.join(filter(None, index_terms))

# Add 'fast' and 'slow'as alternatives for 'high speed' and 'low speed'
def expandSpeedTerms(speed_qualifier):
    speed_qualifiers = ['%s speed' % speed_qualifier]

    if speed_qualifier == 'high':
        speed_qualifiers.append('fast')
    elif speed_qualifier == 'low':
        speed_qualifiers.append('slow')

    return speed_qualifiers

def getCombinedTags(song_json_data, alternative_spelling_dict = {}):
    combined_tags = []
    
    for category in song_json_data['musicinfo']['tags'].keys():
        for tag in song_json_data['musicinfo']['tags'][category]:
            combined_tags.extend(expandAlternativeSpellings(tag, alternative_spelling_dict))

    return combined_tags
    
# Expands a search term with possible alternative spellings   
def expandAlternativeSpellings(search_term, alternative_spelling_dict):
    expansion_list = [search_term]
    
    if alternative_spelling_dict.has_key(search_term):
        expansion_list.extend(alternative_spelling_dict[search_term])
        
    return expansion_list


def getAlternativeSpellingDict(path, delimiter=';'):
    f = open(path,'r')
    tags = f.readlines()
    f.close()
    alternative_spelling_dict = {}
    
    for tag in tags:
        tag_spellings = filter(None, tag.strip().split(delimiter))
        if len(tag_spellings) > 1:
            alternative_spelling_dict[tag_spellings[0]] = tag_spellings[1:]
            
    return alternative_spelling_dict
       
