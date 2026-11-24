// One renderer for both demo sites. Every page (home, location hubs, suburb landing pages,
// sitemaps) is built on request from data/suburbs.json and cached at the CDN, so all suburbs
// are live without committing tens of thousands of HTML files.
const SUBURBS = require('../data/suburbs.json'); // [name, state, postcode, lat, lng, councilArea]

const STATES = {
  nsw: ['New South Wales', 'Sydney', -33.8688, 151.2093],
  vic: ['Victoria', 'Melbourne', -37.8136, 144.9631],
  qld: ['Queensland', 'Brisbane', -27.4698, 153.0251],
  wa: ['Western Australia', 'Perth', -31.9523, 115.8613],
  sa: ['South Australia', 'Adelaide', -34.9285, 138.6007],
  tas: ['Tasmania', 'Hobart', -42.8821, 147.3272],
  act: ['Australian Capital Territory', 'Canberra', -35.2809, 149.13],
  nt: ['Northern Territory', 'Darwin', -12.4634, 130.8456],
};

const SITES = {
  'heavy-movers': {
    name: 'Heavy Movers',
    domain: 'heavymovers.com.au',
    service: 'Heavy Item Lifting & Moving',
    short: 'heavy lifting',
    accent: '#f26a1b',
    accentDark: '#c94f0a',
    ink: '#151d21',
    tint: '#fff4ea',
    tagline: 'Heavy and awkward items moved safely for hospitals, schools, removalists and government.',
    audiences: [
      ['Hospitals', 'Beds, equipment and plant moved between wards, floors and sites, scheduled around clinical activity.'],
      ['Schools', 'Furniture, equipment and stores moved during term or over the holidays.'],
      ['Removalists', 'Extra lifting support when a job includes an item your own crew cannot shift alone.'],
      ['Government', 'Heavy lifting for council, state and federal sites, quoted to suit your procurement process.'],
    ],
    steps: [
      ['Tell us what needs moving', 'What it is, roughly what it weighs, and where it sits now.'],
      ['We plan the lift', 'Access, stairs, lifts and timing are worked out before anyone arrives.'],
      ['We move it', 'The item is lifted, moved and placed where you need it.'],
    ],
    intros: [
      (s) => `Need something heavy moved in ${s.name}? ${'Heavy Movers'} handles heavy and awkward items for hospitals, schools, removalists and government sites across ${s.stateName}.`,
      (s) => `Heavy Movers provides heavy item lifting in ${s.name} ${s.state} ${s.postcode} for hospitals, schools, removalists and government departments.`,
      (s) => `From a single awkward item to a full site relocation, Heavy Movers lifts and moves heavy items in ${s.name} and the surrounding suburbs.`,
    ],
    formLabel: 'What needs lifting?',
    heading: 'Heavy Lifting',
    punch: 'Heavy lifting. Handled properly.',
    cta: 'Get a lifting quote',
    homeHead: ['Heavy items.', 'Moved right.'],
  },
  'patient-movers': {
    name: 'Patient Movers',
    domain: 'patientmovers.com.au',
    service: 'Patient Lifting & Transfer',
    short: 'patient lifting',
    accent: '#12b5a6',
    accentDark: '#0a8377',
    ink: '#0e2230',
    tint: '#ecfbf9',
    tagline: 'Patient lifting for hospitals, schools, NDIS, My Aged Care, DVA and government.',
    audiences: [
      ['Hospitals', 'Lift assistance for patient transfers, scheduled or at short notice.'],
      ['Schools', 'Lifting support for students who need help with transfers during the school day.'],
      ['NDIS', 'Lifting and transfer support for NDIS participants at home and in the community.'],
      ['My Aged Care', 'Help with lifts and transfers for older Australians receiving care at home.'],
      ['DVA', 'Lifting support for veterans receiving DVA-funded care.'],
      ['Government', 'Patient lifting for government-run facilities and programs.'],
    ],
    steps: [
      ['Tell us who needs lifting', 'Where they are, what the transfer involves, and when.'],
      ['We plan the lift', 'Access, equipment and timing are confirmed before we arrive.'],
      ['We carry out the transfer', 'The lift is done calmly, with the person kept informed throughout.'],
    ],
    intros: [
      (s) => `Need help lifting a patient in ${s.name}? Patient Movers provides lifting and transfer support for hospitals, schools, NDIS participants, aged care and DVA clients across ${s.stateName}.`,
      (s) => `Patient Movers provides patient lifting in ${s.name} ${s.state} ${s.postcode} for hospitals, schools, NDIS, My Aged Care, DVA and government.`,
      (s) => `Whether it is a one-off transfer or regular support, Patient Movers lifts and moves patients in ${s.name} and the surrounding suburbs.`,
    ],
    formLabel: 'Who needs lifting?',
    heading: 'Patient Lifting',
    punch: 'Safe lifts. Calm, careful people.',
    cta: 'Get a lifting quote',
    homeHead: ['Patient lifting.', 'Done with care.'],
  },
};

const PHONE = '1300 000 000'; // placeholder until the client supplies the real number

const slug = (s) => s.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const fmt = (n) => n.toLocaleString('en-AU');

// ---- indexes built once per cold start ----------------------------------------------------
const bySlug = new Map(); // "nsw/parramatta-2150" -> suburb
const byState = {}; // nsw -> { councils: Map(councilSlug -> {name, suburbs[]}), count }
const ALL = SUBURBS.map(([name, state, postcode, lat, lng, council]) => {
  const st = state.toLowerCase();
  const s = {
    name, state, st, postcode, lat, lng,
    council: council || '',
    stateName: STATES[st][0],
    path: `${st}/${slug(name)}-${postcode}`,
  };
  if (!bySlug.has(s.path)) bySlug.set(s.path, s);
  const bucket = (byState[st] = byState[st] || { councils: new Map(), count: 0 });
  const cSlug = slug(s.council) || 'other-areas';
  if (!bucket.councils.has(cSlug)) bucket.councils.set(cSlug, { name: s.council || 'Other areas', suburbs: [] });
  bucket.councils.get(cSlug).suburbs.push(s);
  bucket.count += 1;
  return s;
});

function km(aLat, aLng, bLat, bLng) {
  const r = Math.PI / 180;
  const x = (bLng - aLng) * r * Math.cos(((aLat + bLat) / 2) * r);
  const y = (bLat - aLat) * r;
  return Math.sqrt(x * x + y * y) * 6371;
}

function nearest(s, n) {
  const out = [];
  for (const o of ALL) {
    if (o === s) continue;
    const dLat = Math.abs(o.lat - s.lat);
    if (dLat > 1.5) continue; // cheap reject before the trig
    out.push([km(s.lat, s.lng, o.lat, o.lng), o]);
  }
  out.sort((a, b) => a[0] - b[0]);
  return out.slice(0, n);
}

function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i += 1) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h;
}

// ---- layout -------------------------------------------------------------------------------
function layout(site, key, { title, description, canonicalPath, body, jsonLd = [] }) {
  const base = `/${key}`;
  return `<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(title)}</title>
<meta name="description" content="${esc(description)}">
<link rel="canonical" href="https://www.${site.domain}${canonicalPath}">
<meta property="og:title" content="${esc(title)}">
<meta property="og:description" content="${esc(description)}">
<meta name="robots" content="noindex, nofollow">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@600;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
${jsonLd.map((j) => `<script type="application/ld+json">${JSON.stringify(j)}</script>`).join('\n')}
<style>
:root{--accent:${site.accent};--accent-d:${site.accentDark};--ink:${site.ink};--tint:${site.tint};--cream:#fff6ea;--line:#e5e7eb;--mute:#4b5563}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#1f2937;line-height:1.6;background:#fff}
h1,h2,h3,.logo,.btn,.nav,.pill,button{font-family:Poppins,system-ui,-apple-system,"Segoe UI",Arial,sans-serif}
a{color:var(--accent-d)}
.wrap{max-width:1180px;margin:0 auto;padding:0 22px}
.demo{background:#000;color:#cbd5e1;font-size:13px;text-align:center;padding:7px 12px}
.top{background:var(--ink);color:#fff;border-bottom:1px solid rgba(255,255,255,.08)}
.top .wrap{display:flex;align-items:center;justify-content:space-between;gap:18px;padding-top:16px;padding-bottom:16px}
.logo{display:flex;align-items:center;gap:12px;color:#fff;text-decoration:none;font-weight:800;font-size:19px;line-height:1.1}
.logo i{font-style:normal;display:grid;place-items:center;width:52px;height:52px;background:var(--accent);color:var(--ink);font-weight:800;font-size:22px;border-radius:6px;letter-spacing:-.04em}
.logo small{display:block;font-family:Inter,system-ui,sans-serif;font-weight:500;font-size:12px;color:#aab4bb;margin-top:3px}
.nav{display:flex;align-items:center;gap:26px;font-weight:600;font-size:16px}
.nav a{color:#fff;text-decoration:none}
.nav a:hover{color:var(--accent)}
.pill{display:flex;align-items:center;gap:10px;background:#fff;color:var(--ink);text-decoration:none;border-radius:999px;padding:7px 18px 7px 8px;line-height:1.15}
.pill i{display:grid;place-items:center;width:38px;height:38px;border-radius:50%;background:var(--accent)}
.pill small{display:block;font-family:Inter,system-ui,sans-serif;font-size:11px;color:#6b7280;font-weight:500}
.pill b{font-size:16px;font-weight:700;white-space:nowrap}
.hero{background:var(--ink);color:#fff;padding:58px 0 66px}
.hero .wrap{display:grid;grid-template-columns:1.1fr .9fr;gap:48px;align-items:center}
.crumbs{font-size:13px;color:#8b98a1;margin-bottom:22px}
.crumbs a{color:#c5ced4}
.eyebrow{display:flex;align-items:center;gap:14px;font-size:13px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:#e5e9ec;margin:0 0 14px}
.eyebrow::before{content:"";width:38px;height:3px;background:var(--accent)}
h1{font-weight:800;font-size:clamp(38px,6vw,70px);line-height:1.02;letter-spacing:-.035em;margin:0 0 20px}
h1 em{font-style:normal;color:var(--accent);display:block}
.punch{font-weight:700;font-size:20px;color:#e5e9ec;margin:0 0 4px;font-family:Poppins,system-ui,sans-serif}
.lede{font-size:18px;color:#c9d2d8;margin:0 0 26px;max-width:36rem}
.btns{display:flex;flex-wrap:wrap;gap:14px;margin-bottom:26px}
.btn{display:inline-flex;align-items:center;gap:10px;background:var(--accent);color:var(--ink);font-weight:700;text-decoration:none;padding:17px 26px;border-radius:6px;font-size:17px;border:2px solid var(--accent)}
.btn.alt{background:transparent;color:#fff;border-color:rgba(255,255,255,.55)}
.dots{list-style:none;padding:18px 0 0;margin:0;border-top:1px solid rgba(255,255,255,.14);display:flex;flex-wrap:wrap;gap:8px 26px;font-size:14px;color:#dfe5e9}
.dots li::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);margin-right:10px;vertical-align:middle}
.hero.bright{background:var(--accent);color:var(--ink)}
.hero.bright h1{color:var(--cream)}
.hero.bright h1 em{color:var(--ink)}
.hero.bright .eyebrow{color:var(--ink)}.hero.bright .eyebrow::before{background:var(--ink)}
.hero.bright .lede,.hero.bright .punch{color:var(--ink)}
.hero.bright .btn{background:var(--ink);color:#fff;border-color:var(--ink)}
.hero.bright .btn.alt{background:transparent;color:var(--ink);border-color:var(--ink)}
.hero.bright .dots{border-top-color:rgba(0,0,0,.2);color:var(--ink)}.hero.bright .dots li::before{background:var(--ink)}
form.quote{background:#fff;color:#1f2937;border-radius:14px;padding:26px;box-shadow:0 30px 60px -24px rgba(0,0,0,.6);display:grid;gap:12px}
form.quote h2{margin:0;font-size:23px;color:var(--ink);letter-spacing:-.02em}
form.quote p{margin:0;color:var(--mute);font-size:14px}
label{font-size:13px;font-weight:600;display:grid;gap:5px}
input,textarea,select{font:inherit;padding:12px;border:1px solid #cfd6db;border-radius:6px;width:100%}
button{font-weight:700;background:var(--accent);color:var(--ink);border:0;border-radius:6px;padding:15px;font-size:16px;cursor:pointer}
.msg{font-size:13px;color:var(--accent-d);min-height:18px;margin:0;font-weight:600}
.ticker{background:var(--accent);color:var(--ink);overflow:hidden;white-space:nowrap;font-family:Poppins,system-ui,sans-serif;font-weight:700;font-size:16px}
.ticker div{display:inline-block;padding:20px 0;animation:tick 38s linear infinite}
.ticker span{margin:0 26px}.ticker span::after{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--ink);opacity:.45;margin-left:52px;vertical-align:middle}
@keyframes tick{to{transform:translateX(-50%)}}
@media(prefers-reduced-motion:reduce){.ticker div{animation:none}}
.strip{background:var(--tint);border-bottom:1px solid var(--line)}
.strip .wrap{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;padding-top:22px;padding-bottom:22px}
.strip b{display:block;font-size:20px;color:var(--ink);font-family:Poppins,system-ui,sans-serif}
.strip span{font-size:14px;color:var(--mute)}
section{padding:68px 0}
section.alt{background:#f6f7f8}
h2{font-weight:800;font-size:clamp(26px,3.6vw,38px);letter-spacing:-.03em;color:var(--ink);margin:0 0 10px;line-height:1.12}
.sub{color:var(--mute);margin:0 0 32px;max-width:44rem;font-size:17px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px}
.card{border-radius:10px;padding:26px;background:var(--ink);color:#fff;border-left:5px solid var(--accent)}
.card h3{margin:0 0 8px;font-size:20px;color:#fff;font-weight:700}
.card p{margin:0;color:#c9d2d8;font-size:15px}
.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;counter-reset:n}
.step{counter-increment:n;background:#fff;border:1px solid var(--line);border-radius:10px;padding:24px}
.step::before{content:"0" counter(n);display:block;font-family:Poppins,system-ui,sans-serif;font-weight:800;font-size:34px;color:var(--accent);line-height:1;margin-bottom:10px}
.step h3{margin:0 0 4px;font-size:18px;color:var(--ink);font-weight:700}
.step p{margin:0;color:var(--mute);font-size:15px}
.area{display:grid;grid-template-columns:1fr 1fr;gap:44px}
.facts{list-style:none;padding:0;margin:0;border:1px solid var(--line);border-radius:10px;overflow:hidden}
.facts li{display:flex;justify-content:space-between;gap:16px;padding:14px 18px;border-top:1px solid var(--line);font-size:15px}
.facts li:first-child{border-top:0}
.facts span{color:var(--mute)}
.links{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:9px 18px;list-style:none;padding:0;margin:0}
.links a{text-decoration:none;font-weight:600;color:var(--ink)}
.links a:hover{color:var(--accent-d);text-decoration:underline}
.links small{color:#9ca3af;font-weight:400}
details{border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:10px;background:#fff}
summary{font-family:Poppins,system-ui,sans-serif;font-weight:700;cursor:pointer;color:var(--ink)}
details p{margin:10px 0 0;color:var(--mute)}
.cta{background:var(--accent);color:var(--ink);text-align:center}
.cta h2{color:var(--ink)}
.cta a{color:var(--ink);font-family:Poppins,system-ui,sans-serif;font-size:36px;font-weight:800;text-decoration:none}
footer{background:var(--ink);color:#9aa6ae;font-size:14px;padding:36px 0}
footer a{color:#dfe5e9}
.sticky{display:none}
@media(max-width:900px){
.hero .wrap,.area{grid-template-columns:1fr}.steps{grid-template-columns:1fr}.strip .wrap{grid-template-columns:1fr 1fr}
.nav a{display:none}.hero{padding:36px 0 44px}section{padding:46px 0}.btn{flex:1 1 100%;justify-content:center}.logo small{display:none}.pill small{display:none}
.sticky{display:block;position:fixed;left:0;right:0;bottom:0;background:var(--accent);color:var(--ink);text-align:center;font-family:Poppins,system-ui,sans-serif;font-weight:800;padding:15px;text-decoration:none;z-index:9}
body{padding-bottom:54px}
}
</style>
</head>
<body>
<div class="demo">Demo build for review. Phone number, business details and copy are placeholders.</div>
<header class="top"><div class="wrap">
  <a class="logo" href="${base}"><i>${esc(site.name.split(' ').map((w) => w[0]).join(''))}</i><span>${esc(site.name)}<small>Australia-wide</small></span></a>
  <nav class="nav"><a href="${base}#who">Who we help</a><a href="${base}#how">How it works</a><a href="${base}/locations">Areas we cover</a></nav>
  <a class="pill" href="tel:${PHONE.replace(/\s/g, '')}"><i><svg width="18" height="18" viewBox="0 0 24 24" fill="#fff"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.6 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.6 3.6a1 1 0 0 1-.25 1z"/></svg></i><span><small>Call us</small><b>${PHONE}</b></span></a>
</div></header>
${body}
<footer><div class="wrap">
  <p><strong style="color:#fff">${esc(site.name)}</strong> · ${esc(site.tagline)}</p>
  <p><a href="${base}/locations">All service areas</a> · ${Object.keys(STATES).map((st) => `<a href="${base}/locations/${st}">${st.toUpperCase()}</a>`).join(' · ')}</p>
  <p>Demo site built from one template and a dataset of ${fmt(ALL.length)} Australian suburbs. Planned domain: ${esc(site.domain)}.</p>
</div></footer>
<a class="sticky" href="tel:${PHONE.replace(/\s/g, '')}">Call ${PHONE}</a>
</body>
</html>`;
}

function quoteForm(site, where) {
  return `<form class="quote" id="quote" onsubmit="event.preventDefault();this.querySelector('.msg').textContent='Demo form: not connected yet.'">
  <h2>Get a quote${where ? ` in ${esc(where)}` : ''}</h2>
  <p>Tell us the job and we will come back to you with a quote.</p>
  <label>Name<input type="text" autocomplete="name" placeholder="Your name"></label>
  <label>Phone<input type="tel" autocomplete="tel" placeholder="Best number to reach you"></label>
  <label>${esc(site.formLabel)}<textarea rows="3" placeholder="A few details about the job"></textarea></label>
  <button type="submit">Request a quote</button>
  <p class="msg" role="status"></p>
</form>`;
}

function commonSections(site, key) {
  return `<section id="who"><div class="wrap">
  <h2>Who we help</h2>
  <p class="sub">${esc(site.tagline)}</p>
  <div class="cards">${site.audiences.map(([h, p]) => `<div class="card"><h3>${esc(h)}</h3><p>${esc(p)}</p></div>`).join('')}</div>
</div></section>
<section class="alt" id="how"><div class="wrap">
  <h2>How it works</h2>
  <p class="sub">Three steps from first call to job done.</p>
  <div class="steps">${site.steps.map(([h, p]) => `<div class="step"><h3>${esc(h)}</h3><p>${esc(p)}</p></div>`).join('')}</div>
</div></section>`;
}

// ---- pages --------------------------------------------------------------------------------
function suburbPage(site, key, s) {
  const [, capital, cLat, cLng] = STATES[s.st];
  const near = nearest(s, 12);
  const distCap = Math.round(km(s.lat, s.lng, cLat, cLng));
  const intro = site.intros[hash(s.path) % site.intros.length](s);
  const where = distCap < 4 ? `in central ${capital}` : `about ${fmt(distCap)} km from the ${capital} CBD`;
  const local = `${s.name} is ${where}${s.council ? `, in the ${s.council} council area` : ''}. We also cover nearby ${near.slice(0, 3).map(([, o]) => o.name).join(', ')}.`;
  const title = `${site.service} ${s.name} ${s.state} ${s.postcode} | ${site.name}`;
  const description = `${site.name}: ${site.short} in ${s.name} ${s.state} ${s.postcode} for ${site.audiences.map((a) => a[0].toLowerCase()).slice(0, 4).join(', ')}. Call ${PHONE} for a quote.`;
  const faqs = [
    [`Do you cover ${s.name}?`, `Yes. ${s.name} ${s.state} ${s.postcode} is in our service area, along with nearby ${near.slice(0, 4).map(([, o]) => o.name).join(', ')}.`],
    ['How do I get a quote?', `Call ${PHONE} or send the form on this page with the details of the job, where it is and when you need it done. We will come back to you with a quote.`],
    ['Who do you work with?', `We work with ${site.audiences.map((a) => a[0]).join(', ')} in ${s.name} and across ${s.stateName}.`],
  ];
  const base = `/${key}`;
  const cSlug = slug(s.council) || 'other-areas';
  const url = `https://www.${site.domain}/${s.path}`;
  const jsonLd = [
    {
      '@context': 'https://schema.org', '@type': 'Service', name: `${site.service} in ${s.name}`, serviceType: site.service,
      provider: { '@type': 'Organization', name: site.name, url: `https://www.${site.domain}`, telephone: PHONE },
      areaServed: { '@type': 'Place', name: `${s.name} ${s.state} ${s.postcode}`, address: { '@type': 'PostalAddress', addressLocality: s.name, addressRegion: s.state, postalCode: s.postcode, addressCountry: 'AU' }, geo: { '@type': 'GeoCoordinates', latitude: s.lat, longitude: s.lng } },
      url,
    },
    {
      '@context': 'https://schema.org', '@type': 'BreadcrumbList',
      itemListElement: [['Home', ''], ['Locations', '/locations'], [s.stateName, `/locations/${s.st}`], [s.name, `/${s.path}`]].map(([n, p], i) => ({ '@type': 'ListItem', position: i + 1, name: n, item: `https://www.${site.domain}${p}` })),
    },
    { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: faqs.map(([q, a]) => ({ '@type': 'Question', name: q, acceptedAnswer: { '@type': 'Answer', text: a } })) },
  ];
  const body = `<div class="hero"><div class="wrap">
  <div>
    <div class="crumbs"><a href="${base}">Home</a> › <a href="${base}/locations">Locations</a> › <a href="${base}/locations/${s.st}">${esc(s.state)}</a> › <a href="${base}/locations/${s.st}/${cSlug}">${esc(s.council || 'Other areas')}</a> › ${esc(s.name)}</div>
    <p class="eyebrow">${esc(site.name)} · ${esc(s.state)} ${esc(s.postcode)}</p>
    <h1><em>${esc(s.name)}</em>${esc(site.heading)}</h1>
    <p class="punch">${esc(site.punch)}</p>
    <p class="lede">${esc(intro)}</p>
    <div class="btns"><a class="btn" href="#quote">${esc(site.cta)}</a><a class="btn alt" href="tel:${PHONE.replace(/\s/g, '')}">Call ${PHONE}</a></div>
    <ul class="dots">${site.audiences.map(([h]) => `<li>${esc(h)}</li>`).join('')}</ul>
  </div>
  ${quoteForm(site, s.name)}
</div></div>
<div class="ticker"><div>${[...site.audiences, ...site.audiences, ...site.audiences, ...site.audiences].map(([h]) => `<span>${esc(h)}</span>`).join('')}</div></div>
<div class="strip"><div class="wrap">
  <div><b>${esc(s.name)}</b><span>${esc(s.state)} ${esc(s.postcode)}</span></div>
  <div><b>${esc(s.council || s.stateName)}</b><span>${s.council ? 'Council area' : 'State'}</span></div>
  <div><b>${fmt(distCap)} km</b><span>from ${esc(capital)} CBD</span></div>
  <div><b>${near.length} nearby</b><span>suburbs also covered</span></div>
</div></div>
${commonSections(site, key)}
<section><div class="wrap area">
  <div>
    <h2>${esc(site.name)} in ${esc(s.name)}</h2>
    <p>${esc(local)}</p>
    <ul class="facts">
      <li><span>Suburb</span><strong>${esc(s.name)}</strong></li>
      <li><span>State</span><strong>${esc(s.stateName)}</strong></li>
      <li><span>Postcode</span><strong>${esc(s.postcode)}</strong></li>
      ${s.council ? `<li><span>Council area</span><strong>${esc(s.council)}</strong></li>` : ''}
      <li><span>Distance to ${esc(capital)} CBD</span><strong>${fmt(distCap)} km</strong></li>
    </ul>
  </div>
  <div>
    <h2>Nearby areas we cover</h2>
    <ul class="links">${near.map(([d, o]) => `<li><a href="${base}/${o.path}">${esc(o.name)} ${esc(o.postcode)}</a> <small>${d < 10 ? d.toFixed(1) : Math.round(d)} km</small></li>`).join('')}</ul>
    <p style="margin-top:18px"><a href="${base}/locations/${s.st}/${cSlug}">All suburbs in ${esc(s.council || 'this area')}</a></p>
  </div>
</div></section>
<section class="alt"><div class="wrap">
  <h2>Questions about ${esc(site.short)} in ${esc(s.name)}</h2>
  <p class="sub"></p>
  ${faqs.map(([q, a]) => `<details><summary>${esc(q)}</summary><p>${esc(a)}</p></details>`).join('')}
</div></section>
<section class="cta"><div class="wrap"><h2>Need ${esc(site.short)} in ${esc(s.name)}?</h2><a href="tel:${PHONE.replace(/\s/g, '')}">${PHONE}</a></div></section>`;
  return layout(site, key, { title, description, canonicalPath: `/${s.path}`, body, jsonLd });
}

function homePage(site, key) {
  const base = `/${key}`;
  const body = `<div class="hero bright"><div class="wrap">
  <div>
    <p class="eyebrow">${esc(site.service)} · Australia-wide</p>
    <h1>${esc(site.homeHead[0])}<em>${esc(site.homeHead[1])}</em></h1>
    <p class="lede">${esc(site.tagline)}</p>
    <div class="btns"><a class="btn" href="#quote">${esc(site.cta)}</a><a class="btn alt" href="${base}/locations">Find your suburb</a></div>
    <ul class="dots">${site.audiences.map(([h]) => `<li>${esc(h)}</li>`).join('')}</ul>
  </div>
  ${quoteForm(site, '')}
</div></div>
<div class="ticker"><div>${[...site.audiences, ...site.audiences, ...site.audiences, ...site.audiences].map(([h]) => `<span>${esc(h)}</span>`).join('')}</div></div>
<div class="strip"><div class="wrap">
  <div><b>${fmt(ALL.length)}</b><span>suburb pages</span></div>
  <div><b>8</b><span>states and territories</span></div>
  <div><b>${site.audiences.length}</b><span>sectors served</span></div>
  <div><b>${PHONE}</b><span>call for a quote</span></div>
</div></div>
${commonSections(site, key)}
<section><div class="wrap">
  <h2>Service areas</h2>
  <p class="sub">Choose your state to find your suburb.</p>
  <div class="cards">${Object.entries(STATES).map(([st, [nm]]) => `<a class="card" style="text-decoration:none;display:block" href="${base}/locations/${st}"><h3>${esc(nm)}</h3><p>${fmt(byState[st].count)} suburbs</p></a>`).join('')}</div>
</div></section>
<section class="cta"><div class="wrap"><h2>Need ${esc(site.short)}?</h2><a href="tel:${PHONE.replace(/\s/g, '')}">${PHONE}</a></div></section>`;
  return layout(site, key, {
    title: `${site.service} Australia | ${site.name}`,
    description: `${site.name}: ${site.tagline} Call ${PHONE} for a quote.`,
    canonicalPath: '', body,
    jsonLd: [{ '@context': 'https://schema.org', '@type': 'Organization', name: site.name, url: `https://www.${site.domain}`, telephone: PHONE, areaServed: 'AU' }],
  });
}

function hubPage(site, key, { h1, crumbs, intro, items, title, canonicalPath }) {
  const base = `/${key}`;
  const body = `<div class="hero" style="padding:44px 0"><div class="wrap" style="display:block">
  <div class="crumbs">${crumbs.map(([n, p]) => (p === null ? esc(n) : `<a href="${base}${p}">${esc(n)}</a>`)).join(' › ')}</div>
  <h1 style="font-size:clamp(32px,4.6vw,54px)">${h1}</h1><p class="lede">${esc(intro)}</p>
</div></div>
<section><div class="wrap"><ul class="links">${items.map(([n, p, c]) => `<li><a href="${base}${p}">${esc(n)}</a>${c ? ` <small>${esc(c)}</small>` : ''}</li>`).join('')}</ul></div></section>
<section class="cta"><div class="wrap"><h2>Cannot find your suburb?</h2><a href="tel:${PHONE.replace(/\s/g, '')}">${PHONE}</a></div></section>`;
  return layout(site, key, { title, description: intro, canonicalPath, body });
}

function chooser() {
  const cards = Object.entries(SITES).map(([key, s]) => `<a href="/${key}" style="display:block;text-decoration:none;color:#fff;background:${s.ink};border-radius:16px;padding:30px;border-bottom:6px solid ${s.accent}">
  <div style="font-size:26px;font-weight:800">${esc(s.name)}</div><div style="color:#cbd5e1;margin:6px 0 14px">${esc(s.domain)}</div>
  <div style="color:#e2e8f0">${esc(s.tagline)}</div><div style="margin-top:18px;font-weight:700;color:${s.accent}">Open site →</div></a>`).join('');
  const sample = ['nsw/parramatta-2150', 'vic/fitzroy-3065', 'qld/surfers-paradise-4217', 'wa/fremantle-6160'].filter((p) => bySlug.has(p));
  return `<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><title>Suburb landing page demo</title></head>
<body style="margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f1f5f9;color:#0f172a;line-height:1.6">
<div style="max-width:960px;margin:0 auto;padding:48px 20px">
<h1 style="font-size:34px;letter-spacing:-.02em;margin:0 0 8px">Two lead-generation sites, ${fmt(ALL.length)} suburb pages each</h1>
<p style="color:#475569;max-width:44rem;margin:0 0 28px">Both sites run from one template and one suburb dataset. Every suburb page has its own title, heading, local details, nearby-suburb links, FAQ and structured data. Location hubs and XML sitemaps are generated the same way.</p>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px">${cards}</div>
<h2 style="margin:36px 0 10px;font-size:20px">Sample suburb pages</h2>
<ul style="padding-left:18px;margin:0">${Object.keys(SITES).map((key) => sample.map((p) => `<li><a href="/${key}/${p}">/${key}/${p}</a></li>`).join('')).join('')}</ul>
<h2 style="margin:28px 0 10px;font-size:20px">Sitemaps</h2>
<ul style="padding-left:18px;margin:0">${Object.keys(SITES).map((key) => `<li><a href="/${key}/sitemap.xml">/${key}/sitemap.xml</a></li>`).join('')}</ul>
</div></body></html>`;
}

// ---- router -------------------------------------------------------------------------------
function route(parts, origin) {
  if (parts.length === 0) return { html: chooser() };
  if (parts[0] === 'robots.txt') return { text: 'User-agent: *\nDisallow: /\n' };
  const key = parts[0];
  const site = SITES[key];
  if (!site) return null;
  const rest = parts.slice(1);
  if (rest.length === 0) return { html: homePage(site, key) };

  if (rest[0] === 'sitemap.xml' && rest.length === 1) {
    return { xml: `<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${Object.keys(STATES).map((st) => `<sitemap><loc>${origin}/${key}/sitemap-${st}.xml</loc></sitemap>`).join('\n')}\n</sitemapindex>\n` };
  }
  const sm = rest.length === 1 && /^sitemap-([a-z]{2,3})\.xml$/.exec(rest[0]);
  if (sm && byState[sm[1]]) {
    const urls = [];
    for (const [cSlug, c] of byState[sm[1]].councils) {
      urls.push(`${origin}/${key}/locations/${sm[1]}/${cSlug}`);
      for (const s of c.suburbs) urls.push(`${origin}/${key}/${s.path}`);
    }
    return { xml: `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map((u) => `<url><loc>${u}</loc></url>`).join('\n')}\n</urlset>\n` };
  }

  if (rest[0] === 'locations') {
    if (rest.length === 1) {
      return { html: hubPage(site, key, {
        h1: `${esc(site.service)} <em>locations</em>`, title: `Service Areas | ${site.name}`, canonicalPath: '/locations',
        crumbs: [['Home', ''], ['Locations', null]],
        intro: `${site.name} covers ${fmt(ALL.length)} suburbs across every state and territory.`,
        items: Object.entries(STATES).map(([st, [nm]]) => [nm, `/locations/${st}`, `${fmt(byState[st].count)} suburbs`]),
      }) };
    }
    const st = rest[1];
    if (!byState[st]) return null;
    const stateName = STATES[st][0];
    if (rest.length === 2) {
      const councils = [...byState[st].councils.entries()].sort((a, b) => a[1].name.localeCompare(b[1].name));
      return { html: hubPage(site, key, {
        h1: `${esc(site.service)} in <em>${esc(stateName)}</em>`, title: `${site.service} ${stateName} | ${site.name}`, canonicalPath: `/locations/${st}`,
        crumbs: [['Home', ''], ['Locations', '/locations'], [stateName, null]],
        intro: `${site.name} covers ${fmt(byState[st].count)} suburbs in ${stateName}. Choose your council area.`,
        items: councils.map(([cSlug, c]) => [c.name, `/locations/${st}/${cSlug}`, `${fmt(c.suburbs.length)}`]),
      }) };
    }
    const c = rest.length === 3 && byState[st].councils.get(rest[2]);
    if (!c) return null;
    return { html: hubPage(site, key, {
      h1: `${esc(site.service)} in <em>${esc(c.name)}</em>, ${st.toUpperCase()}`, title: `${site.service} ${c.name} ${st.toUpperCase()} | ${site.name}`, canonicalPath: `/locations/${st}/${rest[2]}`,
      crumbs: [['Home', ''], ['Locations', '/locations'], [stateName, `/locations/${st}`], [c.name, null]],
      intro: `${site.name} covers ${fmt(c.suburbs.length)} suburbs in ${c.name}, ${stateName}.`,
      items: c.suburbs.map((s) => [`${s.name} ${s.postcode}`, `/${s.path}`, '']),
    }) };
  }

  if (rest.length === 2) {
    const s = bySlug.get(`${rest[0]}/${rest[1]}`);
    if (s) return { html: suburbPage(site, key, s) };
  }
  return null;
}

module.exports = (req, res) => {
  const q = (req.query && req.query.p) || '';
  const raw = Array.isArray(q) ? q.join('/') : String(q);
  const parts = raw.split('/').map((p) => p.trim().toLowerCase()).filter(Boolean);
  const host = req.headers['x-forwarded-host'] || req.headers.host || 'localhost';
  const proto = req.headers['x-forwarded-proto'] || 'https';
  const out = route(parts, `${proto}://${host}`);

  res.setHeader('X-Robots-Tag', 'noindex, nofollow');
  if (!out) {
    res.statusCode = 404;
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.end('<!doctype html><meta charset="utf-8"><title>Page not found</title><body style="font-family:system-ui;padding:40px"><h1>Page not found</h1><p><a href="/">Back to the demo</a></p>');
    return;
  }
  res.statusCode = 200;
  res.setHeader('Cache-Control', 'public, max-age=0, s-maxage=86400, stale-while-revalidate=604800');
  if (out.xml) { res.setHeader('Content-Type', 'application/xml; charset=utf-8'); res.end(out.xml); return; }
  if (out.text) { res.setHeader('Content-Type', 'text/plain; charset=utf-8'); res.end(out.text); return; }
  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.end(out.html);
};

module.exports.route = route;
module.exports.count = ALL.length;
