from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('landing.html', current_page='home')

@app.route('/courses')
def courses():
    return render_template('courses.html', current_page='courses')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html', current_page='dashboard')

@app.route('/about')
def about():
    return render_template('about.html', current_page='about')

@app.route('/login')
def login():
    return render_template('login.html', current_page='login')

@app.route("/register")
def register():
    return render_template("register.html")

if __name__ == '__main__':
    app.run(debug=True)