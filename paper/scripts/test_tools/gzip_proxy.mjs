// Local test proxy that imitates GitHub Pages for the weight files: forwards every request to the benchmark server and
// returns .tsw responses gzip-encoded (Content-Encoding: gzip, Content-Length = compressed size), as Pages does.
// usage: node gzip_proxy.mjs <listen port> <upstream port>
import http from 'http';
import zlib from 'zlib';
const [listen, upstream] = process.argv.slice(2).map(Number);
const gzCache = new Map();
http.createServer((req, res) => {
  const up = http.request({ host: '127.0.0.1', port: upstream, path: req.url, method: req.method, headers: req.headers }, (ur) => {
    const tsw = req.method === 'GET' && req.url.split('?')[0].endsWith('.tsw') && /gzip/.test(req.headers['accept-encoding'] || '') && ur.statusCode === 200;
    if (!tsw) { res.writeHead(ur.statusCode, ur.headers); ur.pipe(res); return; }
    const chunks = [];
    ur.on('data', (c) => chunks.push(c));
    ur.on('end', () => {
      const key = req.url.split('?')[0];
      let gz = gzCache.get(key);
      if (!gz) { gz = zlib.gzipSync(Buffer.concat(chunks), { level: 6 }); gzCache.set(key, gz); }
      const h = { ...ur.headers, 'content-encoding': 'gzip', 'content-length': gz.length, vary: 'Accept-Encoding' };
      res.writeHead(200, h);
      res.end(gz);
      console.log(`${new Date().toISOString()} gzip ${key} ${Buffer.concat(chunks).length} -> ${gz.length}`);
    });
  });
  up.on('error', (e) => { res.writeHead(502); res.end(String(e)); });
  req.pipe(up);
}).listen(listen, () => console.log(`gzip proxy :${listen} -> :${upstream}`));
