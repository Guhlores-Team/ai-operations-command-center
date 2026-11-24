# Suburb landing page demo

Pitch demo for two lead-generation sites (heavymovers.com.au, patientmovers.com.au) with one
landing page per Australian suburb.

- `api/render.js` renders every page on request from `data/suburbs.json` and is cached at the CDN:
  home, location hubs (state -> council area -> suburb), suburb pages, XML sitemaps.
- `data/suburbs.json` holds 17,419 suburbs (name, state, postcode, lat/lng, council area), built
  from the public matthewproctor/australianpostcodes dataset (delivery areas only).
- Preview locally with `node dev.js`, then open http://localhost:3210.

The demo is `noindex` and uses a placeholder phone number. Before launch: real contact details,
per-site domains, a working quote form, and remove the noindex header and meta tag.
