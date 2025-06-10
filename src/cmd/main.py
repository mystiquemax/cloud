from flask import Flask, render_template, jsonify, request, make_response, abort
from pymongo import MongoClient
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
template_dir = os.path.join(base_dir, 'views')

app = Flask(__name__, template_folder=template_dir)

# MongoDB Setup
client = MongoClient(
    #os.getenv("DATABASE_URI")
    "mongodb://mongodb:27017/exercise-1"
    )
if not client:
    raise RuntimeError("DATABASE_URI environment variable is not set")
db = client.get_default_database()
collection = db["information"]

# Dummy initial data
start_data = [
    {
        "ID": "example1",
        "BookName": "The Vortex",
        "BookAuthor": "José Eustasio Rivera",
        "BookEdition": "958-30-0804-4",
        "BookPages": "292",
        "BookYear": "1924",
    },
    {
        "ID": "example2",
        "BookName": "Frankenstein",
        "BookAuthor": "Mary Shelley",
        "BookEdition": "978-3-649-64609-9",
        "BookPages": "280",
        "BookYear": "1818",
    },
    {
        "ID": "example3",
        "BookName": "The Black Cat",
        "BookAuthor": "Edgar Allan Poe",
        "BookEdition": "978-3-99168-238-7",
        "BookPages": "280",
        "BookYear": "1843",
    },
]

# Populate the database on startup
def prepare_data():
    for book in start_data:
        if not collection.find_one({"ID": book["ID"]}):
            collection.insert_one(book)

# Retrieve all books
def find_all_books():
    books = collection.find()
    return [
        {
            "id": str(book.get("ID", "")),
            "title": book.get("BookName", ""),
            "author": book.get("BookAuthor", ""),
            "edition": book.get("BookEdition", ""),
            "pages": book.get("BookPages", ""),
            "year": book.get("BookYear", "")
        }
        for book in books
    ]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/books")
def books():
    return render_template("book-table.html", books=find_all_books())

@app.route("/authors")
def authors():
    all_books = collection.find()
    author_set = {book.get("BookAuthor") for book in all_books if book.get("BookAuthor")}
    return render_template("authors.html", authors=sorted(author_set))

@app.route("/years")
def years():
    all_books = collection.find()
    year_set = {book.get("BookYear") for book in all_books if book.get("BookYear")}
    return render_template("years.html", years=sorted(year_set))

@app.route("/search")
def search():
    return render_template("search-bar.html")

@app.route("/api/books", methods=["GET"])
def api_books():
    return jsonify(find_all_books())
    
@app.route("/api/books", methods=["POST"])
def create_book():
    data = request.get_json()

    required_fields = ["id", "title", "author"]
    for field in required_fields:
        if field not in data:
            return make_response({"error": f"Missing field: {field}"}, 400)

    if collection.find_one({"ID": data["id"], "BookName": data["title"], "BookAuthor": data["author"], "BookEdition": data.get("edition", ""), "BookPages": data.get("pages", ""), "BookYear": data.get("year", "")}):
        return make_response({"error": "Book with characteristics already exists."}, 409)

    book = {
        "ID": data["id"],
        "BookName": data["title"],
        "BookAuthor": data["author"],
        "BookEdition": data.get("edition", ""),
        "BookPages": data.get("pages", ""),
        "BookYear": data.get("year", ""),
        }

    collection.insert_one(book)
    return make_response({"message": "Book created successfully."}, 201)

@app.route("/api/books/<string:book_id>", methods=["UPDATE", "PUT"])
def update_book(book_id):
    data = request.get_json()

    if not data:
        abort(400, description="Invalid JSON body.")
    
    update_fields = {}
    allowed_fields = {
                      "id": "ID",
                      "title": "BookName",
                      "author": "BookAuthor",
                      "edition": "BookEdition",
                      "pages": "BookPages",
                      "year": "BookYear"
                      }
    
    for key, value in allowed_fields.items():
        if key in data and key != 'id':
            update_fields[value] = data[key]
    
    if not update_fields:
        abort(400, description="No valid fields to update")


    if collection.find_one({"ID": book_id, "BookName": data["title"], "BookAuthor": data["author"], "BookEdition": data.get("edition", ""), "BookPages": data.get("pages", ""), "BookYear": data.get("year", "")}):
        return make_response({"error": "Book with characteristics already exists."}, 409)
    # Updated the row with ID=book_id with update_fields
    result = collection.update_many({"ID": book_id}, {"$set": update_fields})

    if result.matched_count == 0:
        abort(404, description="Book not found.")

    return make_response({"message": "Book updated successfully."}, 200)

@app.route("/api/books/<string:book_id>", methods=["DELETE"])
def delete_book(book_id):
    # Delete just one element with ID=book_id
    result = collection.delete_one({"ID": book_id})

    if result.deleted_count == 0:
        return make_response({"error": "Book not found"}, 404)
    
    return make_response({"message": f"Deleted {result.deleted_count} book(s) with ID '{book_id}'"}, 200)

if __name__ == "__main__":
    prepare_data()
    app.run(host="0.0.0.0", port=3030, debug=True)
