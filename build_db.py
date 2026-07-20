"""
build_db.py — MST Ceramic World
Converts price.csv (CODE,DESCRIPTION,SOURCE,EWP,MDP,SDP,NRP_2025,MRP_2025,NRP_JAN2026,MRP_JAN2026,NRP_JULY2026,MRP_JULY2026)
into optimized SQLite database.
"""
import sqlite3
import csv
import os

CSV_FILE = "price.csv"
DB_FILE = "mst.db"


def normalize(text):
    return (text or "").strip().lower()


def build_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            code_norm TEXT NOT NULL,
            description TEXT,
            desc_norm TEXT,
            source TEXT,
            ewp TEXT,
            mdp TEXT,
            sdp TEXT,
            nrp_2025 TEXT,
            mrp_2025 TEXT,
            nrp_jan2026 TEXT,
            mrp_jan2026 TEXT,
            nrp_july2026 TEXT,
            mrp_july2026 TEXT
        )
    """)

    rows_added = 0
    skipped = 0

    with open(CSV_FILE, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        print("CSV columns found:", reader.fieldnames)
        batch = []
        for row in reader:
            code = (row.get("CODE") or "").strip()
            desc = (row.get("DESCRIPTION") or "").strip()

            if not code or code.upper() == "CODE" or len(code) <= 2 or not desc:
                skipped += 1
                continue

            batch.append((
                code, normalize(code), desc, normalize(desc),
                (row.get("SOURCE") or "FITTINGS").strip().upper(),
                (row.get("EWP") or "").strip(),
                (row.get("MDP") or "").strip(),
                (row.get("SDP") or "").strip(),
                (row.get("NRP_2025") or "").strip(),
                (row.get("MRP_2025") or "").strip(),
                (row.get("NRP_JAN2026") or "").strip(),
                (row.get("MRP_JAN2026") or "").strip(),
                (row.get("NRP_JULY2026") or "").strip(),
                (row.get("MRP_JULY2026") or "").strip(),
            ))
            rows_added += 1

            if len(batch) >= 5000:
                cur.executemany("""
                    INSERT INTO products
                    (code, code_norm, description, desc_norm, source, ewp, mdp, sdp,
                     nrp_2025, mrp_2025, nrp_jan2026, mrp_jan2026, nrp_july2026, mrp_july2026)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                batch = []

        if batch:
            cur.executemany("""
                INSERT INTO products
                (code, code_norm, description, desc_norm, source, ewp, mdp, sdp,
                 nrp_2025, mrp_2025, nrp_jan2026, mrp_jan2026, nrp_july2026, mrp_july2026)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)

    cur.execute("CREATE INDEX idx_code_norm ON products(code_norm)")
    cur.execute("CREATE INDEX idx_desc_norm ON products(desc_norm)")
    cur.execute("CREATE INDEX idx_source ON products(source)")

    conn.commit()
    conn.close()

    print(f"Database built: {DB_FILE}")
    print(f"Rows added: {rows_added}")
    print(f"Rows skipped: {skipped}")


if __name__ == "__main__":
    build_database()
