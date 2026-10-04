// SNOWMAN by Alpindata – Copyright © 2026 Hans Petter Brunstad Sørensen (Alpindata). Alle rettar reserverte. Sjå LICENSE.
// Snowman by Alpindata - terrain proxy for Cloudflare Workers
// Deploy this file as a Cloudflare Worker, then paste the workers.dev URL into Snowman.
const ALLOWED_ORIGIN = 'https://snowman6230.github.io';

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const cors = {
      'Access-Control-Allow-Origin': ALLOWED_ORIGIN,
      'Access-Control-Allow-Methods': 'GET,OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Vary': 'Origin',
      'Cache-Control': 'no-store'
    };
    if (request.method === 'OPTIONS') return new Response(null, {status:204, headers:cors});
    if (request.method !== 'GET' || url.pathname !== '/terrain') return json({ok:false,error:'Not found'},404,cors);

    const lat = Number(url.searchParams.get('lat'));
    const lon = Number(url.searchParams.get('lon'));
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < 57 || lat > 72 || lon < 4 || lon > 32) {
      return json({ok:false,error:'Invalid coordinates'},400,cors);
    }

    const upstream = new URL('https://ws.geonorge.no/hoydedata/v1/punkt');
    upstream.searchParams.set('koordsys','4326');
    upstream.searchParams.set('nord',String(lat));
    upstream.searchParams.set('ost',String(lon));
    const started = Date.now();
    try {
      const r = await fetch(upstream.toString(), {headers:{'Accept':'application/json'}});
      const text = await r.text();
      if (!r.ok) return json({ok:false,error:'Kartverket HTTP '+r.status,upstreamMs:Date.now()-started},502,cors);
      let d;
      try { d = JSON.parse(text); } catch { return json({ok:false,error:'Invalid JSON from Kartverket',upstreamMs:Date.now()-started},502,cors); }
      const p = (d.punkter && d.punkter[0]) || d.punkt || d;
      const z = Number(p?.z ?? p?.hoyde ?? p?.elevation);
      if (!Number.isFinite(z)) return json({ok:false,error:'No readable elevation',upstreamMs:Date.now()-started},502,cors);
      // Deliberately return no latitude/longitude to the browser log payload.
      return json({ok:true,z,source:p?.datakilde || 'Kartverket Høydedata',upstreamMs:Date.now()-started},200,cors);
    } catch (e) {
      return json({ok:false,error:String(e?.message || e),upstreamMs:Date.now()-started},502,cors);
    }
  }
};
function json(body,status,headers){return new Response(JSON.stringify(body),{status,headers:{...headers,'Content-Type':'application/json;charset=UTF-8'}})}
