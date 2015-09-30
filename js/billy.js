String.prototype.format = function () {
  var args = arguments;
  return this.replace(/\{(\d+)\}/g, function (m, n) { return args[n]; });
};

billy = {};

(function(billy, $) {

    billy.token = undefined;
    billy.search_results = {};
    billy.playlists = {};
    billy.playlist_name = undefined;
    billy.playlist = new jPlayerPlaylist({
                         jPlayer: '#player-core',
                         cssSelectorAncestor: '#player-ui'
                     }, [], {
                         supplied: 'mp3',
                         wmode: 'window'
                     });
    billy.api_base = 'http://musesync.ewi.tudelft.nl/api';
    billy.api_session = billy.api_base + '/session';
    billy.api_playlists = billy.api_base + '/playlists?token={0}&search={1}';
    billy.api_tracks = billy.api_base + '/tracks?query={0}&id={1}';

    billy.add_playlists = function(playlists) {
        // Add playlists + add links to the dropdown menu 
        var skipped = [];
        for (var name in playlists) {
            if (name in this.playlists) {
                skipped.push(name);
                continue;
            }
            $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="billy.change_playlist(\'' + name + '\');">' + name + '</a></li>');
            this.playlists[name] = playlists[name];
        }
        // If no playlist was selected, select one now.
        if (this.playlist_name === undefined) {
            this.change_playlist(Object.keys(this.playlists)[0]);
        }
        this.save_to_server();
        return skipped;
    }

    billy.get_playlists = function() {
        // Store current playlist
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name]['tracks'] = this.playlist.playlist;
        }
        return this.playlists;
    }

    billy.load_from_server = function() {
        var self = this;

        this.token = $.cookie('token');
        if (this.token !== undefined) {
            // Load playlists from server and show them to the user
            $.getJSON(self.api_playlists.format(this.token, ''), function(data) {
                self.add_playlists(data);
            })
            .fail(function() {
                // No remote playlists available. Create a new playlist.
                self.create_playlist();
            });
        }
        else {
            $.getJSON(self.api_session, function(data) {
                self.token = data['token'];
                $.cookie('token', self.token, {expires: 3650});
                self.create_playlist();
            })
        }
    }

    billy.save_to_server = function() {
        // Store playlists in remote database
        $.ajax({
            type: 'POST',
            url: this.api_playlists.format(this.token, ''),
            contentType: "application/json",
            processData: false,
            data: JSON.stringify(this.get_playlists()),
            error: function() { bootbox.alert('Failed to contant Billy server') },
            dataType: "text"
        });
    }

    billy.import_json = function(json_string) {
        playlists = JSON.parse(json_string);
        var skipped = this.add_playlists(playlists);
        if (skipped.length > 0) {
            bootbox.alert('You already have playlist(s) with the following name(s): ' + skipped.join(', ') + '. Since playlist names have to be unique, these will not be imported.');
        }
    }

    billy.export_json = function() {
        // Download playlists as JSON file
        var json_playlists = JSON.stringify(this.get_playlists());
        var blob = new Blob([json_playlists], {type: "text/plain;charset=utf-8"});
        saveAs(blob, "playlists.json");
    }

    billy.create_playlist = function(name, description) {
        if (name === undefined) {
            $('#new-playlist-modal').modal('show');
            return;
        }
        $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="billy.change_playlist(\'' + name + '\');">' + name + '</a></li>');
        this.playlists[name] = {name: name, description: description, tracks: []};
        this.change_playlist(name);
        this.save_to_server();
    }

    billy.delete_playlist = function() {
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name]['tracks'] = this.playlist.playlist;
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
        $('#playlist-menu > li > a[onclick="billy.change_playlist(\'' + to_delete + '\');"]').parent().remove();

        this.save_to_server();
    }

    billy.change_playlist = function(name) {
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name]['tracks'] = this.playlist.playlist;
        }
        if (name in this.playlists) {
            this.playlist.setPlaylist(this.playlists[name]['tracks']);
        }
        else {
            this.playlist.setPlaylist([]);
        }
        this.playlist_name = name;
        $('#playlist-menu-button').html('Playlist: ' + name + ' <span class="caret"></span>');
        $('#playlist > .column-description').html(this.playlists[name]['description']);
        this.recommend();
    }

    billy.change_results = function(name) {
        var tab = $('#' + name);
        $('#results-menu-button').html(tab.attr('name') + ' <span class="caret"></span>');
        $('.tab-pane').each(function (item) {
            $(this).hide();
        });
        $(tab).show();
    }

    billy.search = function() {
        this.change_results('search');
        var query = $("#search-query").val();
        this.call_api(this.api_tracks.format(query, ''), $("#search"));
    }

    billy.recommend = function() {
        // TODO
        var tags = ['rock'];
        this.call_api(this.api_tracks.format(tags, ''), $("#recommend"));
    }

    billy.call_api = function (url, target) {
        var self = this;
        $.getJSON(url, function(data) {
            if (!self.check_api_response(data)) {
                return;
            }
            target.empty();

            // If we do not have results, let the user know
            if (data['results'].length == 0) {
                target.append('No results found');
                return;
            }
            // If we do have results, show them
            $.each(data['results'], function(key, val) {

                if (!('tags' in val['musicinfo']))
                    val['musicinfo']['tags'] = {};
                if (!('genres' in val['musicinfo']['tags']))
                    val['musicinfo']['tags']['genres'] = [];
                if (!('instruments' in val['musicinfo']['tags']))
                    val['musicinfo']['tags']['instruments'] = [];
                if (!('vartags' in val['musicinfo']['tags']))
                    val['musicinfo']['tags']['vartags'] = [];

                self.search_results[val['id']] = {
                    title: val['name'],
                    artist: val['artist_name'],
                    mp3: val['audio'],
                    poster: val['image'],
                    musicinfo: val['musicinfo']
                };

                var item_html = '<li class="list-group-item shorten">';

                var tags_html = self.create_tags_popover(val['musicinfo']);

                item_html += '<div class="pull-right m-l btn-group">';
                item_html += '<a href="#" onclick="return false;" data-toggle="popover" data-placement="bottom" tabindex="0" data-trigger="focus" title="Tags" data-content="' + tags_html + '" class="m-r-sm"><span class="glyphicon glyphicon-info-sign"></span></a>';
                item_html += '<a href="#" onclick="billy.play_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-play-circle"></span></a>';
                item_html += '<a href="#" onclick="billy.add_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-remove-circle rotate-45"></span></a>';

                item_html += '</div>';

                item_html += '<a class="img-thumbnail cover-art" href="#" onclick="billy.play_track(' + val['id'] + '); return false;" ><span class="rollover"></span><img alt="" src=' + val['image'] + '></a>';
                item_html += val['name'] + ' - ' + val['artist_name'];

                item_html += '</li>';

                $(item_html).appendTo(target);
            });
          $("[data-toggle=popover]").popover({ html : true, container: 'body'});
        });
    }

    billy.add_track = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            this.playlist.add(this.search_results[jamendo_id]);
            this.save_to_server();
        }
        else {
            var self = this;
            $.getJSON(this.api_tracks.format('', jamendo_id), function(data) {
                if (!self.check_api_response(data)) {
                    return;
                }
                $.each(data['results'], function(key, val) {

                    self.playlist.add({
                        title: val['name'],
                        artist: val['artist_name'],
                        mp3: val['audio'],
                        poster: val['image'],
                        musicinfo: val['musicinfo']
                    });

                });
                self.save_to_server();
            });   
        }
    }

    billy.play_track = function(jamendo_id) {
        if (jamendo_id in this.search_results) {
            $(this.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: this.search_results[jamendo_id]['mp3']}).jPlayer("play");
        }
        else {
            var self = this;
            $.getJSON(this.api_tracks.format('', jamendo_id), function(data) {
                if (!self.check_api_response(data)) {
                    return;
                }
                $(self.playlist.cssSelector.jPlayer).jPlayer("setMedia", {mp3: data['results'][0]['audio']}).jPlayer("play");
            });   
        }
    }

    billy.check_api_response = function(data) {
        var success = !('error' in data);
        if (!success) {
            bootbox.alert('Failed to contact Jamendo server!')
        }
        return success;
    }

    billy.create_tags_popover = function(musicinfo) {
        tags_html = "<div class='tags-container'>" +
                    "<table><tr><td>Genres:</td><td>";

        if (musicinfo['tags']['genres'].length == 0) {
            tags_html += "n/a";
        }

        musicinfo['tags']['genres'].forEach(function (tag) {
            tags_html += "<span class='label label-success'>" + tag + "</span>";
        });

        tags_html += "</td></tr><tr><td>Instruments:</td><td>";

        if (musicinfo['tags']['instruments'].length == 0) {
            tags_html += "n/a";
        }

        musicinfo['tags']['instruments'].forEach(function (tag) {
            tags_html += "<span class='label label-danger'>" + tag + "</span>";
        });

        tags_html += "</td></tr><tr><td>Other:</td><td>";

        if (musicinfo['tags']['vartags'].length == 0) {
            tags_html += "n/a";
        }

        musicinfo['tags']['vartags'].forEach(function (tag) {
            tags_html += "<span class='label label-primary'>" + tag + "</span>";
        });

        tags_html += "</td></tr></div>";

        return tags_html;
    }

})(billy, jQuery);
