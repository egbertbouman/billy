app.filter('underscoreless', function () {
  return function (input) {
      return input.replace(/_/g, ' ');
  };
});
