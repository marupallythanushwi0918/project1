from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ============================================================
# FLASK CONFIGURATION
# ============================================================

app.secret_key = os.getenv(
    "SECRET_KEY",
    "development-secret-key"
)

# ============================================================
# SWAGGER CONFIGURATION
# ============================================================

swagger = Swagger(app)

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

# TiDB Cloud TLS configuration
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
# ============================================================
#              SWAGGER CRUD API - FOODS
# ============================================================
# ============================================================


# ============================================================
# CREATE FOOD - POST
# ============================================================

@app.route("/api/foods", methods=["POST"])
def create_food():
    """
    Create a new food
    ---
    tags:
      - Foods CRUD
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - name
          properties:
            name:
              type: string
              example: Pizza
            category:
              type: string
              example: Fast Food
            price:
              type: number
              example: 200
            description:
              type: string
              example: Cheesy vegetable pizza
    responses:
      201:
        description: Food created successfully
      400:
        description: Invalid request
    """

    try:

        data = request.get_json()

        if not data:
            return jsonify({
                "error": "JSON body is required"
            }), 400

        if "name" not in data:
            return jsonify({
                "error": "Food name is required"
            }), 400

        name = data["name"]
        category = data.get("category")
        price = data.get("price")
        description = data.get("description")

        cursor.execute(
            """
            INSERT INTO foods
            (name, category, price, description)
            VALUES(%s, %s, %s, %s)
            """,
            (
                name,
                category,
                price,
                description
            )
        )

        db.commit()

        return jsonify({
            "message": "Food created successfully",
            "id": cursor.lastrowid
        }), 201

    except Exception as e:

        db.rollback()

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# READ ALL FOODS - GET
# ============================================================

@app.route("/api/foods", methods=["GET"])
def get_foods():
    """
    Get all foods
    ---
    tags:
      - Foods CRUD
    responses:
      200:
        description: List of all foods
    """

    try:

        cursor.execute(
            "SELECT * FROM foods"
        )

        foods = cursor.fetchall()

        return jsonify(foods), 200

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# READ ONE FOOD - GET
# ============================================================

@app.route("/api/foods/<int:food_id>", methods=["GET"])
def get_food(food_id):
    """
    Get a food by ID
    ---
    tags:
      - Foods CRUD
    parameters:
      - name: food_id
        in: path
        required: true
        type: integer
        example: 1
    responses:
      200:
        description: Food found
      404:
        description: Food not found
    """

    try:

        cursor.execute(
            "SELECT * FROM foods WHERE id=%s",
            (food_id,)
        )

        food = cursor.fetchone()

        if not food:

            return jsonify({
                "error": "Food not found"
            }), 404

        return jsonify(food), 200

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# UPDATE FOOD - PUT
# ============================================================

@app.route("/api/foods/<int:food_id>", methods=["PUT"])
def update_food(food_id):
    """
    Update a food
    ---
    tags:
      - Foods CRUD
    consumes:
      - application/json
    parameters:
      - name: food_id
        in: path
        required: true
        type: integer
        example: 1
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              example: Cheese Pizza
            category:
              type: string
              example: Fast Food
            price:
              type: number
              example: 220
            description:
              type: string
              example: Delicious cheese pizza
    responses:
      200:
        description: Food updated successfully
      404:
        description: Food not found
    """

    try:

        data = request.get_json()

        cursor.execute(
            "SELECT * FROM foods WHERE id=%s",
            (food_id,)
        )

        food = cursor.fetchone()

        if not food:

            return jsonify({
                "error": "Food not found"
            }), 404

        name = data.get(
            "name",
            food["name"]
        )

        category = data.get(
            "category",
            food["category"]
        )

        price = data.get(
            "price",
            food["price"]
        )

        description = data.get(
            "description",
            food["description"]
        )

        cursor.execute(
            """
            UPDATE foods
            SET name=%s,
                category=%s,
                price=%s,
                description=%s
            WHERE id=%s
            """,
            (
                name,
                category,
                price,
                description,
                food_id
            )
        )

        db.commit()

        return jsonify({
            "message": "Food updated successfully",
            "id": food_id
        }), 200

    except Exception as e:

        db.rollback()

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# DELETE FOOD - DELETE
# ============================================================

@app.route("/api/foods/<int:food_id>", methods=["DELETE"])
def delete_food(food_id):
    """
    Delete a food
    ---
    tags:
      - Foods CRUD
    parameters:
      - name: food_id
        in: path
        required: true
        type: integer
        example: 7
    responses:
      200:
        description: Food deleted successfully
      404:
        description: Food not found
      409:
        description: Food cannot be deleted because reviews exist
    """

    try:

        cursor.execute(
            "SELECT * FROM foods WHERE id=%s",
            (food_id,)
        )

        food = cursor.fetchone()

        if not food:

            return jsonify({
                "error": "Food not found"
            }), 404

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM reviews
            WHERE food_id=%s
            """,
            (food_id,)
        )

        review_count = cursor.fetchone()["count"]

        if review_count > 0:

            return jsonify({
                "error": "Cannot delete food because reviews exist for this food"
            }), 409

        cursor.execute(
            "DELETE FROM foods WHERE id=%s",
            (food_id,)
        )

        db.commit()

        return jsonify({
            "message": "Food deleted successfully",
            "id": food_id
        }), 200

    except Exception as e:

        db.rollback()

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)