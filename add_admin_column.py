# add_admin_column.py
from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # Add is_admin column
        db.session.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE"))
        db.session.commit()
        print("✅ is_admin column added successfully!")
        
        # Verify it was added
        result = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='users'"))
        columns = [row[0] for row in result]
        if 'is_admin' in columns:
            print("✅ Verified: is_admin column exists in users table")
        else:
            print("⚠️ Column not found, trying alternative method...")
            db.session.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            db.session.commit()
            print("✅ is_admin column added!")
            
    except Exception as e:
        print(f"Error: {e}")
        print("Trying alternative method...")
        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
            db.session.commit()
            print("✅ is_admin column added successfully!")
        except Exception as e2:
            print(f"Still error: {e2}")