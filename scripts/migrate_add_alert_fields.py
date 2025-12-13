#!/usr/bin/env python3
"""
Migration script untuk menambahkan alert threshold fields ke User model
Jalankan: poetry run python scripts/migrate_add_alert_fields.py
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
    """Add alert threshold fields to users table"""
    with engine.connect() as conn:
        try:
            migrations = [
                # Alert threshold fields
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_pm25_threshold DOUBLE PRECISION",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_pm10_threshold DOUBLE PRECISION",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_enabled BOOLEAN DEFAULT TRUE NOT NULL",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_methods VARCHAR(100)",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS alert_frequency VARCHAR(50)",
            ]
            
            for migration in migrations:
                try:
                    conn.execute(text(migration))
                    conn.commit()
                    print(f"✓ {migration[:60]}...")
                except Exception as e:
                    print(f"✗ Error: {e}")
                    conn.rollback()
            
            print("\n✅ Migration completed!")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    run_migration()






