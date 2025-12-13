#!/usr/bin/env python3
"""
Migration script untuk mengubah kolom status dari ENUM ke VARCHAR
Karena SQLAlchemy dengan native enum menggunakan enum name bukan value
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine

def run_migration():
    """Convert status column from ENUM to VARCHAR"""
    with engine.begin() as conn:
        try:
            # Check current column type
            print("Checking current column type...")
            check_sql = text("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'community_feedbacks' 
                AND column_name = 'status'
            """)
            result = conn.execute(check_sql)
            current_type = result.scalar()
            print(f"Current type: {current_type}")
            
            if current_type == 'USER-DEFINED':  # ENUM type
                print("\nConverting status column from ENUM to VARCHAR...")
                
                # Step 1: Add temporary VARCHAR column
                conn.execute(text("""
                    ALTER TABLE community_feedbacks 
                    ADD COLUMN status_temp VARCHAR(20)
                """))
                print("✓ Added temporary column")
                
                # Step 2: Copy data from ENUM to VARCHAR (convert to lowercase)
                conn.execute(text("""
                    UPDATE community_feedbacks 
                    SET status_temp = LOWER(status::text)
                """))
                print("✓ Copied data to temporary column")
                
                # Step 3: Drop old ENUM column
                conn.execute(text("""
                    ALTER TABLE community_feedbacks 
                    DROP COLUMN status
                """))
                print("✓ Dropped old ENUM column")
                
                # Step 4: Rename temporary column
                conn.execute(text("""
                    ALTER TABLE community_feedbacks 
                    RENAME COLUMN status_temp TO status
                """))
                print("✓ Renamed temporary column")
                
                # Step 5: Add NOT NULL constraint and default
                conn.execute(text("""
                    ALTER TABLE community_feedbacks 
                    ALTER COLUMN status SET NOT NULL,
                    ALTER COLUMN status SET DEFAULT 'pending'
                """))
                print("✓ Added constraints")
                
                # Step 6: Recreate index
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_feedback_status 
                    ON community_feedbacks(status)
                """))
                print("✓ Recreated index")
                
                print("\n✅ Migration completed!")
            elif current_type == 'character varying' or current_type == 'varchar':
                print("✓ Status column is already VARCHAR, no migration needed")
            else:
                print(f"⚠ Unexpected column type: {current_type}")
                
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    run_migration()






