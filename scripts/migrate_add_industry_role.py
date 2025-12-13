#!/usr/bin/env python3
"""
Migration script untuk menambahkan role 'industry' ke RoleEnum
Jalankan: poetry run python scripts/migrate_add_industry_role.py
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
    """Add 'industry' value to roleenum type"""
    with engine.connect() as conn:
        try:
            # Check if 'industry' value already exists
            check_sql = text("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM pg_enum 
                    WHERE enumlabel = 'industry' 
                    AND enumtypid = (
                        SELECT oid 
                        FROM pg_type 
                        WHERE typname = 'roleenum'
                    )
                )
            """)
            result = conn.execute(check_sql)
            exists = result.scalar()
            
            if exists:
                print("✓ Role 'industry' already exists in roleenum")
            else:
                # Add 'industry' value to roleenum
                # Note: PostgreSQL doesn't support IF NOT EXISTS for ADD VALUE
                # So we check first and only add if it doesn't exist
                try:
                    add_enum_sql = text("ALTER TYPE roleenum ADD VALUE 'industry'")
                    conn.execute(add_enum_sql)
                    conn.commit()
                    print("✓ Added 'industry' value to roleenum type")
                except Exception as add_error:
                    # If it fails, might be because it was added concurrently
                    # Check again
                    result = conn.execute(check_sql)
                    if result.scalar():
                        print("✓ Role 'industry' was added (possibly by concurrent operation)")
                    else:
                        raise add_error
            
            # Verify the enum values
            verify_sql = text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'roleenum'
                )
                ORDER BY enumsortorder
            """)
            result = conn.execute(verify_sql)
            enum_values = [row[0] for row in result.fetchall()]
            
            print(f"\n✅ Current roleenum values: {', '.join(enum_values)}")
            print("\n✅ Migration completed!")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    run_migration()

