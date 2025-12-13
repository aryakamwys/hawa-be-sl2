#!/usr/bin/env python3
"""
Migration script untuk create compliance_records table
Jalankan: python scripts/migrate_add_compliance_table.py
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
    """Create compliance_records table"""
    with engine.connect() as conn:
        try:
            # Check if table already exists
            check_sql = text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'compliance_records'
                )
            """)
            result = conn.execute(check_sql)
            exists = result.scalar()
            
            if exists:
                print("✓ Table 'compliance_records' already exists")
            else:
                # Create compliance_status enum type
                print("Creating compliance_status enum type...")
                conn.execute(text("""
                    CREATE TYPE compliancestatusenum AS ENUM ('compliant', 'non_compliant', 'warning')
                """))
                conn.commit()
                print("✓ Created compliancestatusenum type")
                
                # Create compliance_records table
                print("Creating compliance_records table...")
                conn.execute(text("""
                    CREATE TABLE compliance_records (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        emission_pm25 DOUBLE PRECISION NOT NULL,
                        emission_pm10 DOUBLE PRECISION NOT NULL,
                        regulatory_threshold_pm25 DOUBLE PRECISION NOT NULL,
                        regulatory_threshold_pm10 DOUBLE PRECISION NOT NULL,
                        compliance_status compliancestatusenum NOT NULL DEFAULT 'compliant',
                        notes VARCHAR(500),
                        facility_name VARCHAR(200),
                        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                conn.commit()
                print("✓ Created compliance_records table")
                
                # Create indexes
                print("Creating indexes...")
                conn.execute(text("CREATE INDEX idx_compliance_records_user_id ON compliance_records(user_id)"))
                conn.execute(text("CREATE INDEX idx_compliance_records_recorded_at ON compliance_records(recorded_at DESC)"))
                conn.execute(text("CREATE INDEX idx_compliance_records_status ON compliance_records(compliance_status)"))
                conn.commit()
                print("✓ Created indexes")
            
            # Verify
            verify_sql = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'compliance_records'
                ORDER BY ordinal_position
            """)
            result = conn.execute(verify_sql)
            columns = result.fetchall()
            
            print(f"\n✅ Table 'compliance_records' columns:")
            for col_name, col_type in columns:
                print(f"   - {col_name}: {col_type}")
            
            print("\n✅ Migration completed!")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    run_migration()






