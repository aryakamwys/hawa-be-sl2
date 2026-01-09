#!/usr/bin/env python3
"""
Test script untuk memverifikasi koneksi ke NeonDB
Jalankan: poetry run python scripts/test_neon_connection.py
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from app.db.postgres import engine
import os

def test_connection():
    """Test koneksi ke database"""
    print("=" * 60)
    print("NeonDB Connection Test")
    print("=" * 60)
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set")
        print("   Please set DATABASE_URL in your .env file")
        return False
    
    # Mask password in URL for display
    if "@" in database_url:
        parts = database_url.split("@")
        if len(parts) == 2:
            user_pass = parts[0].split("://")[1] if "://" in parts[0] else parts[0]
            if ":" in user_pass:
                user = user_pass.split(":")[0]
                masked_url = database_url.replace(user_pass, f"{user}:***")
            else:
                masked_url = database_url
        else:
            masked_url = database_url
    else:
        masked_url = database_url
    
    print(f"\nConnection String: {masked_url}")
    print()
    
    try:
        # Test basic connection
        print("[1/5] Testing basic connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"   [OK] Connected successfully!")
            print(f"   PostgreSQL Version: {version.split(',')[0]}")
        
        # Test pgvector extension
        print("\n[2/5] Testing pgvector extension...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """))
            has_vector = result.fetchone()[0]
            if has_vector:
                print("   [OK] pgvector extension is enabled")
            else:
                print("   [WARNING] pgvector extension is NOT enabled")
                print("   Run this in Neon SQL Editor:")
                print("      CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Test database tables
        print("\n[3/5] Checking database tables...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            if tables:
                print(f"   [OK] Found {len(tables)} table(s):")
                for table in tables:
                    print(f"      - {table}")
            else:
                print("   [WARNING] No tables found in database")
                print("   You may need to run migration scripts")
        
        # Test SSL connection
        print("\n[4/5] Testing SSL connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SHOW ssl"))
            ssl_status = result.fetchone()[0] if result.rowcount > 0 else "unknown"
            print(f"   SSL Status: {ssl_status}")
        
        # Test connection pooling
        print("\n[5/5] Testing connection pool...")
        pool = engine.pool
        print(f"   Pool size: {pool.size()}")
        print(f"   Checked out: {pool.checkedout()}")
        print(f"   Overflow: {pool.overflow()}")
        
        print("\n" + "=" * 60)
        print("[OK] All connection tests passed!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Connection test failed: {e}")
        print("\nTroubleshooting tips:")
        print("   1. Verify your DATABASE_URL is correct")
        print("   2. Make sure your Neon project is active")
        print("   3. Check that SSL is enabled (add ?sslmode=require)")
        print("   4. Verify your network connection")
        print("   5. Check Neon dashboard for any service issues")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

