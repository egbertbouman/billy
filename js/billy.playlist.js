/*
 * Playlist Object for the jPlayer Plugin
 * http://www.jplayer.org
 *
 * Copyright (c) 2009 - 2014 Happyworm Ltd
 * Licensed under the MIT license.
 * http://www.opensource.org/licenses/MIT
 *
 * Author: Mark J Panaghiston
 * Version: 2.4.1
 * Date: 19th November 2014
 *
 * Requires:
 *  - jQuery 1.7.0+
 *  - jPlayer 2.8.2+
 *
 *
 * Modified for use with Billy
 * 
 */

/*global jPlayerPlaylist:true */

(function($, undefined) {

    jPlayerPlaylist = function(player, cssSelector, playlist, options) {
        var self = this;

        this.current = 0;
        this.loop = false; // Flag used with the jPlayer repeat event
        this.removing = false; // Flag is true during remove animation, disabling the remove() method until complete.
        this.player = player;

        this.cssSelector = $.extend({}, this._cssSelector, cssSelector); // Object: Containing the css selectors for jPlayer and its cssSelectorAncestor
        this.options = $.extend(true, {}, this._options, options); // Object: The jPlayer constructor options for this playlist and the playlist options

        this.playlist = playlist;

        // Setup the css selectors for the extra interface items used by the playlist.
        this.cssSelector.playlist = " .jp-playlist";
        this.cssSelector.next = this.cssSelector.cssSelectorAncestor + " .jp-next";
        this.cssSelector.previous = this.cssSelector.cssSelectorAncestor + " .jp-previous";

        // Override the cssSelectorAncestor given in options
        this.options.cssSelectorAncestor = this.cssSelector.cssSelectorAncestor;

        // Override the default repeat event handler
        this.options.repeat = function(event) {
            self.loop = event.jPlayer.options.loop;
        };

        // Create a ready event handler to initialize the playlist
        player.listen('ready', function() {
            self._init();
        });

        // Create an ended event handler to move to the next item
        player.listen('ended', function() {
            self.next();
        });

        // Create a play event handler to pause other instances
        player.listen('play', function() {
            $(this).jPlayer("pauseOthers");
        });

        // Create click handlers for the extra buttons that do playlist functions.
        $(this.cssSelector.previous).click(function(e) {
            e.preventDefault();
            self.previous();
        });

        $(this.cssSelector.next).click(function(e) {
            e.preventDefault();
            self.next();
        });

        // Remove the empty <li> from the page HTML. Allows page to be valid HTML, while not interfereing with display animations
        $(this.cssSelector.playlist + " ul").empty();

        // Create .on() handlers for the playlist items along with the free media and remove controls.
        this._createItemHandlers();
    };

    jPlayerPlaylist.prototype = {
        _cssSelector: { // static object, instanced in constructor
            jPlayer: "#jquery_jplayer_1",
            cssSelectorAncestor: "#jp_container_1"
        },
        _options: { // static object, instanced in constructor
            playlistOptions: {
                autoPlay: false,
                loopOnPrevious: false,
                shuffleOnLoop: true,
                enableRemoveControls: true,
                displayTime: 'slow',
                addTime: 'fast',
                removeTime: 'fast',
                shuffleTime: 'slow',
                itemClass: "jp-playlist-item",
                freeGroupClass: "jp-free-media",
                freeItemClass: "jp-playlist-item-free",
                removeItemClass: "jp-playlist-item-remove",
                moveupItemClass: "jp-playlist-item-moveup",
                movedownItemClass: "jp-playlist-item-movedown"
            }
        },
        option: function(option, value) { // For changing playlist options only
            if(value === undefined) {
                return this.options.playlistOptions[option];
            }

            this.options.playlistOptions[option] = value;

            switch(option) {
                case "enableRemoveControls":
                    this._updateControls();
                    break;
                case "itemClass":
                case "freeGroupClass":
                case "freeItemClass":
                case "removeItemClass":
                    this._refresh(true); // Instant
                    this._createItemHandlers();
                    break;
            }
            return this;
        },
        _init: function() {
            var self = this;
            this._refresh(function() {
                if(self.options.playlistOptions.autoPlay) {
                    self.play(self.current);
                } else {
                    self.select(self.current);
                }
            });
        },
        _refresh: function(instant) {
            /* instant: Can be undefined, true or a function.
             *  undefined -> use animation timings
             *  true -> no animation
             *  function -> use animation timings and excute function at half way point.
             */
            var self = this;

            if(instant && !$.isFunction(instant)) {
                $(this.cssSelector.playlist + " ul").empty();
                $.each(this.playlist, function(i) {
                    $(self.cssSelector.playlist + " ul").append(self._createListItem(self.playlist[i]));
                });
                this._updateControls();
            } else {
                var displayTime = $(this.cssSelector.playlist + " ul").children().length ? this.options.playlistOptions.displayTime : 0;

                $(this.cssSelector.playlist + " ul").slideUp(displayTime, function() {
                    var $this = $(this);
                    $(this).empty();
                    
                    $.each(self.playlist, function(i) {
                        $this.append(self._createListItem(self.playlist[i]));
                    });
                    self._updateControls();
                    if($.isFunction(instant)) {
                        instant();
                    }
                    if(self.playlist.length) {
                        $(this).slideDown(self.options.playlistOptions.displayTime);
                    } else {
                        $(this).show();
                    }
                });
            }
        },
        _createListItem: function(media) {
            var self = this;

                        var listItem = '<li class="list-group-item shorten" data-track-id="' + media.id + '">';

            // Create play/remove controls
            listItem += '<div class="pull-right m-l btn-group">';
            listItem += '<a href="#" class="m-r-sm ' + this.options.playlistOptions.moveupItemClass +'"><span class="glyphicon glyphicon-circle-arrow-up"></span></a>';
            listItem += '<a href="#" class="m-r-sm ' + this.options.playlistOptions.movedownItemClass +'"><span class="glyphicon glyphicon-circle-arrow-down"></span></a>';
            listItem += '<a href="#" onclick="return false;" data-toggle="popover" data-placement="bottom" tabindex="0" data-trigger="focus" title="Tags" data-content="' + billy.create_tags_popover(media['musicinfo']) + '" class="m-r-sm"><span class="glyphicon glyphicon-info-sign"></span></a>';
            listItem += '<a href="#" onclick="window.location = \'' + billy.api_download.format(media.id) + '\'; return false;" class="m-r-sm"><span class="glyphicon glyphicon-record"></span></a>';
            listItem += '<a href="#" class="m-r-sm ' + this.options.playlistOptions.itemClass +'"><span class="glyphicon glyphicon-play-circle"></span></a>';
            listItem += '<a href="#" class="m-r-sm ' + this.options.playlistOptions.removeItemClass +'"><span class="glyphicon glyphicon-remove-circle"></span></a>';
            listItem += '</div>';

            // Create links to free media
            if(media.free) {
                var first = true;
                listItem += "<span class='" + this.options.playlistOptions.freeGroupClass + "'>(";
                $.each(media, function(property,value) {
                    if($.jPlayer.prototype.format[property]) { // Check property is a media format.
                        if(first) {
                            first = false;
                        } else {
                            listItem += " | ";
                        }
                        listItem += "<a class='" + self.options.playlistOptions.freeItemClass + "' href='" + value + "' tabindex='-1'>" + property + "</a>";
                    }
                });
                listItem += ")</span>";
            }

            // The title is given next in the HTML otherwise the float:right on the free media corrupts in IE6/7
            listItem += '<a class="img-thumbnail cover-art ' + this.options.playlistOptions.itemClass +'" href="#"><span class="rollover"></span><img alt="" src=' + media.image + '></a>';
            listItem += media.title;
            listItem += "</li></a>";

            return listItem;
        },
        _createItemHandlers: function() {
            var self = this;
            // Create live handlers for the playlist items
            $(this.cssSelector.playlist).off("click", "a." + this.options.playlistOptions.itemClass).on("click", "a." + this.options.playlistOptions.itemClass, function(e) {
                e.preventDefault();
                var index = $(this).parents('.list-group-item').index();
                if(self.current !== index) {
                    self.play(index);
                } else {
                    self.player.play();
                }
            });

            // Create live handlers that disable free media links to force access via right click
            $(this.cssSelector.playlist).off("click", "a." + this.options.playlistOptions.freeItemClass).on("click", "a." + this.options.playlistOptions.freeItemClass, function(e) {
                e.preventDefault();
                $(this).parent().parent().find("." + self.options.playlistOptions.itemClass).click();
            });

            // Create live handlers for the remove controls
            $(this.cssSelector.playlist).off("click", "a." + this.options.playlistOptions.removeItemClass).on("click", "a." + this.options.playlistOptions.removeItemClass, function(e) {
                e.preventDefault();
                var index = $(this).parent().parent().index();
                self.remove(index);
            });
            // Handlers for reordering playlist itens
            $(this.cssSelector.playlist).off("click", "a." + this.options.playlistOptions.moveupItemClass).on("click", "a." + this.options.playlistOptions.moveupItemClass, function(e) {
                e.preventDefault();
                var index = $(this).parent().parent().index();
                self.position(index, 1);
            });
            $(this.cssSelector.playlist).off("click", "a." + this.options.playlistOptions.movedownItemClass).on("click", "a." + this.options.playlistOptions.movedownItemClass, function(e) {
                e.preventDefault();
                var index = $(this).parent().parent().index();
                self.position(index, -1);
            });
        },
        _updateControls: function() {
            if(this.options.playlistOptions.enableRemoveControls) {
                $(this.cssSelector.playlist + " ." + this.options.playlistOptions.removeItemClass).show();
            } else {
                $(this.cssSelector.playlist + " ." + this.options.playlistOptions.removeItemClass).hide();
            }

            $("[data-toggle=popover]").popover({ html : true, container: 'body'});
        },
        _highlight: function(index) {
            if(this.playlist.length && index !== undefined) {
                $(this.cssSelector.playlist + " .jp-playlist-current").removeClass("jp-playlist-current");
                $(this.cssSelector.playlist + " li:nth-child(" + (index + 1) + ")").addClass("jp-playlist-current").find(".jp-playlist-item").addClass("jp-playlist-current");
            }
        },
        setPlaylist: function(playlist) {
            this.playlist = playlist;
            this._init();
        },
        position: function(index, step) {
            var item = this.playlist[index];
            this.playlist.splice(index, 1);
            this.playlist.splice(index - step, 0, item);

            var current_item = $(".jp-playlist-current");

            if (step > 0)
                $(this.cssSelector.playlist + " li:nth-child(" + (index + 1) + ")").after($(this.cssSelector.playlist + " li:nth-child(" + (index + 1 - step) + ")"));
            else
                $(this.cssSelector.playlist + " li:nth-child(" + (index + 1) + ")").before($(this.cssSelector.playlist + " li:nth-child(" + (index + 1 - step) + ")"));

            this.current = current_item.parents('.list-group-item').index();
        },
        add: function(media, playNow) {
            $(this.cssSelector.playlist + " ul").append(this._createListItem(media)).find("li:last-child").hide().slideDown(this.options.playlistOptions.addTime);
            this._updateControls();
            this.playlist.push(media);

            if(playNow) {
                this.play(this.playlist.length - 1);
            } else {
                if(this.playlist.length === 1) {
                    this.select(0);
                }
            }
        },
        remove: function(index) {
            var self = this;

            if(index === undefined) {
                this._initPlaylist([]);
                this._refresh(function() {
                    self.player.clear();
                });
                return true;
            } else {

                if(this.removing) {
                    return false;
                } else {
                    index = (index < 0) ? self.playlist.length + index : index; // Negative index relates to end of array.
                    if(0 <= index && index < this.playlist.length) {
                        this.removing = true;

                        $(this.cssSelector.playlist + " li:nth-child(" + (index + 1) + ")").slideUp(this.options.playlistOptions.removeTime, function() {
                            $(this).remove();

                            self.playlist.splice(index, 1);

                            billy.save_to_server();

                            if(self.playlist.length) {
                                if(index === self.current) {
                                    self.current = (index < self.playlist.length) ? self.current : self.playlist.length - 1; // To cope when last element being selected when it was removed
                                    self.select(self.current);
                                } else if(index < self.current) {
                                    self.current--;
                                }
                            } else {
                                self.player.clear();
                                self.current = 0;
                                self._updateControls();
                            }

                            self.removing = false;
                        });
                    }
                    return true;
                }
            }
        },
        select: function(index) {
            index = (index < 0) ? this.playlist.length + index : index; // Negative index relates to end of array.
            if(0 <= index && index < this.playlist.length) {
                this.current = index;
                this._highlight(index);

                var track = this.playlist[this.current];
                this.player.load(track);

            } else {
                this.current = 0;
            }
            $('#results .list-group').children(".jp-playlist-current").removeClass("jp-playlist-current");
        },
        play: function(index) {
            index = (index < 0) ? this.playlist.length + index : index; // Negative index relates to end of array.
            var track = this.playlist[index];

            if(0 <= index && index < this.playlist.length) {
                if(this.playlist.length) {
                    this.select(index);
                    this.player.load_and_play(track);
                }
            } else if(index === undefined) {
                this.player.load_and_play(track);
            }
        },
        pause: function() {
            this.player.pause(track);
        },
        next: function() {
            var index = (this.current + 1 < this.playlist.length) ? this.current + 1 : 0;

            if(this.loop) {
                this.play(index);
            } else {
                // The index will be zero if it just looped round
                if(index > 0) {
                    this.play(index);
                }
            }
        },
        previous: function() {
            var index = (this.current - 1 >= 0) ? this.current - 1 : this.playlist.length - 1;

            if(this.loop && this.options.playlistOptions.loopOnPrevious || index < this.playlist.length - 1) {
                this.play(index);
            }
        },
    };
})(jQuery);
