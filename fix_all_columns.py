# fix_all_columns.py
from app import app, db
from sqlalchemy import text

print("🔧 Fixing database columns...")

with app.app_context():
    # Fix courses table - add created_at
    try:
        db.session.execute(text("ALTER TABLE courses ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
        db.session.commit()
        print("✅ created_at column added to courses table")
    except Exception as e:
        print(f"Note: courses table - {e}")
    
    # Fix users table - add force_password_change
    try:
        db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS force_password_change BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        print("✅ force_password_change column added to users table")
    except Exception as e:
        print(f"Note: users table - {e}")
    
    # Verify all columns exist
    print("\n📋 Verifying columns:")
    
    # Check courses columns
    result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='courses'"))
    courses_columns = [row[0] for row in result]
    print(f"   Courses table columns: {courses_columns}")
    
    # Check users columns
    result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
    users_columns = [row[0] for row in result]
    print(f"   Users table columns: {users_columns}")
    
    print("\n✅ Database fix complete!")

print("\n🚀 Restart your Flask app now: python app.py")