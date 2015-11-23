String.prototype.format = function () {
  var args = arguments;
  return this.replace(/\{(\d+)\}/g, function (m, n) { return args[n]; });
};

Number.prototype.pad = function(size) {
    var s = String(this);
    while (s.length < (size || 2))
        s = "0" + s;
    return s;
};


billy = {};

(function(billy, $) {

    billy.token = undefined;
    billy.results = {};
    billy.playlists = {};
    billy.playlist_name = undefined;
    billy.api_base = 'http://home.tribler-g.org:8000/api';
    billy.api_session = billy.api_base + '/session';
    billy.api_playlists = billy.api_base + '/playlists?token={0}&search={1}';
    billy.api_tracks = billy.api_base + '/tracks?query={0}&id={1}';
    billy.api_recommend = billy.api_base + '/recommend?token={0}&name={1}';
    billy.api_clicklog = billy.api_base + '/clicklog?token={0}';
    billy.api_waveform = billy.api_base + '/waveform?id={0}';
    billy.api_download = billy.api_base + '/download?id={0}';



    billy.Observable = function(){};
    billy.Observable.prototype = {

        listen: function(type, method) {
            var listeners, handlers;
            if (!(listeners = this.listeners)) {
                listeners = this.listeners = {};
            }
            if (!(handlers = listeners[type])) {
                handlers = listeners[type] = [];
            }
            handlers.push(method);
        },

        fire_event: function(type) {
            var listeners, handlers, i, n, handler;
            if (!(listeners = this.listeners)) {
                return;
            }
            if (!(handlers = listeners[type])) {
                return;
            }
            for (i = 0, n = handlers.length; i < n; i++) {
                handler = handlers[i];
                var args = [].slice.call(arguments);
                if (handler.apply(this, args) === false) {
                    return false;
                }
            }
        }
    }



    billy.Player = function(css_selectors) {
        this.players_total = 2;
        this.players_ready = 0;
        this.setup_jplayer(css_selectors['jplayer_core'], css_selectors['jplayer_ui']);
        this.setup_youtube(css_selectors['youtube']);
    }

    billy.Player.prototype = new billy.Observable();
    billy.Player.prototype = $.extend(billy.Player.prototype, {

        setup_jplayer: function(css_selector_core, css_selector_ui) {
            var self = this;

            self.j_player = $(css_selector_core).jPlayer({
                supplied: 'mp3',
                wmode: 'window',
                cssSelectorAncestor: css_selector_ui,
                ready: function () {
                    self.players_ready += 1;
                    if (self.players_ready === self.players_total)
                        self.fire_event('ready');
                },
                ended: function () {
                    self.fire_event('ended', 'jplayer');
                },
                play: function () {
                    self.fire_event('playing', 'jplayer');
                },
                ended: function () {
                    self.fire_event('ended', 'jplayer');
                },
                pause: function () {
                    self.fire_event('paused', 'jplayer');
                },
                timeupdate: function () {
                    self.fire_event('timeupdate', 'jplayer');
                },
                loadstart: function () {
                    self.fire_event('loadstart', 'jplayer');
                },
                error: function () {
                    self.fire_event('error', 'jplayer');
                }
            });
        },

        setup_youtube: function(css_selector) {
            var self = this;

            // Load Youtube API
            var tag = document.createElement('script');
            tag.src = "http://www.youtube.com/iframe_api";
            var firstScriptTag = document.getElementsByTagName('script')[0];
            firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);
            
            // Create player
            window.onYouTubeIframeAPIReady = function() {
                self.yt_player = new YT.Player(css_selector, {
                    height      : '200',
                    width       : '320',
                    playerVars: {
                        'autohide':         1,
                        'autoplay':         0,
                        'controls':         0,
                        'fs':               1,
                        'disablekb':        0,
                        'modestbranding':   1,
                        'iv_load_policy':   3,
                        'rel':              0,
                        'showinfo':         0,
                        'theme':            'dark',
                        'color':            'red'
                        },
                    events: {
                        'onReady': function (data) {
                            self.players_ready += 1;
                            if (self.players_ready === self.players_total)
                                self.fire_event('ready', data);
                        },
                        'onStateChange': function (state) {
                            switch(state.data) {
                                case 0:
                                    self.fire_event('ended', 'youtube');
                                    break;
                                case 1:
                                    self.fire_event('playing', 'youtube');
                                    if (self.yt_player_timer !== undefined)
                                        clearInterval(self.yt_player_timer);
                                    self.yt_player_timer = setInterval(function () {
                                        self.fire_event('timeupdate', 'youtube');
                                    }, 250);
                                    break;
                                case 2:
                                    self.fire_event('paused', 'youtube');
                                    break;
                                case 5:
                                    self.fire_event('loadstart', 'youtube');
                                    break;
                                default:
                                    // do nothing
                            }
                        },
                        'onError': function (error) {
                            self.fire_event('error', 'youtube', error);
                        }
                    }
                });
            }
        },

        load_and_play: function(track) {
            this.load(track);
            this.play();
        },

        load: function(track) {
            this.clear();

            var link = track['link'];
            if (link.startsWith('youtube:')) {
                this.yt_player.cueVideoById(link.substring(8));
            }
            else {
                this.j_player.jPlayer("setMedia", {mp3: track.link});
            }
            this.track = track;
        },

        play: function() {
            if (this.track['link'].startsWith('youtube:')) {
                this.yt_player.playVideo();
            }
            else {
                this.j_player.jPlayer("play");
            }
        },

        pause: function() {
            if (this.track['link'].startsWith('youtube:')) {
                this.yt_player.pauseVideo();
            }
            else {
                this.j_player.jPlayer("pause");
            }
        },

        stop: function() {
            this.yt_player.seekTo(0);
            this.yt_player.stopVideo();
            if (this.yt_player_timer !== undefined) {
                clearInterval(this.yt_player_timer);
                this.yt_player_timer = undefined;
            }

            this.j_player.jPlayer("stop");
        },

        clear: function() {
            this.stop();
            this.yt_player.clearVideo();
            this.j_player.jPlayer("clearMedia");
            this.track = undefined;
        },

        set_volume: function(value) {
            this.yt_player.setVolume(value);
            this.j_player.jPlayer("volume", value / 100);
        },

        seek: function(value) {
            if (this.track['link'].startsWith('youtube:')) {
                return this.yt_player.seekTo(value);
            }
            else {
                return this.j_player.jPlayer("play", value);
            }
        },

        get_current_time: function(value) {
            if (this.track === undefined) {
                return 0
            }
            else if (this.track['link'].startsWith('youtube:')) {
                return this.yt_player.getCurrentTime();
            }
            else {
                return this.j_player.data("jPlayer").status.currentTime;
            }
        },

        get_duration: function(value) {
            if (this.track === undefined) {
                return 0
            }
            else if (this.track['link'].startsWith('youtube:')) {
                return this.yt_player.getDuration();
            }
            else {
                return this.j_player.data("jPlayer").status.duration;
            }
        }
    });



    billy.Playlist = function(player, playlist) {
        this.current = undefined;
        this.player = player;
        this.playlist = playlist;
    };

    billy.Playlist.prototype = new billy.Observable();
    billy.Playlist.prototype = $.extend(billy.Playlist.prototype, {

        set_playlist: function(playlist) {
            this.playlist = playlist;
            this.fire_event('set');
        },

        reposition: function(index, step) {
            var item = this.playlist[index];
            this.playlist.splice(index, 1);
            this.playlist.splice(index - step, 0, item);
            if (this.current < index && (this.current + step) < index) {
                this.current = this.current + step;
            }
            if (this.current < index && (this.current + step) > index) {
                this.current = this.current - step;
            }
            this.fire_event('reorder', index, step);
        },

        add: function(track) {
            this.playlist.push(track);
            this.fire_event('add', track);
        },

        remove: function(index) {
            index = (index < 0) ? self.playlist.length + index : index;

            if(0 <= index && index < this.playlist.length) {
                this.playlist.splice(index, 1);

                if(this.playlist.length) {
                    if(index === self.current) {
                        this.current = (index < this.playlist.length) ? this.current : this.playlist.length - 1;
                        this.player.clear();
                    }
                    else if(index < self.current) {
                        this.current--;
                    }
                }
                else {
                    this.player.clear();
                    this.current = 0;
                }
                this.fire_event('remove', index);
            }
        },

        play: function(index) {
            index = (index < 0) ? this.playlist.length + index : index;
            var track = this.playlist[index];

            if(0 <= index && index < this.playlist.length) {
                if(this.playlist.length) {
                    this.player.load_and_play(track);
                    this.current = index;
                    this.fire_event('play', index);
                }
            }
            else if(index === undefined) {
                this.player.load_and_play(track);
                this.current = index;
                this.fire_event('play', index);
            }
        },

        pause: function() {
            this.player.pause(track);
        },

        next: function() {
            var index = (this.current + 1 < this.playlist.length) ? this.current + 1 : 0;

            if(index > 0) {
                this.play(index);
            }
        },

        previous: function() {
            var index = (this.current - 1 >= 0) ? this.current - 1 : this.playlist.length - 1;

            if(index < this.playlist.length - 1) {
                this.play(index);
            }
        }
    });



    billy.add_handlers = function(){
        var self = this;

        // Player UI event handlers

        $('#player-ui .pause').hide();
        $('#player-ui .play').on('click', function() {
            self.player.play();
        });
        $('#player-ui .pause').on('click', function() {
            self.player.pause();
        });
        $('#player-ui .stop').on('click', function() {
            self.player.stop();
        });
        $('#player-ui .previous').on('click', function() {
            self.playlist.previous();
        });
        $('#player-ui .next').on('click', function() {
            self.playlist.next();
        });
        $('#player-ui .volume-bar').on('click', function(e) {
            var pos_x = $(this).offset().left;
            var pos_width = $(this).width();
            pos_x = (e.pageX - pos_x) / pos_width;
            $('#player-ui .volume-bar .volume-bar-value').width((pos_x * 100) + '%').show();
            self.player.set_volume(pos_x * 100);
        });
        $('#player-ui .inner-seek-bar').on('click', function(e) {
            var pos_x = $(this).offset().left;
            var pos_width = $(this).width();
            pos_x = (e.pageX - pos_x) / pos_width;
            self.player.seek(pos_x * self.player.get_duration());
        });
        $('#waveform').on('mousemove mouseout', function (event) {
            var position = (event.type == 'mousemove') ? event.clientX - $(this).offset().left : 0;
            if (self.waveform_mouse_pos !== position) {
                self.waveform_mouse_pos = position;
                self.update_waveform();
            }
        });


        // Player event handlers

        this.player.listen('loadstart', function(event, player_type) {
            self.set_waveform(self.player.track._id);
        });
        this.player.listen('playing', function(event, player_type) {
            $('#player-ui .pause').show();
            $('#player-ui .play').hide();
        });
        this.player.listen('ended', function(event, player_type) {
            $('#player-ui .pause').hide();
            $('#player-ui .play').show();
            self.update_waveform();

            if (self.playlist.current !== undefined) {
                self.playlist.next();
            }
        });
        this.player.listen('paused', function(event, player_type) {
            $('#player-ui .pause').hide();
            $('#player-ui .play').show();
        });
        this.player.listen('timeupdate', function(event, player_type) {
            var duration = self.player.get_duration();
            var duration_str = (duration >= 60) ? Math.floor(duration / 60).pad(2) + ':' + Math.round(duration % 60).pad(2) : '00:' + Math.round(duration).pad(2)
            $('#player-ui .duration').text(duration_str);

            var time = self.player.get_current_time();
            var time_str = (time >= 60) ? Math.floor(time / 60).pad(2) + ':' + Math.round(time % 60).pad(2) : '00:' + Math.round(time).pad(2)
            $('#player-ui .current-time').text(time_str);
            $('#player-ui .inner-seek-bar .play-bar').width(((time / duration) * 100) + '%');

            self.update_waveform();
        });


        // Playlist event handlers

        this.playlist.listen('set', function(event) {
            var target = $("#playlist");
            target.empty();

            // Refresh playlist
            $.each(self.playlist.playlist, function(index, track) {
                var item = self.create_listitem(track, true);
                item.appendTo(target);
            });
        });
        this.playlist.listen('play', function(event, index) {
            self.set_highlighting();
        });
        this.playlist.listen('add', function(event, track) {
            var target = $("#playlist");
            var item = self.create_listitem(track, true);
            item.appendTo(target);
        });
        this.playlist.listen('remove', function(event, index) {
            $("#playlist li:nth-child(" + (index + 1) + ")").remove();
        });
        this.playlist.listen('reorder', function(event, index, step) {
            if (step > 0)
                $("#playlist li:nth-child(" + (index + 1) + ")").after($("#playlist li:nth-child(" + (index + 1 - step) + ")"));
            else
                $("#playlist li:nth-child(" + (index + 1) + ")").before($("#playlist li:nth-child(" + (index + 1 - step) + ")"));
        });
    }

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
            this.playlist.set_playlist(this.playlists[name]['tracks']);
        }
        else {
            this.playlist.set_playlist([]);
        }
        this.playlist_name = name;
        $('#playlist-tabs > li > a').filter(function() {
            return $(this).text() === name;
        }).parent().tab('show');
        $('#playlist-menu-button').html('Playlist: ' + name + ' <span class="caret"></span>');
        $('#playlist > .column-description').html(this.playlists[name]['description']);
        this.recommend();
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
            var current = $('#results .list-group').children('.playlist-current').data('track-id');

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

                var track = {
                    title: val['title'],
                    link: val['link'],
                    image: val['image'],
                    musicinfo: val['musicinfo'],
                    _id: val['_id']
                };
                self.results[val['_id']] = track;

                var item = self.create_listitem(track);
                item.appendTo(target);

                if (current == val['_id'])
                    item.addClass('playlist-current');
            });

            if (callback !== undefined)
                callback();

            $("[data-toggle=popover]").popover({html : true, container: 'body'});
        });
    }

    billy.check_api_response = function(data) {
        var success = !('error' in data);
        if (!success) {
            bootbox.alert('Failed to contact Billy server!')
        }
        return success;
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

    billy.create_listitem = function(track, inPlaylist) {
        var item_html = '<li class="list-group-item shorten" data-track-id="' + track['_id'] + '">';
        var tags_html = this.create_tags_popover(track['musicinfo']);

        item_html += '<div class="pull-right m-l btn-group">';

        if (inPlaylist) {
            item_html += '<a href="#" data-action="pl_moveup"class="m-r-sm"><span class="glyphicon glyphicon-circle-arrow-up"></span></a>';
            item_html += '<a href="#" data-action="pl_movedown"class="m-r-sm"><span class="glyphicon glyphicon-circle-arrow-down"></span></a>';
            item_html += '<a href="#" data-toggle="popover" data-placement="bottom" tabindex="0" data-trigger="focus" title="Tags" data-content="' + tags_html + '" class="m-r-sm"><span class="glyphicon glyphicon-info-sign"></span></a>';
            item_html += '<a href="#" onclick="window.location = \'' + billy.api_download.format(track.id) + '\'" class="m-r-sm"><span class="glyphicon glyphicon-record"></span></a>';
            item_html += '<a href="#" data-action="pl_play" class="m-r-sm"><span class="glyphicon glyphicon-play-circle"></span></a>';
            item_html += '<a href="#" data-action="pl_remove" class="m-r-sm"><span class="glyphicon glyphicon-remove-circle"></span></a>';
        }
        else {
            item_html += '<a href="#" data-toggle="popover" data-placement="bottom" tabindex="0" data-trigger="focus" title="Tags" data-content="' + tags_html + '" class="m-r-sm"><span class="glyphicon glyphicon-info-sign"></span></a>';
            item_html += '<a href="#" onclick="window.location = \'' + this.api_download.format(track['_id']) + '\'" class="m-r-sm"><span class="glyphicon glyphicon-record"></span></a>';
            item_html += '<a href="#" data-action="play" class="m-r-sm"><span class="glyphicon glyphicon-play-circle"></span></a>';
            item_html += '<a href="#" data-action="add" class="m-r-sm"><span class="glyphicon glyphicon-remove-circle rotate-45"></span></a>';
        }

        item_html += '</div>';

        var action = (inPlaylist) ? 'pl_play' : 'play';
        item_html += '<a href="#" data-action="' + action + '" class="img-thumbnail cover-art"><span class="rollover"></span><img alt="" src=' + track['image'] + ' onerror="this.src = \'img/blank.png\';"></a>';
        item_html += track['title'];
        item_html += '</li>';

        var item = $(item_html);

        // Add event handlers

        var self = this;
        item.off('click', 'a').on('click', 'a', function(e) {
            e.preventDefault();
            var action = $(this).data("action");

            if (action === undefined) {
                return;
            }
            else if (action.startsWith('pl_')) {
                var index = $(this).parents('.list-group-item').index();

                if (action === 'pl_play')
                    self.playlist.play(index);
                else if (action === 'pl_remove')
                    self.playlist.remove(index);
                else if (action === 'pl_moveup')
                    self.playlist.reposition(index, 1);
                else if (action === 'pl_movedown')
                    self.playlist.reposition(index, -1);
            }
            else {
                var track_id = $(this).parents('.list-group-item').data('track-id')

                if (action === 'add')
                    self.add_track(track_id);
                else if (action === 'play')
                    self.play_track(track_id);
            }
        });

        return item;
    }

    billy.set_highlighting = function() {
        if (this.playlist.current === undefined) {
            var track_id = this.player.track._id;
            $('#playlist .playlist-current').removeClass("playlist-current");
            $('#results .playlist-current').removeClass("playlist-current");
            $('#results .list-group-item[data-track-id="' + track_id + '"]').addClass('playlist-current');
        }
        else {
            var index = this.playlist.current;
            $("#results .playlist-current").removeClass("playlist-current");
            $("#playlist .playlist-current").removeClass("playlist-current");
            $("#playlist li:nth-child(" + (index + 1) + ")").addClass("playlist-current");
        }
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

    billy.add_track = function(track_id) {
        if (track_id in this.results) {
            this.playlist.add(this.results[track_id]);
            if ($('#results .list-group').children('.playlist-current').data('track-id') == track_id) {
                // Change the playlist state if the track is currently playing
                this.playlist.current = this.playlist.playlist.length - 1;
                this.set_highlighting();
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
            var track = this.results[track_id];
            this.player.load_and_play(track);

            // Reset playlist index
            this.playlist.current = undefined;
            this.set_highlighting();
        }
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
                    $('#player-ui .inner-seek-bar').removeClass('progress').removeClass('inner-seek-bar-nowaveform');
                    $('#player-ui .play-bar').removeClass('progress-bar').children().show();

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
        })
        .fail(function() {
            $('#player-ui .inner-seek-bar').addClass('progress').addClass('inner-seek-bar-nowaveform');
            $('#player-ui .play-bar').addClass('progress-bar').children().hide();
        });
    }

    billy.update_waveform = function() {
        if (this.waveform_b === undefined)
            return;

        var context = $("#waveform")[0].getContext('2d');

        var play_position = $('.play-bar').width();
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


    billy.player = new billy.Player({jplayer_core: '#player-core',
                                     jplayer_ui: '#player-ui',
                                     youtube: 'yt_player'});

    billy.playlist = new billy.Playlist(billy.player, []);

    billy.add_handlers();

})(billy, jQuery);
