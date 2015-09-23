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
                                  supplied: 'mp3',
                                  wmode: 'window'
                                });

    playlist_builder.add_playlists = function(playlists) {
        // Add playlists + add links to the dropdown menu 
        var skipped = [];
        for (var name in playlists) {
            if (name in this.playlists) {
                skipped.push(name);
                continue;
            }
            $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="playlist_builder.change_playlist(\'' + name + '\');">' + name + '</a></li>');
            this.playlists[name] = playlists[name];
        }
        // If no playlist was selected, select one now.
        if (this.playlist_name === undefined) {
            this.change_playlist(Object.keys(this.playlists)[0]);
        }
        this.save_cookie();
        return skipped;
    }

    playlist_builder.get_playlists = function() {
        // Store current playlist
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name] = this.playlist.playlist;
        }
        return this.playlists;
    }

    playlist_builder.load_cookie = function() {
        // Load cookie and add the playlists
        var cookie = $.cookie("playlists");
        if (cookie !== undefined) {
            this.add_playlists(JSON.parse(cookie));
        } 
        return (cookie !== undefined)
    }

    playlist_builder.save_cookie = function() {
        // Store playlists to cookie
        $.cookie("playlists", JSON.stringify(this.get_playlists()));
    }

    playlist_builder.import_json = function(json_string) {
        playlists = JSON.parse(json_string);
        var skipped = this.add_playlists(playlists);
        if (skipped.length > 0) {
            bootbox.alert('You already have playlist(s) with the following name(s): ' + skipped.join(', ') + '. Since playlist names have to be unique, these will not be imported.');
        }
    }

    playlist_builder.export_json = function() {
        // Download playlists as JSON file
        var json_playlists = JSON.stringify(this.get_playlists());
        var blob = new Blob([json_playlists], {type: "text/plain;charset=utf-8"});
        saveAs(blob, "playlists.json");
    }

    playlist_builder.create_playlist = function(name, description) {
        // TODO: call API
        // TODO: check if name already exists
        $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="playlist_builder.change_playlist(\'' + name + '\');">' + name + '</a></li>');
        this.change_playlist(name);
        this.save_cookie();
    }

    playlist_builder.delete_playlist = function() {
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name] = this.playlist.playlist;
        }

        var keys = Object.keys(this.playlists);
        if (keys.length < 2) {
            bootbox.alert("You need to have multiple playlists in order to remove one.");
            return;
        }

        var index = keys.indexOf(this.playlist_name);
        index = (index < keys.length - 1) ? index + 1 : index - 1
        var to_delete = this.playlist_name;
        var to_show = keys[index];

        this.change_playlist(to_show);

        delete this.playlists[to_delete];
        $('#playlist-menu > li > a[onclick="playlist_builder.change_playlist(\'' + to_delete + '\');"]').parent().remove();

        this.save_cookie();
    }

    playlist_builder.change_playlist = function(name) {
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
        $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + this.jamendo_client + "&limit=20&namesearch=" + query + "&groupby=artist_id", function(data) {
            if (!self.check_jamendo_response(data)) {
                return;
            }
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
                item_html += '<a href="#" onclick="playlist_builder.play_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-play"></span></a>';
                item_html += '<a href="#" onclick="playlist_builder.add_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-plus"></span></a>';
                item_html += '</div>';

                item_html += '<img src="' + val['image'] + '" alt="" class="img-thumbnail covert-art"';
                item_html += '<a href="javascript:;" class="jp-playlist-item" tabindex="0">' + val['name'] + ' <span class="jp-artist">' + val['artist_name'] + '</span></a>';

                item_html += '</li>';

                $(item_html).appendTo(results);
            });
        });
    }

    playlist_builder.add_track = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            this.playlist.add(this.search_results[jamendo_id]);
            this.save_cookie();
        }
        else {
            var self = this;
            $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + self.jamendo_client + "&id=" + jamendo_id, function(data) {
                if (!self.check_jamendo_response(data)) {
                    return;
                }
                $.each(data['results'], function(key, val) {

                    self.playlist.add({
                        title: val['name'],
                        artist: val['artist_name'],
                        mp3: val['audio'],
                        poster: val['image']
                    });

                });
                self.save_cookie();
            });   
        }
    }

    playlist_builder.play_track = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            $(this.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: this.search_results[jamendo_id]['mp3']}).jPlayer("play");
        }
        else {
            var self = this;
            $.getJSON("https://api.jamendo.com/v3.0/tracks/?client_id=" + self.jamendo_client + "&id=" + jamendo_id, function(data) {
                if (!self.check_jamendo_response(data)) {
                    return;
                }
                $(self.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: data['results'][0]['audio']}).jPlayer("play");
            });   
        }
    }

    playlist_builder.check_jamendo_response = function(data) {
        var success = ('headers' in data && 'status' in data['headers'] && data['headers']['status'] === 'success');
        if (!success) {
            bootbox.alert('Failed to contact Jamendo server!')
        }
        return success;
    }

})(playlist_builder, jQuery);


