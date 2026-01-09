#!/usr/bin/env python3
"""
Script untuk migrate semua tabel dari semua models
Jalankan: poetry run python scripts/migrate_all_tables.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import Base, engine

# Import semua models untuk memastikan mereka terdaftar di Base.metadata
from app.db.models import (
    User,
    ComplianceRecord,
    CommunityFeedback,
    FeedbackVote,
    WeatherKnowledge
)

def enable_pgvector():
    """Enable pgvector extension jika tersedia"""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("[OK] pgvector extension enabled")
            return True
    except Exception as e:
        print(f"[WARNING] Could not enable pgvector extension: {e}")
        print("   Continuing without vector support...")
        return False

def create_all_tables():
    """Create semua tabel dari semua models"""
    print("=" * 60)
    print("Migrating All Database Tables")
    print("=" * 60)
    print()
    
    # Enable pgvector extension
    print("[1/3] Enabling pgvector extension...")
    enable_pgvector()
    print()
    
    # Get all table names that will be created
    print("[2/3] Creating all tables from models...")
    tables_to_create = list(Base.metadata.tables.keys())
    
    print(f"   Found {len(tables_to_create)} table(s) to create:")
    for table_name in sorted(tables_to_create):
        print(f"      - {table_name}")
    print()
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        print("[OK] All tables created successfully!")
        print()
        
        # Verify tables were created
        print("[3/3] Verifying created tables...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """))
            created_tables = [row[0] for row in result.fetchall()]
            
            print(f"   Found {len(created_tables)} table(s) in database:")
            for table in sorted(created_tables):
                print(f"      - {table}")
        
        print()
        print("=" * 60)
        print("[OK] Migration completed successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"[ERROR] Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_all_tables()
    sys.exit(0 if success else 1)

