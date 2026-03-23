from flask import Flask, render_template, request, redirect, url_for, flash, session
from config import Config
from extensions import db, login_manager
from models import User, Course, Enrollment
from werkzeug.security import check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
import secrets
import requests
import json

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

# Helper function to generate payment reference
def generate_reference(user_id):
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = secrets.token_hex(4)
    return f"COR-{user_id}-{timestamp}-{random_str}"

# ----------------------
# Routes
# ----------------------

@app.route("/")
def landing():
    return render_template("landing.html", user=current_user)

@app.route("/courses")
def courses():
    return render_template("courses.html", user=current_user)

@app.route("/about")
def about():
    return render_template("about.html", user=current_user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Get form data
        bride_first = request.form.get("bride_first_name")
        bride_last = request.form.get("bride_last_name")
        bride_email = request.form.get("bride_email")
        bride_parish = request.form.get("bride_parish")
        
        groom_first = request.form.get("groom_first_name")
        groom_last = request.form.get("groom_last_name")
        groom_email = request.form.get("groom_email")
        groom_parish = request.form.get("groom_parish")
        
        wedding_date = request.form.get("wedding_date")
        email = request.form.get("bride_email")  # Primary email for login
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        
        # Validation
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for("register"))
        
        # Check if user exists
        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "error")
            return redirect(url_for("register"))
        
        # Create new user
        user = User(
            email=email,
            bride_first_name=bride_first,
            bride_last_name=bride_last,
            bride_email=bride_email,
            bride_parish=bride_parish,
            groom_first_name=groom_first,
            groom_last_name=groom_last,
            groom_email=groom_email,
            groom_parish=groom_parish,
            wedding_date=datetime.strptime(wedding_date, '%Y-%m-%d') if wedding_date else None,
            is_paid=False
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        # Auto login after registration
        login_user(user)
        
        flash("Registration successful! Welcome to COR AMANS. Please complete payment to access your dashboard.", "success")
        return redirect(url_for("payment"))
    
    return render_template("register.html", user=current_user)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        remember = request.form.get("remember")
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user, remember=bool(remember))
            
            # Check if user has paid
            if user.is_paid:
                flash("Welcome back! You have successfully logged in.", "success")
                return redirect(url_for("dashboard"))
            else:
                # Success message first
                flash("Login successful! Welcome to COR AMANS.", "success")
                # Then payment reminder
                flash("Please complete payment to access your dashboard. You can browse courses or make payment below.", "warning")
                return redirect(url_for("payment"))
        else:
            flash("Invalid email or password! Please try again.", "error")
            return redirect(url_for("login"))
    
    return render_template("login.html", user=current_user)
@app.route("/dashboard")
@login_required
def dashboard():
    if not current_user.is_paid:
        flash("Please complete payment to access your dashboard.", "warning")
        return redirect(url_for("payment"))
    
    return render_template("dashboard.html", user=current_user)

@app.route("/payment", methods=["GET", "POST"])
@login_required
def payment():
    # If user already paid, redirect to dashboard
    if current_user.is_paid:
        flash("You already have access to your dashboard!", "info")
        return redirect(url_for("dashboard"))
    
    if request.method == "POST":
        payment_method = request.form.get("payment_method")
        
        # Paystack integration
        if payment_method == "paystack":
            # For development/testing, simulate payment
            current_user.is_paid = True
            db.session.commit()
            flash("Payment successful! Welcome to COR AMANS.", "success")
            return redirect(url_for("dashboard"))
    
    return render_template("payment.html", user=current_user)

@app.route("/verify-payment")
@login_required
def verify_payment():
    """Verify payment after returning from Paystack"""
    reference = request.args.get('reference')
    
    if not reference:
        flash("Invalid payment reference.", "error")
        return redirect(url_for("payment"))
    
    # For development, simulate successful verification
    current_user.is_paid = True
    db.session.commit()
    flash("Payment verified successfully! Your dashboard is now unlocked.", "success")
    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing"))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html", user=current_user), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template("500.html", user=current_user), 500

if __name__ == "__main__":
    app.run(debug=True)