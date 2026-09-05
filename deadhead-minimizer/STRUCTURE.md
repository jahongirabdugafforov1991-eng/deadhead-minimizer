# Dynamic Deadhead Minimizer — Foundation Structure

/backend
├── app/
│   ├── main.py                     # FastAPI app entrypoint, router mounting, CORS, lifespan
│   ├── core/
│   │   ├── config.py                # Pydantic Settings (env vars: DB URL, DAT API keys, Twilio, OpenAI)
│   │   └── database.py              # Async SQLAlchemy engine/session, PostGIS-aware Base
│   ├── models/
│   │   ├── load.py                  # `loads` table (DAT postings, geo columns)
│   │   ├── truck.py                 # `trucks` table (driver position/status)
│   │   └── kma_heatmap.py           # `kma_heatmaps` table (zone ratios, polygons)
│   ├── schemas/
│   │   └── routing.py               # Pydantic request/response models for deadhead analysis
│   ├── services/
│   │   └── deadhead_service.py      # PostGIS radius query + net RPM arbitrage math
│   └── api/
│       └── v1/
│           └── routing.py           # POST /api/v1/routing/analyze-deadhead
├── migrations/
│   └── 001_initial_schema.sql       # Raw SQL DDL (PostGIS extension, tables, spatial indexes)
└── requirements.txt

/frontend
├── components/
│   └── map/
│       └── HeatmapLayer.tsx         # Typed Mapbox GL layer for hot/dead zone polygons
└── types/
    └── heatmap.ts                   # Shared GeoJSON/zone types

Design notes:
- All geo data uses SRID 4326 (WGS84) at rest; PostGIS `geography` type is used for the
  `loads`/`trucks` point columns so `ST_DWithin` radius math is done in meters correctly
  across latitude (avoids the "degrees aren't miles" bug you get with `geometry`).
- `kma_heatmaps.geom` stays as `geometry(Polygon, 4326)` since KMA boundaries are static
  reference geography we render, not something we distance-query against directly — we
  join it via `kma_code`/`zip3` rather than ST_DWithin on the polygon itself.
- Deadhead radius search runs against `kma_heatmaps` centroids for speed; swap to the
  polygon boundary if you want strict "inside the KMA polygon" semantics later.
