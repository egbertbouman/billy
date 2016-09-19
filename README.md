# Billy
Billy allow you to create playlists with music from YouTube, SoundCloud, LastFM, and various RSS feeds. Billy features explicit search, automatic recommendation, playlist organization and playback functionality.


### Server dependencies
* Python 2.7+
* Twisted
* Autobahn
* pymongo
* requests
* lxml
* cssselect
* feedparser
* dateutil
* isodate

The python packages can be installed with

    pip install -r requirements.txt


### Music collection
Billy collects music automatically. However, Billy does require an initial list of sources. Sources can be YouTube, SoundCloud, LastFM, or RSS feeds. The Billy server checks all these sources daily for new tracks, and imports them into its (MongoDB) database. Billy also has limited capabilities to create new sources on it's own, based on the tracks in the identity playlist (see below).


### Metadata
For all tracks in the music collection Billy tries to gather as much metadata as possible from Last.fm (e.g., tags, playcount, listeners) and SoundCloud (e.g., followers). This metadata is stored in the database, along with the tracks themselves.


### Search
To overcome MongoDB's limited text search capabilities, Billy uses Elasticsearch to search it's music collection. Elasticsearch enables Billy to quickly search for tracks or metadata.


### Identity playlist
Billy's recommendation relies heavily on the concept of identity playlists. An identity playlist is basically a list a tracks that identify the musical taste of the current user.


### Recommendation
Recommendation is based on the search functionality, and works as follow:

1. Get the artists from the tracks in the identity playlist.
2. Get the similar artists from the tracks in the identity playlist.
3. Build a search query using the top-100 most frequently seen artists, and query the search engine.

Similar artists are discovered using Last.fm's similar artists feature. Each time a user adds a track to the identity playlist, the Billy server will look for similar artists on Last.fm and start collecting tracks for these artists.

Currently, recommendation only works when there is an identity playlist. Otherwise recommendations will be random.


### Radio
Billy allows multiple users to listen to a certain playlist synchronized. Playlists that have this radio feature enabled are called Billy radio stations. The Billy server uses WebSockets to synchronize the correct playlist position across all connected clients. The only GUI available at the moment is our [Billy-radio edX plugin](https://github.com/egbertbouman/billy-radio).


### Online demo
An online demo is available [here](http://musesync.ewi.tudelft.nl:8000/billy/).

