# migrate_reviews.py
import re
import sys
from pathlib import Path
from sqlalchemy import text, create_engine
from sqlalchemy.exc import SQLAlchemyError

# ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# import app factory to read DB URI and config
from app import create_app

app = create_app()

# Names for old table and new table
OLD_TABLE = "old_reviews"   # change if your old table is named differently
NEW_TABLE = "reviews"

def map_category(s: str) -> int:
    if s is None:
        return 2
    s2 = s.strip().lower()
    # numeric?
    if re.fullmatch(r'[0-9]+(\.[0-9]+)?', s2):
        try:
            v = float(s2)
            if v <= 2: return 1
            if v == 3: return 2
            return 3
        except Exception:
            pass
    # keywords
    if any(w in s2 for w in ('good','great','excellent','awesome','fantastic')):
        return 3
    if any(w in s2 for w in ('avg','average','okay','ok','fine','mediocre')):
        return 2
    if any(w in s2 for w in ('bad','poor','terrible','awful','horrible')):
        return 1
    # fallback
    return 2

def main():
    with app.app_context():
        db_uri = app.config.get("SQLALCHEMY_DATABASE_URI") or app.config.get("DATABASE_URL")
        if not db_uri:
            print("ERROR: No database URI found in app.config['SQLALCHEMY_DATABASE_URI'] or app.config['DATABASE_URL'].")
            sys.exit(1)

        print("Using database URI:", db_uri.split("@")[-1] if "@" in db_uri else db_uri)

        engine = create_engine(db_uri, future=True)

        # quick check to ensure old table exists and count rows
        try:
            with engine.connect() as conn:
                res = conn.execute(text(f"SELECT COUNT(*) AS cnt FROM {OLD_TABLE}"))
                total = res.scalar_one()
        except SQLAlchemyError as e:
            print(f"ERROR: Could not read table `{OLD_TABLE}`. Check table name and DB connection.")
            print("Exception:", e)
            sys.exit(1)

        print(f"Found {total} rows in `{OLD_TABLE}`.")

        confirm = input("Proceed with migration? Type 'yes' to continue (anything else => dry-run): ").strip().lower()
        if confirm != "yes":
            print("Dry-run: showing 10 sample rows (most recent):")
            with engine.connect() as conn:
                sample = conn.execute(text(f"SELECT id, user_id, review, \"timestamp\" FROM {OLD_TABLE} ORDER BY id DESC LIMIT 10")).fetchall()
                for r in sample:
                    print(r)
            print("Dry-run complete. Re-run and type 'yes' to execute migration.")
            return

        # Fetch all rows from old table (streaming friendly)
        with engine.connect() as conn:
            rows = conn.execute(text(f"SELECT id, user_id, review, \"timestamp\" FROM {OLD_TABLE} ORDER BY id")).fetchall()

        print(f"Read {len(rows)} rows; preparing mapped inserts...")

        # Build list of dicts for executemany
        params = []
        for old_id, user_id, review_text, ts in rows:
            cat = map_category(review_text or "")
            params.append({
                "user_id": user_id,
                "place_id": None,      # old data has no place_id; set a default if you want
                "category": cat,
                "title": None,
                "body": review_text,
                "created_at": ts
            })

        # Insert in batches
        BATCH = 500
        inserted = 0
        insert_sql = f"""
        INSERT INTO {NEW_TABLE} (user_id, place_id, category, title, body, created_at)
        VALUES (:user_id, :place_id, :category, :title, :body, :created_at)
        """

        try:
            with engine.begin() as conn:  # transaction
                for i in range(0, len(params), BATCH):
                    batch = params[i:i+BATCH]
                    conn.execute(text(insert_sql), batch)
                    inserted += len(batch)
                    print(f"Inserted {inserted} rows...")
        except SQLAlchemyError as e:
            print("ERROR during insert. Transaction rolled back.")
            print(e)
            sys.exit(1)

        print("Migration finished. Inserted", inserted, "rows into", NEW_TABLE)

if __name__ == "__main__":
    main()
