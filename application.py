import os
import requests
import json

from flask import Flask, session, render_template, request, redirect, url_for
from flask_session import Session
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

@app.route("/", methods=["GET","POST"])
def index():
    message = "Please sign in to continue"
    result = None

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username and password:
            result = db.execute(text("SELECT * FROM users WHERE username = :username AND password = :password"),
                       {"username": str(username), "password": str(password)}).fetchone()        
            if result:    
                return redirect(url_for('library', user_id=result.id))
            else:
                message = "Invalid username or password."
                return render_template("index.html", message=message)
        else:
            return render_template("index.html", message=message)
    else:
        return render_template("index.html", message=message)
    
@app.route("/register", methods=["GET","POST"])
def register():
    headline = "Create Account!"
    message = "Please sign up!"
    if request.method == "POST":
        new_username = request.form.get("newusername")
        new_password = request.form.get("newpassword")
        if new_username and new_password:
            result = db.execute(text("SELECT EXISTS (SELECT 1 FROM users WHERE username = :username);"),
                                {"username": str(new_username)})          
            result = result.scalar()
            if result == False:
                db.execute(text('INSERT INTO users (username, password) VALUES (:username, :password);'),
                   {"username": str(new_username), "password": str(new_password)})
                db.commit()
                return redirect(url_for('index'))
            else:
                message = "Sorry the username is already taken"
                return render_template("register.html",headline=headline, message=message)

    return render_template("register.html",headline=headline, message=message)

@app.route("/library/<int:user_id>", methods=["GET","POST"])
def library(user_id):
    if not user_id:
        return "ERROR"

    searches=None
    user = db.execute(text("SELECT * FROM users WHERE id=:user_id"),
                    {"user_id":user_id}).fetchone() 

    if request.method == "POST":
        isbn = request.form.get("isbn")
        title = request.form.get("title")
        author = request.form.get("author")
        year = request.form.get("year")
        if isbn or title or author or year:
            if year.isdigit():
                searches = db.execute(text("SELECT * FROM library WHERE isbn ILIKE :isbn AND title ILIKE :title AND author ILIKE :author AND year = :year"),
                                  {"isbn":f'%{isbn}%',"title":f'%{title}%',"author":f'%{author}%',"year":int(year)}).fetchall() 
            else:
                searches = db.execute(text("SELECT * FROM library WHERE isbn ILIKE :isbn AND title ILIKE :title AND author ILIKE :author"),
                                  {"isbn":f'%{isbn}%',"title":f'%{title}%',"author":f'%{author}%'}).fetchall()

            return render_template("library.html",user_id=user_id, searches=searches, username=user.username)
        else:
            searches = db.execute(text("SELECT * FROM library;")).fetchall()
            return render_template("library.html",user_id=user_id, searches=searches, username=user.username)
    else:
        searches = db.execute(text("SELECT * FROM library")).fetchall()
        return render_template("library.html",user_id=user_id, searches=searches, username=user.username)
    
@app.route("/reviews/<string:book_id>/<int:user_id>", methods=["GET","POST"])
def reviews(book_id, user_id):

    if not book_id and not user_id:
        return "ERROR"

    # SQL Queries
    searches = db.execute(text("SELECT * FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = :book_id ORDER BY reviews.id DESC"),
                          {"book_id":book_id}).fetchall()
    book = db.execute(text("SELECT * FROM library WHERE id = :book_id"),
                      {"book_id":book_id}).fetchone()
    user = db.execute(text("SELECT * FROM users WHERE id=:user_id"),
                    {"user_id":user_id}).fetchone()
    
    # API
    res = requests.get("https://www.googleapis.com/books/v1/volumes", params={"q": "isbn:{}".format(book.isbn)})
    data = res.json()
    try:
        description = data["items"][0]["volumeInfo"]["description"]
    except:
        description = None
    try:
        averageRating = data["items"][0]["volumeInfo"]["averageRating"]
    except:
        averageRating = 0
    try:
        ratingCount = data["items"][0]["volumeInfo"]["ratingsCount"]
    except:
        ratingCount = 0
    
    if request.method == "POST":
        review = request.form.get("review")
        stars = request.form.get("rating")
        check = db.execute(text("SELECT EXISTS( SELECT * FROM reviews WHERE user_id=:user_id and book_id=:book_id)"),
                    {"user_id":user_id,"book_id":book_id}).fetchone()
        if check[0]:
            return render_template("reviews.html",book_id=book_id,user_id=user_id,book=book,
                               searches=searches,username=user.username, description=description,
                               averageRating=averageRating, ratingCount=ratingCount,warning=True)
        else:
            db.execute(text('INSERT INTO reviews (book_id, user_id, review,stars) VALUES (:book_id, :user_id, :review, :stars)'),
                   {"book_id": book_id, "user_id": user_id, "review": str(review), "stars": stars})
            db.commit()
        searches = db.execute(text("SELECT * FROM reviews JOIN users ON users.id = reviews.user_id WHERE book_id = :book_id"),
                          {"book_id":book_id}).fetchall()
        return render_template("reviews.html",book_id=book_id,user_id=user_id,book=book,
                               searches=searches,username=user.username, description=description,
                               averageRating=averageRating, ratingCount=ratingCount,warning=False)
    else:
        return render_template("reviews.html",book_id=book_id,user_id=user_id,book=book,
                               searches=searches,username=user.username, description=description,
                               averageRating=averageRating, ratingCount=ratingCount,warning=False)


@app.route("/api/<string:isbn>")
def api(isbn):
    res = requests.get("https://www.googleapis.com/books/v1/volumes", params={"q": "isbn:{}".format(isbn)})
    data = res.json()

    info = {
        "title": None,
        "author": None,
        "publishedDate": None,
        "ISBN_10": None,
        "ISBN_13": None,
        "reviewCount": None,
        "averageRating": None
    }

    # Attempting to get information from Google API
    try:
        info["title"] = data["items"][0]["volumeInfo"]["title"]
    except:
        pass
    try:
        info["author"] = data["items"][0]["volumeInfo"]["authors"][0]
    except:
        pass
    try:
        info["publishedDate"] = data["items"][0]["volumeInfo"]["publishedDate"]
    except:
        pass
    try:
        if data["items"][0]["volumeInfo"]["industryIdentifiers"][0]["type"] == "ISBN_10":
            info["ISBN_10"] = data["items"][0]["volumeInfo"]["industryIdentifiers"][0]["identifier"]
        elif data["items"][0]["volumeInfo"]["industryIdentifiers"][0]["type"] == "ISBN_13":
            info["ISBN_13"] = data["items"][0]["volumeInfo"]["industryIdentifiers"][0]["identifier"]
    except:
        pass
    try:
        if data["items"][0]["volumeInfo"]["industryIdentifiers"][1]["type"] == "ISBN_10":
            info["ISBN_10"] = data["items"][0]["volumeInfo"]["industryIdentifiers"][1]["identifier"]
        elif data["items"][0]["volumeInfo"]["industryIdentifiers"][1]["type"] == "ISBN_13":
            info["ISBN_13"] = data["items"][0]["volumeInfo"]["industryIdentifiers"][1]["identifier"]
    except:
        pass
    try:
        info["reviewCount"] = data["items"][0]["volumeInfo"]["ratingsCount"]
    except:
        pass
    try:
        info["averageRating"] = data["items"][0]["volumeInfo"]["averageRating"]
    except:
        pass

    json_data = json.dumps(info)
    if info["ISBN_10"] or info["ISBN_13"]:
        return json_data
    else:
        return "404 error: ISBN not found"