String.prototype.format = function () {
  var args = arguments;
  return this.replace(/\{(\d+)\}/g, function (m, n) { return args[n]; });
};

billy = {};

(function(billy, $) {

    billy.token = undefined;
    billy.results = {};
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
    billy.api_recommend = billy.api_base + '/recommend?token={0}&name={1}';
    billy.api_clicklog = billy.api_base + '/clicklog?token={0}';
    billy.api_waveform = billy.api_base + '/waveform?id={0}';

    $(billy.playlist.cssSelector.jPlayer).bind($.jPlayer.event.loadstart, function(event) {
        billy.set_waveform(event.jPlayer.status.media.id);
    });
    $(billy.playlist.cssSelector.jPlayer).bind($.jPlayer.event.timeupdate + " " + $.jPlayer.event.ended, function() {
        billy.update_waveform();
    });
    $('#waveform').on('mousemove mouseout', function (event) {
        var position = (event.type == 'mousemove') ? event.clientX - $(this).offset().left : 0;
        if (billy.waveform_mouse_pos !== position) {
            billy.waveform_mouse_pos = position;
            billy.update_waveform();
        }
    });

    billy.add_playlists = function(playlists) {
        // Add playlists + add links to the playlist tabs
        var skipped = [];
        for (var name in playlists) {
            if (name in this.playlists) {
                skipped.push(name);
                continue;
            }

            $('#playlist-tabs').append('<li role="presentation"><a href="#" onclick="billy.change_playlist(\'' + name + '\');">' + name + '</a></li>');
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
                if ($.isEmptyObject(data))
                     self.create_playlist();
                else
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
        var self = this;

        // Store playlists in remote database
        $.ajax({
            type: 'POST',
            url: this.api_playlists.format(this.token, ''),
            contentType: "application/json",
            processData: false,
            data: JSON.stringify(this.get_playlists()),
            success: function() { self.recommend() },
            error: function() { bootbox.alert('Failed to contact Billy server') },
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
        var tab = $('<li role="presentation"><a href="#" onclick="billy.change_playlist(\'' + name + '\');">' + name + '</a></li>').appendTo($('#playlist-tabs'));
        if (Object.keys(this.playlists).length == 0)
            tab.tab('show');
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
            bootbox.alert("You should have at least one playlist. Please create a new one before deleting this one.");
            return;
        }

        var index = keys.indexOf(this.playlist_name);
        index = (index < keys.length - 1) ? index + 1 : index - 1
        var to_delete = this.playlist_name;
        var to_show = keys[index];

        this.change_playlist(to_show);

        delete this.playlists[to_delete];
        $('#playlist-tabs > li > a').filter(function() {
            return $(this).text() === to_delete;
        }).parent().remove();

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
        $('#playlist-tabs > li > a').filter(function() {
            return $(this).text() === name;
        }).parent().tab('show');
        $('#playlist-menu-button').html('Playlist: ' + name + ' <span class="caret"></span>');
        $('#playlist > .column-description').html(this.playlists[name]['description']);
        this.recommend();
    }

    billy.change_results = function(name) {
        // Highlight tab
        $('#' + name + '-tab').tab('show');
        // Show tab pane
        var tab = $('#' + name);
        $('.tab-pane').each(function (item) {
            $(this).hide();
        });
        $(tab).show();
        // Set description
        if (name === 'search') {
            var msg = ($('#search > .list-group-item').length > 0) ? 'The songs below match your search terms best:' : '';
            $('#results > .column-description').html(msg);
        }
        else if (name === 'recommend')
            $('#results > .column-description').html('Consider adding some of these songs to your playlist too:');
    }

    billy.search = function() {
        var query = $("#search-query").val();
        this.call_api(this.api_tracks.format(query, ''), $("#search"), function() {billy.change_results('search');});
    }

    billy.recommend = function() {
        this.call_api(this.api_recommend.format(this.token, this.playlist_name), $("#recommend"));
    }

    billy.call_api = function (url, target, callback) {
        var self = this;
        $.getJSON(url, function(data) {
            if (!self.check_api_response(data)) {
                return;
            }

            // Find out which track is highlighted (if any)
            var current = $('#results .list-group').children('.jp-playlist-current').data('track-id');

            target.empty();

            // If we do not have results, let the user know
            if (data['results'].length == 0)
                target.append('No results found');

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

                self.results[val['id']] = {
                    title: val['name'],
                    artist: val['artist_name'],
                    mp3: val['audio'],
                    poster: val['image'],
                    musicinfo: val['musicinfo'],
                    id: val['id']
                };

                var item_html = '<li class="list-group-item shorten" data-track-id="' + val['id'] + '">';

                var tags_html = self.create_tags_popover(val['musicinfo']);

                item_html += '<div class="pull-right m-l btn-group">';
                item_html += '<a href="#" data-toggle="popover" data-placement="bottom" tabindex="0" data-trigger="focus" title="Tags" data-content="' + tags_html + '" class="m-r-sm"><span class="glyphicon glyphicon-info-sign"></span></a>';
                item_html += '<a href="#" data-action="play" class="m-r-sm"><span class="glyphicon glyphicon-play-circle"></span></a>';
                item_html += '<a href="#" data-action="add" class="m-r-sm"><span class="glyphicon glyphicon-remove-circle rotate-45"></span></a>';

                item_html += '</div>';

                item_html += '<a href="#" data-action="play" class="img-thumbnail cover-art"><span class="rollover"></span><img alt="" src=' + val['image'] + '></a>';
                item_html += val['name'] + ' - ' + val['artist_name'];

                item_html += '</li>';

                var item = $(item_html).appendTo(target);

                if (current == val['id'])
                    item.addClass('jp-playlist-current');
            });
            // Bind event handlers
            target.off("click", "a").on("click", "a", function(e) {
                e.preventDefault();
                var action = $(this).data("action");
                var item = $(this).parents('.list-group-item');

                if (action === 'play')
                    self.play_track(item.data('track-id'));
                else if (action === 'add')
                    self.add_track(item.data('track-id'));
            });

            if (callback !== undefined)
                callback();

            $("[data-toggle=popover]").popover({html : true, container: 'body'});
        });
    }

    billy.add_track = function(track_id) {
        if (track_id in this.results) {
            this.playlist.add(this.results[track_id]);
            if ($('#results .list-group').children('.jp-playlist-current').data('track-id') == track_id) {
                // Change the playlist state if the track is currently playing
                var index = this.playlist.playlist.length - 1
                this.playlist.current = index;
                this.playlist._highlight(index);
                $('#results .list-group').children(".jp-playlist-current").removeClass("jp-playlist-current");
            }
            this.save_to_server();
            this.clicklog({
                track_id: track_id,
                playlist_name: this.playlist_name,
                tab: $("#results .tab-pane").filter(function() { return $(this).css("display") !== "none" }).attr('id'),
                query: $("#search-query").val()
            });
        }
    }

    billy.play_track = function(track_id) {
        if (track_id in this.results) {
            $(this.playlist.cssSelector.jPlayer).jPlayer("setMedia", {id: track_id, mp3: this.results[track_id]['mp3']}).jPlayer("play");
            // Set highlighting
            $('#results .list-group').children(".jp-playlist-current").removeClass("jp-playlist-current");
            $('#results .list-group-item[data-track-id="' + track_id + '"]').addClass('jp-playlist-current');
            // Reset playlist index
            this.playlist.current = undefined;
            this.playlist._refresh(true);
        }
    }

    billy.clicklog = function(data) {
        // Post clicklog data to server
        $.ajax({
            type: 'POST',
            url: this.api_clicklog.format(this.token),
            contentType: "application/json",
            processData: false,
            data: JSON.stringify(data),
            dataType: "text"
        });
    }

    billy.check_api_response = function(data) {
        var success = !('error' in data);
        if (!success) {
            bootbox.alert('Failed to contact Billy server!')
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

    billy.set_waveform = function(track_id) {
        var self = this;

        $.getJSON(self.api_waveform.format(track_id), function(data) {
            settings = {
                canvas_width: $('#waveform').width(),
                canvas_height: $('#waveform').height(),
                bar_width: 3,
                bar_gap : 0.2,
                wave_color: "#337ab7",
                download: false,
                onComplete: function(png, pixels) {
                    var context = $("#waveform")[0].getContext('2d');

                    // Waveform image data in different colors
                    self.waveform_b = pixels;
                    self.waveform_d = context.createImageData(pixels);
                    self.waveform_gs = context.createImageData(pixels);

                    for (var i = 0; i < pixels.data.length; i += 4) {
                        self.waveform_d.data[i] = pixels.data[i] - 80;
                        self.waveform_d.data[i + 1] = pixels.data[i + 1] - 80;
                        self.waveform_d.data[i + 2] = pixels.data[i + 2] - 80;
                        self.waveform_d.data[i + 3] = pixels.data[i + 3] - 80;

                        var brightness = (pixels.data[i] + pixels.data[i + 1] + pixels.data[i + 2]) / 3;
                        brightness *= 1.5;
                        self.waveform_gs.data[i] = brightness;
                        self.waveform_gs.data[i + 1] = brightness;
                        self.waveform_gs.data[i + 2] = brightness;
                        self.waveform_gs.data[i + 3] = pixels.data[i + 3];
                    }

                    self.update_waveform();
                }
            };
            SoundCloudWaveform.generate(data['waveform'], settings);
        });
    }

    billy.update_waveform = function() {
        if (this.waveform_b === undefined)
            return;

        var context = $("#waveform")[0].getContext('2d');

        var play_position = $('.jp-play-bar').width();
        var mouse_position = this.waveform_mouse_pos || 0;

        // Draw background
        context.putImageData(this.waveform_gs, 0, 0);

        // Draw position within the track
        context.putImageData(this.waveform_b, 0, 0, 0, 0, play_position, this.waveform_b.height);

        if (mouse_position === 0)
            return;

        // Draw hover
        if (mouse_position > play_position)
            context.putImageData(this.waveform_d, 0, 0, play_position, 0, mouse_position - play_position, this.waveform_b.height);
        else
            context.putImageData(this.waveform_d, 0, 0, mouse_position, 0, play_position - mouse_position, this.waveform_b.height);

    }

})(billy, jQuery);