function start_seadragon(name, image_width, image_height, rotation) {
    /* The CONTENTdm image server expresses scale as a percent, so
       "DMSCALE=100" requests tiles scaled 1:1 to the original image.
       Its own image viewer uses magnifications like "5,10,15,20,..."
       as the user zooms in.  Since Seadragon wants scales that are
       instead separated by a factor of 2, we here use 128% as our
       maximum magnification so that we can cleanly ask for 7 levels of
       lesser magnification without generating fractional percents. */

    var log2 = function(n) {
        return Math.log(n) * Math.LOG2E;
    };

    var levels = 7;             // log2(128)
    var tile_size = 512;
    var largest_dimension = Math.max(image_width, image_height);
    var max_level = Math.trunc(log2(largest_dimension) + 0.9999999);
    var min_level = Math.max(1, max_level - levels);

    var get_tile_url = function(level, x, y) {
        /* When Seadragon asks for max_level, use 128%. */
        var scale = Math.pow(2, levels - (max_level - level));
        var x = x * tile_size;
        var y = y * tile_size;
        var width = tile_size;
        var height = tile_size;
        var cisoroot = 'cpa';
        var dmtext = '';
        var dmrotate = '0';
        console.log(level, scale, x, y, width, height);
        var u = 'http://archive.library.nau.edu/utils/ajaxhelper/?CISOROOT={cisoroot}&CISOPTR={name}&action=2&DMSCALE={scale}&DMWIDTH={width}&DMHEIGHT={height}&DMX={x}&DMY={y}&DMTEXT={dmtext}&DMROTATE={dmrotate}';
        return u.
            replace(/{cisoroot}/g, cisoroot).
            replace(/{name}/g, name).
            replace(/{scale}/g, scale).
            replace(/{x}/g, x).
            replace(/{y}/g, y).
            replace(/{width}/g, width).
            replace(/{height}/g, height).
            replace(/{dmtext}/g, dmtext).
            replace(/{dmrotate}/g, dmrotate);
    };

    OpenSeadragon({
        id: 'map',
        prefixUrl: 'https://rawgit.com/fabiovalse/Hub/master/lib/openseadragon/images/',
        navigatorSizeRatio: 0.25,
        showRotationControl: true,
        degrees: rotation,
        tileSources: {
            width: Math.trunc(image_width * 1.28),
            height: Math.trunc(image_height * 1.28),
            tileSize: tile_size,
            maxLevel: max_level,
            minLevel: min_level,
            getTileUrl: get_tile_url
        }
    });
}
