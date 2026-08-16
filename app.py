from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)

# Secret key for Flask sessions
app.secret_key = os.getenv("SECRET_KEY", "development-secret-key")


# ============================================================
# DATABASE CONNECTION
# ============================================================

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "login_db")


db_config = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
}


# TiDB Cloud uses a secure TLS connection.
# Local MySQL continues to use the normal localhost connection.
if DB_HOST != "localhost" and DB_HOST != "127.0.0.1":

    db_config.update({
        "ssl_ca": os.getenv(
            "SSL_CA",
            "/etc/ssl/certs/ca-certificates.crt"
        ),
        "ssl_verify_cert": True,
        "ssl_verify_identity": True,
        "use_pure": True
    })


db = mysql.connector.connect(**db_config)

cursor = db.cursor(dictionary=True)


# ============================================================
# LOGIN
# ============================================================

@app.route("/")
def login():
    return render_template("login.html")


# ============================================================
# REGISTER PAGE
# ============================================================

@app.route("/register")
def register():
    return render_template("register.html")


# ============================================================
# REGISTER USER
# ============================================================

@app.route("/register_user", methods=["POST"])
def register_user():

    username = request.form["username"]
    email = request.form["email"]
    password = request.form["password"]
    confirm_password = request.form["confirm_password"]

    if password != confirm_password:
        return render_template(
            "register.html",
            message="Passwords do not match!"
        )

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (email,)
    )

    if cursor.fetchone():
        return render_template(
            "register.html",
            message="Email already exists!"
        )

    hashed_password = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO users(username, email, password)
        VALUES(%s, %s, %s)
        """,
        (username, email, hashed_password)
    )

    db.commit()

    return redirect(url_for("login"))


# ============================================================
# LOGIN USER
# ============================================================

@app.route("/login_user", methods=["POST"])
def login_user():

    email = request.form["email"]
    password = request.form["password"]

    cursor.execute(
        "SELECT * FROM users WHERE email=%s",
        (email,)
    )

    user = cursor.fetchone()

    if user and check_password_hash(
        user["password"],
        password
    ):

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        return redirect(url_for("home"))

    return render_template(
        "login.html",
        message="Invalid Email or Password"
    )


# ============================================================
# HOME
# ============================================================

@app.route("/home")
def home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor.execute("SELECT * FROM foods")
    foods = cursor.fetchall()

    return render_template(
        "home.html",
        foods=foods,
        username=session["username"]
    )


# ============================================================
# FOOD DETAILS
# ============================================================

@app.route("/food/<int:food_id>")
def food_details(food_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "SELECT * FROM foods WHERE id=%s",
        (food_id,)
    )

    food = cursor.fetchone()

    cursor.execute(
        """
        SELECT reviews.*, users.username
        FROM reviews
        JOIN users ON reviews.user_id = users.id
        WHERE reviews.food_id=%s
        ORDER BY reviews.created_at DESC
        """,
        (food_id,)
    )

    reviews = cursor.fetchall()

    return render_template(
        "food.html",
        food=food,
        reviews=reviews
    )


# ============================================================
# ADD REVIEW
# ============================================================

@app.route("/add_review/<int:food_id>", methods=["POST"])
def add_review(food_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    rating = request.form["rating"]
    review_text = request.form["review_text"]

    cursor.execute(
        """
        INSERT INTO reviews
        (user_id, food_id, rating, review_text)
        VALUES(%s, %s, %s, %s)
        """,
        (
            session["user_id"],
            food_id,
            rating,
            review_text
        )
    )

    db.commit()

    return redirect(
        url_for("food_details", food_id=food_id)
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# ============================================================
# RUN LOCALLY
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)