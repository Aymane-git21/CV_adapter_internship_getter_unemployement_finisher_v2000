import os
import sys
from app import app, db, User, Application, Feedback
from sqlalchemy import text

def inspect_data():
    """
    Connects to the database and prints the first 10 rows of each table.
    """
    # Check if DATABASE_URL is set
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("\n❌ Error: DATABASE_URL environment variable is not set.")
        print("Usage:  $env:DATABASE_URL='your_neon_url'; python inspect_db.py")
        print("   OR   set DATABASE_URL=your_neon_url && python inspect_db.py")
        return

    print(f"\n🔌 Connecting to: {db_url.split('@')[-1]}") # Hide password
    
    try:
        with app.app_context():
            # Override config to ensure we use the env var
            app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace("postgres://", "postgresql://")
            
            # Test Connection
            db.session.execute(text('SELECT 1'))
            print("✅ Connection Successful!\n")

            # 1. Users
            users = User.query.limit(10).all()
            print(f"--- 👤 USERS ({User.query.count()} total) ---")
            for u in users:
                print(f"ID: {u.id} | Email: {u.email} | Plan: {u.plan_type} | Credits: {u.credits_used}")
            if not users: print("(No users found)")
            print("")

            # 2. Applications
            apps = Application.query.limit(10).all()
            print(f"--- 📄 APPLICATIONS ({Application.query.count()} total) ---")
            for a in apps:
                print(f"ID: {a.id} | User: {a.user_id} | Job: {a.job_title} | Score: {a.ats_score}")
            if not apps: print("(No applications found)")
            print("")

            # 3. Feedback
            feedbacks = Feedback.query.limit(10).all()
            print(f"--- 💬 FEEDBACK ({Feedback.query.count()} total) ---")
            for f in feedbacks:
                print(f"From: {f.email} | Msg: {f.message[:50]}...")
            if not feedbacks: print("(No feedback found)")
            print("")
            
    except Exception as e:
        print(f"\n❌ Failed to connect/read: {e}")

if __name__ == "__main__":
    inspect_data()
