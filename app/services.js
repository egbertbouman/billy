app.factory('jPlayerFactory', function($rootScope) {

    var player = {};
    player.create = function(css_selector_core, css_selector_ui) {
        this.player = $(css_selector_core).jPlayer({
            supplied: 'mp3',
            wmode: 'window',
            cssSelectorAncestor: css_selector_ui,
            ready: function () {
                $rootScope.$broadcast('_ready');
            },
            play: function () {
                $rootScope.$broadcast('playing');
            },
            ended: function () {
                $rootScope.$broadcast('ended');
            },
            pause: function () {
                $rootScope.$broadcast('paused');
            },
            loadstart: function () {
                $rootScope.$broadcast('loadstart');
            },
            error: function () {
                $rootScope.$broadcast('error');
            }
        });
    };
    player.load_and_play = function(track) {
        this.clear();
        this.player.jPlayer("setMedia", {mp3: track.link});
        this.player.jPlayer("play");
        this.track = track;
    };
    player.play = function() {
        this.player.jPlayer("play");
    };
    player.pause = function() {
        this.player.jPlayer("pause");
    };
    player.stop = function() {
        this.player.jPlayer("stop");
    };
    player.clear = function() {
        this.player.jPlayer("clearMedia");
        this.track = undefined;
    };
    player.set_volume = function(value) {
        this.player.jPlayer("volume", value / 100);
    };
    player.seek = function(value) {
        this.player.jPlayer("play", value);
    };
    player.get_current_time = function(value) {
        return this.player.data("jPlayer").status.currentTime;
    };
    player.get_duration = function(value) {
        return this.player.data("jPlayer").status.duration;
    };

    return player;
});


app.factory('YoutubePlayerFactory', function($rootScope) {

    var player = {};
    player.create = function(css_selector) {
        var self = this;

        // Load Youtube API
        $.getScript('http://www.youtube.com/iframe_api');

        $('<div id="' + css_selector + '"></div>').appendTo('body');

        // Create player
        window.onYouTubeIframeAPIReady = function() {
            self.player = new YT.Player(css_selector, {
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
                        $rootScope.$broadcast('_ready', data);
                    },
                    'onStateChange': function (state) {
                        switch(state.data) {
                            case -1:
                                $rootScope.$broadcast('loadstart');
                                break;
                            case 0:
                                $rootScope.$broadcast('ended');
                                break;
                            case 1:
                                $rootScope.$broadcast('playing');
                                break;
                            case 2:
                                $rootScope.$broadcast('paused');
                                break;
                            case 5:
                                $rootScope.$broadcast('loadstart');
                                break;
                            default:
                                // do nothing
                        }
                    },
                    'onError': function (error) {
                        $rootScope.$broadcast('error', error);
                    }
                }
            });
        };
    };
    player.load_and_play = function(track) {
        this.clear();
        this.player.cueVideoById(track.link.substring(8));
        this.player.playVideo();
        this.track = track;
    };
    player.play = function() {
        this.player.playVideo();
    };
    player.pause = function() {
        this.player.pauseVideo();
    };
    player.stop = function() {
        this.player.stopVideo();
        $rootScope.$broadcast('paused');
    };
    player.clear = function() {
        this.stop();
        this.player.clearVideo();
        this.track = undefined;
    };
    player.set_volume = function(value) {
        this.player.setVolume(value);
    };
    player.seek = function(value) {
        this.player.seekTo(value);
    };
    player.get_current_time = function(value) {
        return (this.player.getPlayerState() === -1) ? 0 : this.player.getCurrentTime();
    };
    player.get_duration = function(value) {
        return this.player.getDuration();
    };

    return player;
});


app.factory('SoundCloudPlayerFactory', function($rootScope) {

    var player = {};
    player.create = function(css_selector) {
        var self = this;

        // Load SoundCloud API
        $.when(
            $.getScript('http://connect.soundcloud.com/sdk.js'),
            $.getScript('https://w.soundcloud.com/player/api.js'),
            $.Deferred(function(deferred) {
                $(deferred.resolve);
            })
        ).done(function() {
            // Start player
            SC.initialize({
                client_id: "ac0c94880338e855de3743d143368221"
            });

            $('<iframe id="' + css_selector + '" src="https://w.soundcloud.com/player/?url=https://api.soundcloud.com/tracks/39804767&show_artwork=false&liking=false&sharing=false&auto_play=false" scrolling="no" frameborder="no"></iframe>').appendTo('body');

            self.player = SC.Widget(css_selector);

            self.player.bind(SC.Widget.Events.READY, function() {
                $rootScope.$broadcast('_ready');
            });
            self.player.bind(SC.Widget.Events.PLAY, function() {
                $rootScope.$broadcast('playing');
            });
            self.player.bind(SC.Widget.Events.PAUSE, function() {
                $rootScope.$broadcast('paused');
            });
            self.player.bind(SC.Widget.Events.FINISH, function() {
                $rootScope.$broadcast('ended');
            });
            self.player.bind(SC.Widget.Events.PLAY_PROGRESS, function() {
                self.player.getPosition(function(value) {
                    if (value === 0)
                        $rootScope.$broadcast('loadstart');
                    self.player_position = value / 1000;
                });
                self.player.getDuration(function(value) { self.player_duration = value / 1000; });
            });
            self.player.bind(SC.Widget.Events.ERROR, function() {
                $rootScope.$broadcast('error');
            });
        });
    };
    player.load_and_play = function(track) {
        this.clear();
        var self = this;
        this.player.load('http://api.soundcloud.com/tracks/' + track.link.substring(11), { callback: function () { self.player.play(); }});
        this.track = track;
    };
    player.play = function() {
        this.player.play();
    };
    player.pause = function() {
        this.player.pause();
    };
    player.stop = function() {
        this.player.pause();
        this.player.seekTo(0);
    };
    player.clear = function() {
        this.track = undefined;
    };
    player.set_volume = function(value) {
        this.player.setVolume(value / 100);
    };
    player.seek = function(value) {
        this.player.seekTo(value * 1000);
    };
    player.get_current_time = function(value) {
        return this.player_position;
    };
    player.get_duration = function(value) {
        return this.player_duration;
    };

    return player;
});


app.service('MusicService', function($rootScope, jPlayerFactory, YoutubePlayerFactory, SoundCloudPlayerFactory) {

    // Initialize players
    jPlayerFactory.create('#player-core', '#player-ui');
    YoutubePlayerFactory.create('yt_player');
    SoundCloudPlayerFactory.create('sc_player');

    this.players_ready = 0;
    this.players_total = 3;

    this.playing = false;
    this.players = {
        'jplayer': jPlayerFactory,
        'youtube': YoutubePlayerFactory,
        'soundcloud': SoundCloudPlayerFactory
    };

    // Playlist status
    this.playlists = {};
    this.name = undefined;
    this.index = 0;

    // Player methods
    this.get_player_type = function() {
        var link = (this.track && this.track.link) || '';
        return (link.indexOf('youtube:') === 0) ? 'youtube' : ((link.indexOf('soundcloud:') === 0) ? 'soundcloud' : 'jplayer');
    };
    this.get_player = function() {
        return this.players[this.get_player_type()];
    };
    this.load_and_play = function(params) {
        // Stop currently playing track
        if (this.track)
            this.stop();

        if (params.index !== undefined && params.name) {
            // Load track from playlist
            this.track = this.playlists[params.name].tracks[params.index];
            this.name = params.name;
            this.index = params.index;
        }
        else {
            // Load without a playlist
            this.track = params.track;
            this.name = this.index = undefined;
        }

        this.get_player().load_and_play(this.track);
    };
    this.play = function() {
        this.get_player().play();
    };
    this.pause = function() {
        this.get_player().pause();
    };
    this.stop = function() {
        this.get_player().stop();
    };
    this.seek = function(position) {
        this.get_player().seek(position);
    };
    this.get_current_time = function() {
        return this.get_player().get_current_time();
    };
    this.get_duration = function() {
        return this.get_player().get_duration();
    };
    this.set_volume = function(volume) {
        Object.keys(this.players).forEach(function(type) {
            this.players[type].set_volume(volume);
        }, this);
        this.volume = volume;
    };

    // Playlist methods
    this.set_playlists = function(playlists) {
        this.playlists = playlists;
    };
    this.get_playlists = function() {
        return this.playlists;
    };
    this.add_playlist = function(playlist_name, playlist) {
        this.playlists[playlist_name] = playlist;
    };
    this.delete_playlist = function(playlist_name) {
        if (Object.keys(this.playlists).length > 1) {
            delete this.playlists[playlist_name];
            return true;
        }
        return false;
    };
    this.reposition = function(playlist_name, index, step) {
        var playlist = this.playlists[playlist_name].tracks;
        var item = playlist[index];
        playlist.splice(index, 1);
        playlist.splice(index - step, 0, item);
        if (this.index < index && (this.index + step) < index) {
            this.index += step;
        }
        if (this.index < index && (this.index + step) > index) {
            this.index -= step;
        }
    };
    this.next = function() {
        var next_index = (this.index + 1 < this.playlists[this.name].tracks.length) ? this.index + 1 : 0;

        if(next_index > 0) {
            this.load_and_play({name: this.name, index: next_index});
            this.index = next_index;
        }
    };
    this.previous = function() {
        var previous_index = (this.index - 1 >= 0) ? this.index - 1 : this.playlists[this.name].tracks.length - 1;

        if (previous_index < this.playlists[this.name].tracks.length - 1) {
            this.load_and_play({name: this.name, index: previous_index});
            this.index = previous_index;
        }
    };
    this.add = function(playlist_name, track) {
        this.playlists[playlist_name].tracks.push(track);
    };
    this.remove = function(playlist_name, index) {
        this.playlists[playlist_name].tracks.splice(index, 1);
    };

    var self = this;
    $rootScope.$on('playing', function(event) {
        self.playing = true;
    });
    $rootScope.$on('paused', function(event) {
        self.playing = false;
    });
    $rootScope.$on('ended', function(event) {
        self.playing = false;
    });
    $rootScope.$on('_ready', function(event) {
        self.players_ready += 1
        if (self.players_ready === self.players_total) {
            $rootScope.$broadcast('ready');
        }
    });
});


app.service('ApiService', function($http, $cookies, HelperService) {

    this.api_base = 'http://musesync.ewi.tudelft.nl:8000/api';
    this.api_session = this.api_base + '/session';
    this.api_playlists = this.api_base + '/playlists?token={0}&search={1}';
    this.api_tracks = this.api_base + '/tracks?query={0}&id={1}&offset={2}';
    this.api_recommend = this.api_base + '/recommend?token={0}&name={1}&offset={2}';
    this.api_clicklog = this.api_base + '/clicklog?token={0}';
    this.api_waveform = this.api_base + '/waveform?id={0}';
    this.api_info = this.api_base + '/info';

    this.init = function() {
        var port = location.port || (location.protocol === 'https:' ? '443' : '80');
        this.cookie_name = 'token' + port;

        this.token = HelperService.getParameterByName('token') || $cookies.get(this.cookie_name);
        if (this.token) {
            // Remove trailing '/' chars
            this.token = this.token.replace(/\/+$/g, '');
        }
    };
    this.do_get = function(url, ignore_errors) {
        return $http.get(url).then(function successCallback(response) {
            return response.data;
        }, ignore_errors ? null : this.show_and_throw_error);
    };
    this.do_post = function(url, data, ignore_errors) {
        return $http.post(url, data).then(function successCallback(response) {
            return response.data;
        }, ignore_errors ? null : this.show_and_throw_error);
    };
    this.show_and_throw_error = function(response) {
        var message = (response.data && response.data.error) ? 'Got error from server (' + response.data.error + ')' : 'Failed to contact Billy server';
        HelperService.alert(message);
        throw response;
    };
    this.new_session = function(ignore_errors) {
        var self = this;
        return this.do_get(this.api_session, ignore_errors).then(function(data) {
            self.token = data.token;
            var now = new Date();
            now.setYear(now.getYear() + 10);
            $cookies.put(self.cookie_name, self.token);
            return data;
        });
    };
    this.get_playlists = function(ignore_errors) {
        return this.do_get(HelperService.formatString(this.api_playlists , this.token, ''), ignore_errors);
    };
    this.post_playlists = function(playlists, ignore_errors) {
        return this.do_post(HelperService.formatString(this.api_playlists, this.token, ''), JSON.stringify(playlists), ignore_errors);
    };
    this.get_tracks = function(query, offset, ignore_errors) {
        return this.do_get(HelperService.formatString(this.api_tracks, encodeURIComponent(query), '', offset), ignore_errors);
    };
    this.get_recommendation = function(name, offset, ignore_errors) {
        return this.do_get(HelperService.formatString(this.api_recommend, this.token, name, offset), ignore_errors);
    };
    this.post_clicklog = function(clicklog, ignore_errors) {
        return this.do_post(HelperService.formatString(this.api_clicklog, this.token, ''), clicklog, ignore_errors);
    };
    this.get_waveform = function(track_id, ignore_errors) {
        return this.do_get(HelperService.formatString(this.api_waveform, track_id, ''), ignore_errors);
    };
    this.get_info = function(ignore_errors) {
        return this.do_get(this.api_info, ignore_errors);
    };

    this.init();
});


app.service('HelperService', function($uibModal) {

    this.padNumber = function(number, size) {
        var s = String(number);
        while (s.length < (size || 2))
            s = "0" + s;
        return s;
    };
    this.formatTime = function(time) {
        if (time >= 60)
            return this.padNumber(Math.floor(time / 60), 2) + ':' + this.padNumber(Math.round(time % 60), 2);
        else
            return '00:' + this.padNumber(Math.round(time), 2);
    };
    this.getParameterByName = function(name) {
        name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
        var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
            results = regex.exec(location.search);
        return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
    };
    this.replaceParameter = function(url, name, value) {
        var pattern = new RegExp('\\b(' + name + '=).*?(&|$)');
        if (url.search(pattern) >= 0) {
            return url.replace(pattern, '$1' + value + '$2');
        }
        return url + (url.indexOf('?') > 0 ? '&' : '?') + name + '=' + value;
    };
    this.formatString = function() {
        var args = Array.prototype.slice.call(arguments);
        var str = args.shift();
        return str.replace(/\{(\d+)\}/g, function (m, n) { return args[n]; });
    };
    this.alert = function(message) {
        $uibModal.open({
            animation: false,
            templateUrl: 'app/views/alert_modal.html',
            controller: function($scope) {
                $scope.message = message;
            },
        });
    };

});
