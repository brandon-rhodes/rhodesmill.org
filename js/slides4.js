
/* https://stackoverflow.com/a/14786759/85360 */

function loadScript(url, callback) {
   var head = document.getElementsByTagName('head')[0];
   var script = document.createElement('script');
   script.type = 'text/javascript';
   script.src = url;

   script.onreadystatechange = callback;
   script.onload = callback;

   head.appendChild(script);
}

function setup() {
    /*global*/ $slides = $('.slide');
    $slides.hide();
    current_slide_n = -1;
    last_slide_change = null;

    var select_slide = function(n) {
        window.location = '#' + n + '';
    }

    var select_slide_based_on_hash = function() {
        var n = location.hash ? parseInt(location.hash.substring(1)) : 0;
        if (current_slide_n != -1)
            $slides.eq(current_slide_n).hide();
        current_slide_n = n;
        $slides.eq(current_slide_n).show();

        /* Remember when the slide was last changed. */
        last_slide_change = new Date();

        /* Update the status line immediately. */
        timer_update();
    }

    window.onhashchange = select_slide_based_on_hash;

    var leftKeys = [33, 37, 38, 66];
    var rightKeys = [32, 34, 39, 40, 70];

    $('html').bind('keydown', function(event) {
        if (rightKeys.indexOf(event.keyCode) !== -1) {
            event.preventDefault();
            if (current_slide_n < $slides.length - 1)
                select_slide(current_slide_n + 1);
        } else if (leftKeys.indexOf(event.keyCode) != -1) {
            event.preventDefault();
            if (current_slide_n > 0)
                select_slide(current_slide_n - 1);
        }
    });

    /* Timer */

    var timer_update = function() {
        timer_div.removeClass('emergency');

        var now = new Date();
        if (!endtime) {
            readout = 'Time ' + now.toTimeString().substring(0, 5) +
                '<br>' + current_slide_n + '/' + ($slides.length - 1);
        } else {
            var left = Math.floor((endtime - now) / 1000);
            var leftm = Math.floor(left / 60);
            var lefts = left % 60;
            readout = ('' + current_slide_n + '/' + ($slides.length - 1) +
                       '<br>' + leftm + 'm' + lefts + 's');
            if (last_slide_change) {
                var til_end = endtime - last_slide_change;
                var slides_left = $slides.length - current_slide_n;
                var time_per_slide = til_end / slides_left;
                var ss = (last_slide_change - now) + time_per_slide;
                readout += ('<br>' + Math.floor(ss / 1000) + 's');
                if (ss < 0)
                    timer_div.addClass('emergency');
            }
        }
        timer_div.html(readout);
    }

    var timer_div = $('<div class="timer"></div>');
    $('body').append(timer_div);

    var endtime = null;
    if (end_param && end_param.startsWith('+')) {
        minutes = parseInt(end_param.substr(1));
        endtime = new Date();
        endtime.setSeconds(endtime.getSeconds() + minutes * 60);
    } else {
        hours = parseInt(end_param.substring(0, end_param.length - 2));
        minutes = parseInt(end_param.substring(end_param.length - 2));
        console.log(minutes);
        var endtime = new Date();
        if (hours || hours === 0)
            endtime.setHours(hours);
        endtime.setMinutes(minutes);
        endtime.setSeconds(0);
        endtime.setMilliseconds(0);
    }

    /* Kick things off. */

    select_slide_based_on_hash();
    setInterval(timer_update, 1000);
}

document.addEventListener("DOMContentLoaded", function(event) {

    /* If not doing a live presentation, exit without loading jQuery. */

    var url_params = new URLSearchParams(window.location.search);
    /*global*/ end_param = url_params.get('end');
    if (!end_param)
        return;

    /* Else. */

    loadScript('../js/jquery-1.6.2.min.js', setup);
});
