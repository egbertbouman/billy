var gulp = require('gulp'),
    del = require('del'),
    jshint = require('gulp-jshint'),
    uglify = require('gulp-uglify');
    minifyHtml = require('gulp-minify-html'),
    minifyCss = require('gulp-minify-css'),
    rev = require('gulp-rev'),
    ngAnnotate = require('gulp-ng-annotate'),
    templateCache = require('gulp-angular-templatecache'),
    addsrc = require('gulp-add-src'),
    useref = require('gulp-useref'),
    gulpif = require('gulp-if'),
    concat = require('gulp-concat'),
    lazypipe = require('lazypipe'),
    revReplace = require('gulp-rev-replace');

var jsTask = lazypipe()
    .pipe(addsrc.append, 'tmp/templates.js')
    .pipe(concat, 'assets/js/app.js')
    .pipe(ngAnnotate)
    .pipe(uglify)
    .pipe(rev);

var cssTask = lazypipe()
    .pipe(minifyCss)
    .pipe(rev);

gulp.task('clean', function () {
    return del(['dist']);
});

gulp.task('jshint', function() {
    return gulp.src(['app/*.js', 'assets/js/*.js'])
        .pipe(jshint())
        .pipe(jshint.reporter('default'));
});

gulp.task('build-tmpls', ['clean'], function () {
    return gulp.src('app/views/*.html')
        .pipe(minifyHtml({quotes: true}))
        .pipe(templateCache({module: 'billy', root: 'app/views/'}))
        .pipe(gulp.dest('tmp'));
});

gulp.task('build-js-css-html', ['build-tmpls'], function () {
    return gulp.src('index.html')
        .pipe(useref())
        .pipe(gulpif('*.js', jsTask()))
        .pipe(gulpif('*.css', cssTask()))
        .pipe(revReplace())
        .pipe(gulp.dest('dist'));
});

gulp.task('build-img', ['clean'], function () {
    return gulp.src(['assets/img/**'])
        .pipe(gulp.dest('dist/assets/img'));
})

gulp.task('build-fonts', ['clean'], function () {
    return gulp.src(['assets/fonts/**'])
        .pipe(gulp.dest('dist/assets/fonts'));
})

gulp.task('remove-tmp', ['build-js-css-html'], function () {
    return del(['tmp']);
});

gulp.task('default', ['clean', 'jshint', 'build-tmpls', 'build-js-css-html', 'remove-tmp', 'build-img', 'build-fonts']);

