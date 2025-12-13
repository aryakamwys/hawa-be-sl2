#!/usr/bin/env python3
"""
Migration script untuk menambahkan tabel community_feedbacks dan feedback_votes
"""
import sys
from pathlib import Path

# Add parent directory to path untuk import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text
from app.db.postgres import engine

# Load environment variables
load_dotenv()


def run_migration():
    """Create community_feedbacks dan feedback_votes tables"""
    with engine.begin() as conn:  # Use begin() for automatic transaction management
        try:
            # 1. Create FeedbackStatusEnum type
            print("Creating FeedbackStatusEnum type...")
            try:
                # Check if enum already exists
                check_enum = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM pg_type WHERE typname = 'feedbackstatusenum'
                    )
                """))
                enum_exists = check_enum.scalar()
                
                if not enum_exists:
                    conn.execute(text("""
                        CREATE TYPE feedbackstatusenum AS ENUM (
                            'pending',
                            'reviewed',
                            'resolved',
                            'rejected'
                        )
                    """))
                    print("✓ FeedbackStatusEnum type created")
                else:
                    print("✓ FeedbackStatusEnum type already exists")
            except Exception as e:
                print(f"⚠ Warning checking enum: {e}")
                # Try to create anyway
                try:
                    conn.execute(text("""
                        CREATE TYPE feedbackstatusenum AS ENUM (
                            'pending',
                            'reviewed',
                            'resolved',
                            'rejected'
                        )
                    """))
                    print("✓ FeedbackStatusEnum type created")
                except Exception as e2:
                    if "already exists" in str(e2).lower() or "duplicate" in str(e2).lower():
                        print("✓ FeedbackStatusEnum type already exists")
                    else:
                        raise

            # 2. Create community_feedbacks table
            print("\nCreating community_feedbacks table...")
            try:
                # Check if table already exists
                check_table = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'community_feedbacks'
                    )
                """))
                table_exists = check_table.scalar()
                
                if not table_exists:
                    conn.execute(text("""
                        CREATE TABLE community_feedbacks (
                            id SERIAL PRIMARY KEY,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            title VARCHAR(200) NOT NULL,
                            description TEXT NOT NULL,
                            location VARCHAR(200),
                            latitude DOUBLE PRECISION,
                            longitude DOUBLE PRECISION,
                            category VARCHAR(50),
                            severity VARCHAR(20),
                            is_anonymous BOOLEAN DEFAULT FALSE NOT NULL,
                            is_public BOOLEAN DEFAULT TRUE NOT NULL,
                            attachment_paths TEXT,
                            attachment_count INTEGER DEFAULT 0 NOT NULL,
                            status feedbackstatusenum DEFAULT 'pending' NOT NULL,
                            admin_notes TEXT,
                            reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                            reviewed_at TIMESTAMP WITH TIME ZONE,
                            upvotes INTEGER DEFAULT 0 NOT NULL,
                            downvotes INTEGER DEFAULT 0 NOT NULL,
                            view_count INTEGER DEFAULT 0 NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        )
                    """))
                    print("✓ community_feedbacks table created")
                else:
                    print("✓ community_feedbacks table already exists")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print("✓ community_feedbacks table already exists")
                else:
                    raise

            # 3. Create indexes
            print("\nCreating indexes...")
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON community_feedbacks(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_status ON community_feedbacks(status)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON community_feedbacks(created_at DESC)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_category ON community_feedbacks(category)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_reviewed_by ON community_feedbacks(reviewed_by)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_is_public ON community_feedbacks(is_public) WHERE is_public = true",
                "CREATE INDEX IF NOT EXISTS idx_feedback_upvotes ON community_feedbacks(upvotes DESC)",
            ]
            
            for idx_sql in indexes:
                try:
                    conn.execute(text(idx_sql))
                    print(f"✓ {idx_sql.split('ON')[0].strip()}...")
                except Exception as e:
                    print(f"⚠ Warning: {e}")

            # 4. Create feedback_votes table
            print("\nCreating feedback_votes table...")
            try:
                # Check if table already exists
                check_table = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'feedback_votes'
                    )
                """))
                table_exists = check_table.scalar()
                
                if not table_exists:
                    conn.execute(text("""
                        CREATE TABLE feedback_votes (
                            id SERIAL PRIMARY KEY,
                            feedback_id INTEGER NOT NULL REFERENCES community_feedbacks(id) ON DELETE CASCADE,
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            vote_type VARCHAR(10) NOT NULL,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                            UNIQUE(feedback_id, user_id)
                        )
                    """))
                    print("✓ feedback_votes table created")
                else:
                    print("✓ feedback_votes table already exists")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print("✓ feedback_votes table already exists")
                else:
                    raise

            # 5. Create index for feedback_votes
            print("\nCreating feedback_votes indexes...")
            vote_indexes = [
                "CREATE INDEX IF NOT EXISTS idx_feedback_votes_feedback_id ON feedback_votes(feedback_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_votes_user_id ON feedback_votes(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_feedback_votes_user_feedback ON feedback_votes(feedback_id, user_id)",
            ]
            
            for idx_sql in vote_indexes:
                try:
                    conn.execute(text(idx_sql))
                    print(f"✓ {idx_sql.split('ON')[0].strip()}...")
                except Exception as e:
                    print(f"⚠ Warning: {e}")

            print("\n✅ Migration completed!")
            return True

        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            raise


if __name__ == "__main__":
    run_migration()

