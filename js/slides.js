
$(document).ready(function() {

    $('h1').each(function() {
        /* Remove useless titles, included only to start a new slide. */
        if ($(this).html() === 'slide')
            $(this).remove();
    });

    /* If not doing a live presentation, keep slide stack vertical. */

    var end_param = $.url.param('end');
    if (!end_param)
        return;

    /* Only style the deck once. */

    if (typeof already !== 'undefined')
        return;
    already = true;

    /* Live presentations get identically-sized scrolling slides. */

    var slide_width = 800;
    var slide_height = 600;
    var slide_gap = 200;    // px between outgoing and incoming big slide
    var slide_margin = 20;  // px between big slide and thumbnails
    var slide_scale = 0.2;  // how much tinier the thumbnailed slides are
    var duration = window.slide_transition_time ||
        500;                // animated motion duration, in ms

    $('.section').wrap('<div class="slide" />');

    /* Global state */

    slides = $('.slide');
    current_slide_n = -1;
    last_slide_change = null;

    /* Functions */

    var minus = function(boolValue) { return boolValue ? '-' : ''; }

    var select_slide = function(n) {
        window.location = '#' + n + '';
    }

    var select_slide_based_on_hash = function() {
        var n = location.hash ? parseInt(location.hash.substring(1)) : 0;
        var old_n = current_slide_n;
        var goleft = n > old_n;
        current_slide_n = n;

        /* Move the old slide out of the way. */
        if (old_n !== -1) {
            slides.eq(old_n).stop().animate({
                left: minus(goleft) + slide_width + 'px'
            }, duration, function() {
                // The second animate() in this statement may look
                // needless, but without it the slide does not move into
                // its new position.
                $(this).removeClass('full-size-slide').css(thumbpos(old_n))
                    .animate(thumbpos(old_n));
            });
        }

        /* Move the new slide into place. */
        var left = minus(!goleft) + (slide_width + slide_gap);
        slides.eq(n).stop()
            .addClass('full-size-slide')
            .css({left: left + 'px', top: '0px'})
            .animate({left: '0px'}, duration);

        /* Reposition all thumbnails. */
        for (i = 0; i < slides.length; i++) {
            var slide = slides.eq(i);
            if (!slide.hasClass('full-size-slide'))
                slide.stop().animate(thumbpos(i), duration);
        }

        /* Remember when the slide was last changed. */
        last_slide_change = new Date();
    }

    var thumbpos = function(n) {
        var slot = n - current_slide_n;
        var left = slot * slide_width * slide_scale;
        return {left: left + 'px',
                top: (0.6 * slide_height + slide_margin) + 'px'};
    }

    /* Event bindings */

    window.onhashchange = select_slide_based_on_hash;

    var leftKeys = [98];
    var rightKeys = [13, 32, 102];

    $('html').bind('keypress', function(event) {
        if (rightKeys.indexOf(event.charCode) !== -1) {
            event.preventDefault();
            if (current_slide_n < slides.length - 1)
                select_slide(current_slide_n + 1);
        } else if (leftKeys.indexOf(event.charCode) != -1) {
            event.preventDefault();
            if (current_slide_n > 0)
                select_slide(current_slide_n - 1);
        }
    });

    /* Kick things off. */

    select_slide_based_on_hash();

    /* Timer */

    var timer_update = function() {
        timer_div.removeClass('emergency');

        var now = new Date();
        readout = 'Time ' + now.toTimeString().substring(0, 5) +
            '<br>' + current_slide_n + '/' + slides.length;
        if (endtime) {
            var left = Math.floor((endtime - now) / 1000);
            var leftm = Math.floor(left / 60);
            var lefts = left % 60;
            readout += ('<br>Left ' + leftm + 'm' + lefts + 's');
            if (last_slide_change) {
                var til_end = endtime - last_slide_change;
                var slides_left = slides.length - current_slide_n;
                var time_per_slide = til_end / slides_left;
                var ss = (last_slide_change - now) + time_per_slide;
                readout += ('<br>This slide:' +
                            '<br>' + Math.floor(ss / 1000) + ' s');
                if (ss < 0)
                    timer_div.addClass('emergency');
            }
        }
        timer_div.html(readout);
    }

    var timer_div = $('<div class="timer"></div>');
    $('body').append(timer_div);
    timer_div.css({left: (slide_width * (1 - slide_scale) / 2) + 'px',
                   top: (slide_height + slide_margin) + 'px',
                   width: slide_width * slide_scale + 'px'});

    var endtime = null;
    if (end_param) {
        hours = parseInt(end_param.substring(0, end_param.length - 2));
        minutes = parseInt(end_param.substring(end_param.length - 2));
        var endtime = new Date();
        if (hours || hours === 0)
            endtime.setHours(hours);
        endtime.setMinutes(minutes);
        endtime.setSeconds(0);
        endtime.setMilliseconds(0);
    }

    setInterval(timer_update, 1000);
});
