app.directive('clipboardCopy', function() {
    return {
        restrict: 'A',
        link: function (scope, element, attrs) {
            element.bind('click', function (e) {
                var $temp = $('<input>');
                $('body').append($temp);
                $temp.val(attrs.clipboardCopy).select();
                document.execCommand('copy');
                $temp.remove();
            });
        }
    };
});
