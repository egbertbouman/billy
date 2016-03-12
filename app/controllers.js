app.controller('PlaylistCtrl', function ($scope, $rootScope, $timeout, $cookies, $uibModal, HelperService, MusicService, ApiService) {

    $scope.tabs = {};
    $scope.musicservice = MusicService;

    var load_playlists = function() {
        ApiService.get_playlists(true).then(function success(data) {
            // Share playlists between this controller and MusicService
            MusicService.set_playlists($scope.playlists = data);
            if ($.isEmptyObject(data))
                $scope.playlist_modal();
        }, function error(response) {
            if (response.status == 404 && ApiService.token !== undefined) {
                document.body.innerHTML = '';
                HelperService.alert('Failed to find Billy session');
            }
            else {
                // Create a new Billy session
                ApiService.new_session().then(function (data) {
                    MusicService.set_playlists($scope.playlists = {});
                    $scope.playlist_modal();
                });
            }
        });
    };
    var save_playlists = function() {
        var playlists = jQuery.extend(true, {}, $scope.playlists);

        Object.keys(playlists).forEach(function (name) {
            var playlist = playlists[name];
            var track_ids = [];
            playlist.tracks.forEach(function (track) {
                track_ids.push(track._id);
            });
            playlist.tracks = track_ids;
        });

        // Store playlists in remote database
        ApiService.post_playlists(playlists);
    };
    $scope.export_playlists = function() {
        var blob = new Blob([JSON.stringify($scope.playlists)], { type:"application/json;charset=utf-8;" });
        var download_link = angular.element('<a></a>');
        download_link.attr('href', window.URL.createObjectURL(blob));
        download_link.attr('download', 'playlists.json');
        download_link[0].click();
    };
    $scope.import_playlists = function() {
        var file = document.getElementById('file').files[0];

        if (file) {
            var reader = new FileReader();
            reader.readAsText(file, 'UTF-8');
            reader.onloadend = function(event) {
                var playlists = JSON.parse(event.target.result);

                // Add playlists
                var skipped = [];
                for (var name in playlists) {
                    if (name in $scope.playlists) {
                        skipped.push(name);
                        continue;
                    }
                    $scope.playlists[name] = playlists[name];
                }
                if (skipped.length > 0)
                    HelperService.alert('You already have playlist(s) with the following name(s): ' + skipped.join(', ') + '. Since playlist names have to be unique, these will not be imported.');
            };
            reader.onerror = function (evt) {
                HelperService.alert('Could not read file!');
            };
        }
    };
    $scope.playlist_modal = function () {
        var modalInstance = $uibModal.open({
            animation: false,
            templateUrl: 'app/views/playlist_modal.html',
            controller: 'PlaylistModalCtrl',
        });
        modalInstance.result.then(function success(result) {
            result.tracks = [];
            MusicService.add_playlist(result.name, result);
        }, function error() {
        });
    };
    $scope.delete_playlist = function(playlist_name) {
        if (!MusicService.delete_playlist(playlist_name))
            HelperService.alert('You should have at least one playlist. Please create a new one before deleting this one.');
    };
    $scope.next = function() {
        MusicService.next();
    };
    $scope.previous = function() {
        MusicService.previous();
    };
    $scope.move_up = function(playlist_name, index) {
        MusicService.reposition(playlist_name, index, 1);
    };
    $scope.move_down = function(playlist_name, index) {
        MusicService.reposition(playlist_name, index, -1);
    };
    $scope.load_and_play = function(playlist_name, index) {
        MusicService.load_and_play({name: playlist_name, index: index});
    };
    $scope.add = function(track) {
        MusicService.add(current_playlist, track);
        $timeout(function() { $rootScope.$broadcast('recommend', current_playlist); }, 5000);
    };
    $scope.remove = function(playlist_name, index) {
        MusicService.remove(playlist_name, index);
        $timeout(function() { $rootScope.$broadcast('recommend', playlist_name); }, 5000);
    };

    var current_playlist;
    $scope.$watch('tabs', function(new_value, old_value) {
        // Perform recommendation when user switches playlist tabs
        Object.keys(new_value).forEach(function(playlist_name) {
            if ((new_value[playlist_name] || {}).active && !(old_value[playlist_name] || {}).active) {
                $rootScope.$broadcast('recommend', playlist_name);
                current_playlist = playlist_name;
            }
        });
    }, true);
    $scope.$watch('playlists', function(new_value, old_value) {
        if (old_value !== undefined)
            save_playlists();
    }, true);

    $scope.$on('loadstart', function(event) {
        $('#yt_player').toggle((MusicService.get_player_type() === 'youtube'));
        if (MusicService.get_player_type() === 'soundcloud')
            MusicService.set_volume(MusicService.volume);
    });
    $scope.$on('ended', function(event) {
        $scope.next();
    });
    $scope.$on('add', function(event, track) {
        $scope.add(track);
    });

    load_playlists();
});


app.controller('PlaylistModalCtrl',  function ($scope, $uibModalInstance) {

    $scope.functions = {
        'foreground': false,
        'background': false,
        'action': false
    };

    $scope.save = function () {
        $scope.name_popover = (!$scope.name);
        $scope.description_popover = (!$scope.description);

        if (!$scope.name || !$scope.description)
            return;

        // TODO: enforce unique name

        var functions = [];
        Object.keys($scope.functions).forEach(function(playlist_name) {
            if ($scope.functions[playlist_name])
                functions.push(playlist_name);
        });

        $uibModalInstance.close({
            name: $scope.name,
            description: $scope.description,
            functions: functions,
            type: $scope.identity_playlist ? 'identity' : 'user'
        });
    };

    $scope.close = function () {
        $uibModalInstance.dismiss('cancel');
    };
});


app.controller('ResultCtrl', function ($rootScope, $scope, MusicService, ApiService) {

    $scope.tabs = {
        search: {
            active: false,
            current_page: 1,
            page_size: 0,
            results: []
        },
        recommendation: {
            active: true,
            current_page: 1,
            page_size: 0,
            results: []
        }
    };
    $scope.musicservice = MusicService;

    function search() {
        var offset = ($scope.tabs.search.current_page - 1) * $scope.tabs.search.page_size;
        ApiService.get_tracks($scope.query, offset).then(function(data) {
            $scope.tabs.search.total_items = data.total;
            $scope.tabs.search.page_size = data.page_size;
            angular.copy(data.results, $scope.tabs.search.results);
            // Switch to search tab
            $scope.tabs.search.active = true;
        });
    }
    function recommend() {
        var offset = ($scope.tabs.recommendation.current_page - 1) * $scope.tabs.recommendation.page_size;
        ApiService.get_recommendation($scope.playlist_name, offset).then(function(data) {
            $scope.tabs.recommendation.total_items = data.total;
            $scope.tabs.recommendation.page_size = data.page_size;
            angular.copy(data.results, $scope.tabs.recommendation.results);
        });
    }

    $scope.load_and_play = function(track) {
        MusicService.load_and_play({track: track});
    };
    $scope.add = function(track) {
        $rootScope.$broadcast('add', track);
    };
    $scope.page_changed = function() {
        if ($scope.tabs.search.active)
            search();
        else
            recommend();
    };

    $scope.$on('search', function(event, query) {
        $scope.query = query;
        search();
    });
    $scope.$on('recommend', function(event, playlist_name) {
        $scope.playlist_name = playlist_name;
        recommend();
    });

});


app.controller('PlayerCtrl', function ($scope, $rootScope, $interval, HelperService, MusicService) {

    $scope.musicservice = MusicService;
    $scope.load_and_play = function(track) { MusicService.load_and_play({track: track}); };
    $scope.play = function() { MusicService.play(); };
    $scope.pause = function() { MusicService.pause(); };
    $scope.stop = function() { MusicService.stop(); };

    $scope.next = function() {
        MusicService.next();
    };
    $scope.previous = function() {
        MusicService.previous();
    };
    $scope.timeline_click = function(e) {
        var width = $(e.currentTarget).width();
        var pos = e.offsetX / width;
        MusicService.seek(pos * $scope.duration);
    };
    $scope.volume_click = function(e) {
        var width = $(e.currentTarget).width();
        var volume = (e.offsetX / width) * 100;
        MusicService.set_volume(volume);
        $scope.current_volume = volume;
    };

    $scope.current_time = 0;
    $scope.current_volume = 80;
    $interval(function() {
        var time = MusicService.get_current_time();
        $scope.current_time = time;
        $scope.current_time_str = HelperService.formatTime(time);

        time = MusicService.get_duration();
        $scope.duration = time || 1;
        $scope.duration_str = HelperService.formatTime(time);

        $scope.playing = MusicService.playing;
    }, 1000);
});

app.controller('HeaderCtrl', function ($rootScope, $scope, HelperService, ApiService) {

    $scope.url = HelperService.replaceParameter(window.location.href, 'token', ApiService.token);

    $scope.search = function() {
        $rootScope.$broadcast('search', $scope.query);
    };
    $scope.status = function() {
        ApiService.get_info().then(function(data) {
            $scope.status = data;
            $scope.status.info.total_tracks = 0;
            Object.keys($scope.status.info.num_tracks).forEach(function(key, index) {
                $scope.status.info.total_tracks += $scope.status.info.num_tracks[key];
            });
        });
    };

    $scope.$watch('status_shown', function(new_value, old_value) {
        if (new_value)
            $scope.status();
    });
});
