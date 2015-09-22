playlist_builder = {};

(function(playlist_builder, $) {

    playlist_builder.jamendo_client = '9d9f42e3';
    playlist_builder.search_results = {};
    playlist_builder.playlists = {};
    playlist_builder.playlist_name = undefined;
    playlist_builder.playlist = new jPlayerPlaylist({
                                  jPlayer: '#player-core',
                                  cssSelectorAncestor: '#player-ui'
                                }, [],
                                {
                                  swfPath: 'js/jplayer-2.2.0',
                                  supplied: 'mp3,m4a',
                                  wmode: 'window'
                                });       

    playlist_builder.create = function(name, description) {
        // TODO: call API
        // TODO: check if name already exists
        $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="playlist_builder.set(\'' + name + '\');">' + name + '</a></li>');
        this.set(name);
    }

    playlist_builder.set = function(name) {
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name] = this.playlist.playlist;
        }
        if (name in this.playlists) {
            this.playlist.setPlaylist(this.playlists[name]);
        }
        else {
            this.playlist.setPlaylist([]);
        }
        this.playlist_name = name;
    }

    playlist_builder.search = function() {
        var self = this;
        var query = $("#search-query").val();
        var results = $("#search-results");
        $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + this.jamendo_client + "&format=jsonpretty&limit=20&namesearch=" + query + "&groupby=artist_id", function(data) {
            //TODO: check success
            results.empty();
            $.each(data['results'], function(key, val) {

                self.search_results[val['id']] = {
                    title: val['name'],
                    artist: val['artist_name'],
                    mp3: val['audio'],
                    poster: val['image']
                };

                var item_html = '<li class="list-group-item shorten">';

                item_html += '<div class="pull-right m-l btn-group">';
                item_html += '<a href="#" onclick="playlist_builder.play(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-play"></span></a>';
                item_html += '<a href="#" onclick="playlist_builder.add(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-plus"></span></a>';
                item_html += '</div>';

                item_html += '<img src="' + val['image'] + '" alt="" class="img-thumbnail covert-art"';
                item_html += '<a href="javascript:;" class="jp-playlist-item" tabindex="0">' + val['name'] + ' <span class="jp-artist">' + val['artist_name'] + '</span></a>';

                item_html += '</li>';

                $(item_html).appendTo(results);
            });
        });
    }

    playlist_builder.add = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            this.playlist.add(this.search_results[jamendo_id]);
        }
        else {
            var self = this;
            $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + self.jamendo_client + "&id=" + jamendo_id, function(data) {
                //TODO: check success
                $.each(data['results'], function(key, val) {

                    self.playlist.add({
                        title: val['name'],
                        artist: val['artist_name'],
                        mp3: val['audio'],
                        poster: val['image']
                    });

                });
            });   
        }
    }

    playlist_builder.play = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            $(this.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: this.search_results[jamendo_id]['mp3']}).jPlayer("play");
        }
        else {
            var self = this;
            $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + self.jamendo_client + "&id=" + jamendo_id, function(data) {
                //TODO: check success
                $(self.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: data['results'][0]['audio']}).jPlayer("play");
            });   
        }
    }

})(playlist_builder, jQuery);


