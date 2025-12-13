#!/usr/bin/env python3
"""
Script untuk create admin user dari command line
Usage: python scripts/create_admin.py --email admin@example.com --password secret123 --full-name "Admin Name"
"""
import sys
import argparse
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy.orm import Session
from app.db.postgres import get_db
from app.db.models.user import User, RoleEnum
from app.core.security import hash_password

def create_admin_user(email: str, password: str, full_name: str | None = None, phone_e164: str | None = None):
    """Create admin user from command line"""
    db: Session = next(get_db())
    
    try:
        # Check if admin already exists
        existing_admin = db.query(User).filter(User.role == RoleEnum.ADMIN).first()
        if existing_admin:
            print(f"⚠️  Admin user already exists: {existing_admin.email}")
            response = input("Do you want to create another admin? (yes/no): ").strip().lower()
            if response not in ['yes', 'y']:
                print("❌ Cancelled.")
                return
        
        # Check if email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ Error: Email {email} already registered")
            print(f"   Existing user: {existing_user.email} (role: {existing_user.role.value})")
            return
        
        # Check if phone already exists
        if phone_e164:
            existing_phone = db.query(User).filter(User.phone_e164 == phone_e164).first()
            if existing_phone:
                print(f"❌ Error: Phone {phone_e164} already registered")
                return
        
        # Create admin user
        admin_user = User(
            full_name=full_name,
            email=email,
            phone_e164=phone_e164,
            password_hash=hash_password(password),
            role=RoleEnum.ADMIN,
        )
        
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        
        print(f"\n✅ Admin user created successfully!")
        print(f"   ID: {admin_user.id}")
        print(f"   Email: {admin_user.email}")
        print(f"   Full Name: {admin_user.full_name or 'N/A'}")
        print(f"   Role: {admin_user.role.value}")
        print(f"\n📝 You can now login with this account at the admin dashboard.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating admin user: {e}")
        raise
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Create admin user from command line")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--full-name", help="Admin full name (optional)")
    parser.add_argument("--phone", help="Admin phone number in E.164 format (optional, e.g., +6281234567890)")
    
    args = parser.parse_args()
    
    print("🔐 Creating admin user...")
    print(f"   Email: {args.email}")
    print(f"   Full Name: {args.full_name or 'N/A'}")
    print(f"   Phone: {args.phone or 'N/A'}")
    print()
    
    create_admin_user(
        email=args.email,
        password=args.password,
        full_name=args.full_name,
        phone_e164=args.phone
    )

if __name__ == "__main__":
    main()
