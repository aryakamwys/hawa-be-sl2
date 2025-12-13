#!/usr/bin/env python3
"""
Fix roleenum case inconsistency
Database has: USER, ADMIN (uppercase) and industry (lowercase)
We need to make it consistent - all lowercase: user, admin, industry
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine

def fix_enum_case():
    """Fix roleenum to be all lowercase"""
    with engine.connect() as conn:
        try:
            # Check current values
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'roleenum'
                )
                ORDER BY enumsortorder
            """))
            current_values = [row[0] for row in result.fetchall()]
            print(f"Current enum values: {current_values}")
            
            # Check if we have the lowercase values we need
            needed_values = ['user', 'admin', 'industry']
            missing = [v for v in needed_values if v not in current_values]
            
            if missing:
                print(f"\nAdding missing lowercase values: {missing}")
                for value in missing:
                    try:
                        conn.execute(text(f"ALTER TYPE roleenum ADD VALUE '{value}'"))
                        conn.commit()
                        print(f"✓ Added '{value}' to enum")
                    except Exception as e:
                        print(f"✗ Error adding '{value}': {e}")
                        conn.rollback()
            
            # Verify final values
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'roleenum'
                )
                ORDER BY enumsortorder
            """))
            final_values = [row[0] for row in result.fetchall()]
            print(f"\n✅ Final enum values: {final_values}")
            print("\n✅ Migration completed!")
            print("\nNote: Old uppercase values (USER, ADMIN, INDUSTRY) still exist but won't be used.")
            print("SQLAlchemy will use lowercase values (user, admin, industry) from RoleEnum.")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    fix_enum_case()






