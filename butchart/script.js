(function() {
  var d = quad_data;

  var map = L.map('map');
  map.fitBounds([[d['lat1'], d['lon1']], [d['lat2'], d['lon2']]]);

  var Stamen_Terrain = L.tileLayer(
    'https://stamen-tiles-{s}.a.ssl.fastly.net/terrain/{z}/{x}/{y}{r}.{ext}',
    {
      attribution: 'Map tiles by <a href="http://stamen.com">Stamen Design</a>, <a href="http://creativecommons.org/licenses/by/3.0">CC BY 3.0</a> &mdash; Map data &copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      subdomains: 'abcd',
      minZoom: 0,
      maxZoom: 15,
      ext: 'png'
    }
  );
  map.addLayer(Stamen_Terrain);

  for (var i = 0; i < quad_data['quads'].length; i++) {
    var q = quad_data['quads'][i];
    var bounds = [[q['lat1'], q['lon1']], [q['lat2'], q['lon2']]];
    var r = L.rectangle(bounds, {color: '#ff7800', weight: 1});
    r.url = q['url'];
    r.addTo(map);
    r.on('click', function(e) {
      window.open(e.target.url, '_blank');
    });
  }
})();
