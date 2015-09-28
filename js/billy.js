billy = {};

(function(billy, $) {

    billy.jamendo_client = '9d9f42e3';
    billy.search_results = {};
    billy.whitelist = [];
    billy.playlists = {};
    billy.playlist_name = undefined;
    billy.playlist = new jPlayerPlaylist({
                     jPlayer: '#player-core',
                     cssSelectorAncestor: '#player-ui'
                     }, [],
                     {
                     supplied: 'mp3',
                     wmode: 'window'
                     });

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
        this.save_cookie();
        return skipped;
    }

    billy.get_playlists = function() {
        // Store current playlist
        if (this.playlist_name !== undefined) {
            this.playlists[this.playlist_name] = this.playlist.playlist;
        }
        return this.playlists;
    }

    billy.load_cookie = function() {
        // Load cookie and add the playlists
        var cookie = $.cookie("playlists");
        var parsed_cookie = (cookie !== undefined) ? JSON.parse(cookie) : cookie;
        var add = parsed_cookie !== undefined && !$.isEmptyObject(parsed_cookie);
        if (add) {
            this.add_playlists(parsed_cookie);
        } 
        return add;
    }

    billy.save_cookie = function() {
        // Store playlists to cookie
        $.cookie("playlists", JSON.stringify(this.get_playlists()));
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
        // TODO: call API
        // TODO: check if name already exists
        $('#playlist-menu').append('<li role="presentation"><a role="menuitem" tabindex="-1" href="#" onclick="billy.change_playlist(\'' + name + '\');">' + name + '</a></li>');
        this.change_playlist(name);
        this.save_cookie();
    }

    billy.delete_playlist = function() {
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
        $('#playlist-menu > li > a[onclick="billy.change_playlist(\'' + to_delete + '\');"]').parent().remove();

        this.save_cookie();
    }

    billy.change_playlist = function(name) {
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
        $('#playlist-menu-button').html('Playlist: ' + name + ' <span class="caret"></span>');
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
        var query = $("#search-query").val();
        this.call_jamendo("https://api.jamendo.com/v3.0/tracks/?client_id=" + this.jamendo_client + "&limit=200&include=musicinfo&namesearch=" + query + "&groupby=artist_id", $("#search"));
    }

    billy.recommend = function() {
        var tags = ['rock'];
        this.call_jamendo("https://api.jamendo.com/v3.0/tracks/?client_id=" + this.jamendo_client + "&limit=200&include=musicinfo&tags=" + tags, $("#recommend"));
    }

    billy.call_jamendo = function (url, target) {
        var self = this;
        $.getJSON(url, function(data) {
            if (!self.check_jamendo_response(data)) {
                return;
            }
            data = self.filter_jamendo_response(data);
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
                item_html += '<a href="#" onclick="billy.play_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-play"></span></a>';
                item_html += '<a href="#" onclick="billy.add_track(' + val['id'] + '); return false;" class="m-r-sm"><span class="glyphicon glyphicon-plus"></span></a>';

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
                        poster: val['image'],
                        musicinfo: val['musicinfo']
                    });

                });
                self.save_cookie();
            });   
        }
    }

    billy.play_track = function(jamendo_id) {
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

    billy.check_jamendo_response = function(data) {
        var success = ('headers' in data && 'status' in data['headers'] && data['headers']['status'] === 'success');
        if (!success) {
            bootbox.alert('Failed to contact Jamendo server!')
        }
        return success;
    }

    billy.filter_jamendo_response = function(data) {
        if (this.whitelist.length == 0) {
            return data;
        }

        var i = data['results'].length;
        while (i--) {
            var item = data['results'][i];
            if (this.whitelist.indexOf(item['id']) < 0) {
                var index = data['results'].indexOf(item);
                data['results'].splice(index, 1);
            }
        }
        return data;
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
