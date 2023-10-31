(function() {
  var d = quad_data;

  var map = L.map('map');
  map.fitBounds([[d['lat1'], d['lon1']], [d['lat2'], d['lon2']]]);

  var Esri_WorldTopoMap = L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    {
      attribution: 'Tiles &copy; Esri &mdash; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC, USGS, FAO, NPS, NRCAN, GeoBase, Kadaster NL, Ordnance Survey, Esri Japan, METI, Esri China (Hong Kong), and the GIS User Community'
    }
  );
  map.addLayer(Esri_WorldTopoMap);

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
