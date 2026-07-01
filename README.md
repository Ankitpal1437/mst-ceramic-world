# MST CERAMIC WORLD 🏪

Complete web-based business management system for MST Ceramic World, an authorized Jaquar dealer in Kalyan-West.

## Modules
- Session authentication with pending approval and 30-day remember-me support.
- Fast SQLite product search for Jaquar fittings and lighting with normalized indexed columns.
- Customer CRM, visitor check-in, local products library, follow-up dashboard foundation.
- Mobile-first React quotation builder with all four pricing modes, GST and discount visibility controls.
- Browser print-to-PDF quotation output matching MST branding, terms, bank details and bathroom/area sections.
- Admin dashboard foundation for metrics, assignments, approvals and activity oversight.

## Run locally

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

Default admin login: `ankit@mst.local` / `admin123`.

## Product CSV import
Place the Jaquar CSV at `backend/data/products.csv` or set `PRODUCT_CSV=/path/to/file.csv`. On startup the backend imports rows into SQLite with `code_norm` and `desc_norm` indexes.

Expected CSV columns:
`CODE, DESCRIPTION, EWP, MDP, SDP, NPP, NRP, MRP, OLD_NRP, OLD_MRP, SOURCE`.

## Deployment
`render.yaml` defines a Python FastAPI service with persistent disk for SQLite data and a static React frontend service for Render.com.
