// Pings every live endpoint the app uses and reports HTTP status + latency.  Usage: npm run check-endpoints
const T = '12/946/1607'; // z/x/y tile over Oklahoma City (OSM order)
const tileYX = '12/1607/946';
const merc = '-10856000,4225000,-10846000,4235000';
const E = [
  ['USGS Imagery tiles', `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/tile/${tileYX}`],
  ['USGS Imagery+Topo tiles', `https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryTopo/MapServer/tile/${tileYX}`],
  ['USGS Topo tiles', `https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/${tileYX}`],
  ['USGS Shaded relief tiles', `https://basemap.nationalmap.gov/arcgis/rest/services/USGSShadedReliefOnly/MapServer/tile/${tileYX}`],
  ['Esri World Imagery tiles', `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${tileYX}`],
  ['Esri transportation ref', `https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/${tileYX}`],
  ['Esri places ref', `https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/${tileYX}`],
  ['OpenStreetMap tiles', `https://tile.openstreetmap.org/${T}.png`],
  ['USGS contours export', `https://carto.nationalmap.gov/arcgis/rest/services/contours/MapServer/export?bbox=${merc}&bboxSR=3857&imageSR=3857&size=256,256&format=png32&transparent=true&f=image`],
  ['USGS NHD export', `https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/export?bbox=${merc}&bboxSR=3857&imageSR=3857&size=256,256&format=png32&transparent=true&f=image`],
  ['USGS EPQS elevation', 'https://epqs.nationalmap.gov/v1/json?x=-97.52&y=35.47&units=Feet&wkid=4326'],
  ['OK County Assessor tax parcels (point)', 'https://okassessor.oklahomacounty.org/server/rest/services/OnlineMapping/Property_Information/MapServer/3/query?geometry=-97.52034,35.46499&geometryType=esriGeometryPoint&inSR=4326&outFields=accountno,name1&returnGeometry=false&f=json'],
  ['OK County Assessor owner search', "https://okassessor.oklahomacounty.org/server/rest/services/OnlineMapping/Property_Information/MapServer/3/query?where=name1%20LIKE%20'SMITH%20JOHN%25'&outFields=accountno&returnGeometry=false&resultRecordCount=1&f=json"],
  ['OK County Assessor account page', 'https://docs.oklahomacounty.org/AssessorWP5/AN-R.asp?PropertyID=159818'],
  ['Nominatim search', 'https://nominatim.openstreetmap.org/search?q=Oklahoma%20City%2C%20OK&format=json&limit=1'],
  // data-refresh sources
  ['TIGERweb county', "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query?where=GEOID%3D'40109'&returnGeometry=false&f=json"],
  ['PAD-US 4.1 Manager Name', 'https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/Manager_Name_PADUS/FeatureServer/0?f=json'],
  ['OK Recreational Areas (WMA)', 'https://services6.arcgis.com/RBtoEUQ2lmN0K3GY/arcgis/rest/services/OklahomaRecreationalAreas/FeatureServer/0?f=json'],
  ['ODWC WILMA features', 'https://www.wildlifedepartment.com/server/rest/services/PublicWILMA/WILMAFeatures/MapServer?f=json'],
  ['BLM PLSS CadNSDI', 'https://gis.blm.gov/arcgis/rest/services/Cadastral/BLM_Natl_PLSS_CadNSDI/MapServer?f=json'],
  ['OKC open data parks', 'https://utility.arcgis.com/usrsvcs/servers/1e65b61d07f5458a90d4cfa01e882044/rest/services/OpenData/Recreation_Parks/FeatureServer/4?f=json'],
];
let bad = 0;
await Promise.all(E.map(async ([name, url]) => {
  const t0 = Date.now();
  try {
    const r = await fetch(url, { headers: { 'User-Agent': 'onx-oklahoma-county endpoint check' }, signal: AbortSignal.timeout(30000) });
    const buf = await r.arrayBuffer(); const ct = r.headers.get('content-type') || '';
    let ok = r.ok && buf.byteLength > 50;
    if (ok && ct.includes('json')) { const j = JSON.parse(new TextDecoder().decode(buf)); if (j.error) ok = false; }
    if (!ok) bad++;
    console.log(`${ok ? 'OK  ' : 'FAIL'} ${String(r.status).padEnd(4)} ${String(Date.now() - t0).padStart(5)}ms  ${name}`);
  } catch (e) { bad++; console.log(`FAIL ---- ${String(Date.now() - t0).padStart(5)}ms  ${name}: ${e.message}`); }
}));
process.exit(bad ? 1 : 0);
