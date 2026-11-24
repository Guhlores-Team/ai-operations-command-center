// Local preview: node dev.js  ->  http://localhost:3210
const http = require('http');
const handler = require('./api/render.js');
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  req.query = { p: url.pathname.replace(/^\/+/, '') };
  handler(req, res);
}).listen(3210, () => console.log('http://localhost:3210'));
