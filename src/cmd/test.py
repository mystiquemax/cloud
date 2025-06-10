import os
import sys
from bson.objectid import ObjectId # Import ObjectId for working with MongoDB _id
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, CollectionInvalid
from flask import Flask, render_template, jsonify, request, make_response, abort

# --- Global MongoDB Collection Reference ---
# It's better to manage this more explicitly or pass it around, but for a
# simple Flask app, a global variable is common.
mongo_collection = None

def prepare_database(client: MongoClient, db_name: str, collec_name: str):
    """
    Ensures the database and collection exist.
    Collections are implicitly created on first insert if they don't exist.
    """
    db = client[db_name]
    
    # Optional: Explicitly create collection if you need to enforce options like schema validation.
    # Otherwise, PyMongo will create it automatically on the first insert.
    if collec_name not in db.list_collection_names():
        print(f"Collection '{collec_name}' not found. It will be created implicitly on first data insert.")
        # try:
        #     db.create_collection(collec_name)
        # except CollectionInvalid:
        #     pass # Already created by another process concurrently
    
    return db[collec_name]

def prepare_data(coll):
    """
    Prepares some fictional data and inserts it into the database if not already present.
    It uses BookISBN for uniqueness check.
    """
    start_data = [
        {
            "BookName": "The Vortex",
            "BookAuthor": "José Eustasio Rivera",
            "BookISBN": "958-30-0804-4",
            "BookPages": 292,
            "BookYear": 1924,
        },
        {
            "BookName": "Frankenstein",
            "BookAuthor": "Mary Shelley",
            "BookISBN": "978-3-649-64609-9",
            "BookPages": 280,
            "BookYear": 1818,
        },
        {
            "BookName": "The Black Cat",
            "BookAuthor": "Edgar Allan Poe",
            "BookISBN": "978-3-99168-238-7",
            "BookPages": 280,
            "BookYear": 1843,
        },
    ]

    for book in start_data:
        # Check if a book with the same ISBN already exists
        existing_book = coll.find_one({"BookISBN": book["BookISBN"]})
        if not existing_book:
            try:
                result = coll.insert_one(book)
                print(f"Inserted new book '{book['BookName']}' with ID: {result.inserted_id}")
            except Exception as e:
                print(f"Error inserting book: {e}", file=sys.stderr)
                sys.exit(1) # Exit if we can't insert essential data
        else:
            print(f"Book '{book['BookName']}' (ISBN: {book['BookISBN']}) already exists.")

def find_all_books(coll):
    """
    Retrieves all books from the collection, converting MongoDB's _id to string.
    """
    results = []
    for book in coll.find({}):
        # Convert ObjectId to string for proper JSON serialization and template rendering
        book['_id'] = str(book['_id']) 
        results.append(book)
    return results

# --- Flask Application Setup ---
app = Flask(__name__, template_folder='views', static_folder='css')

# --- Middleware ---
@app.before_request
def log_request_info():
    """Simple logging middleware for incoming requests."""
    app.logger.info(f"Request: {request.method} {request.url}")

# --- Web Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/books")
def books():
    # Pass the global mongo_collection to the find_all_books function
    return render_template("book-table.html", books=find_all_books(mongo_collection))

@app.route("/authors")
def authors():
    # Ensure mongo_collection is used and find distinct authors
    if mongo_collection is None:
        abort(500, description="Database not initialized.")
    
    # Use distinct() for efficiency
    author_set = mongo_collection.distinct("BookAuthor")
    return render_template("authors.html", authors=sorted(author_set))

@app.route("/years")
def years():
    # Ensure mongo_collection is used and find distinct years
    if mongo_collection is None:
        abort(500, description="Database not initialized.")
        
    year_set = mongo_collection.distinct("BookYear")
    return render_template("years.html", years=sorted(year_set))

@app.route("/search")
def search():
    return render_template("search-bar.html")

# --- API Endpoints ---

@app.route("/api/books", methods=["GET"])
def api_books_get():
    """Returns all books as JSON."""
    if mongo_collection is None:
        abort(500, description="Database not initialized.")
    return jsonify(find_all_books(mongo_collection)) # Pass collection to find_all_books
    
@app.route("/api/books", methods=["POST"])
def create_book():
    """
    Creates a new book entry.
    Expects JSON data with "BookName", "BookAuthor", "BookISBN", etc.
    """
    if mongo_collection is None:
        abort(500, description="Database not initialized.")

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON body.")

    # Define required fields based on the BookStore structure
    required_fields = ["BookName", "BookAuthor", "BookISBN", "BookPages", "BookYear"]
    for field in required_fields:
        if field not in data:
            return make_response(jsonify({"error": f"Missing required field: '{field}'"}), 400)
    
    # Check if a book with the given ISBN already exists to prevent duplicates
    if mongo_collection.find_one({"BookISBN": data["BookISBN"]}):
        return make_response(jsonify({"error": "Book with this ISBN already exists."}), 409)

    # Construct the book document based on your Go struct's fields
    book_document = {
        "BookName": data["BookName"],
        "BookAuthor": data["BookAuthor"],
        "BookISBN": data["BookISBN"],
        "BookPages": data["BookPages"],
        "BookYear": data["BookYear"],
        # Add other optional fields if present in data, e.g.:
        # "BookEdition": data.get("BookEdition", ""),
    }

    try:
        result = mongo_collection.insert_one(book_document)
        # Return the MongoDB generated _id for the new book
        return make_response(jsonify({"message": "Book created successfully.", "id": str(result.inserted_id)}), 201)
    except Exception as e:
        app.logger.error(f"Error inserting book: {e}")
        return make_response(jsonify({"error": "Failed to create book due to a database error."}), 500)

@app.route("/api/books/<string:book_id>", methods=["PUT"])
def update_book(book_id):
    """
    Updates an existing book by its MongoDB _id.
    Expects JSON data for fields to update.
    """
    if mongo_collection is None:
        abort(500, description="Database not initialized.")

    data = request.get_json()
    if not data:
        abort(400, description="Invalid JSON body.")
    
    # Convert book_id to ObjectId for MongoDB query
    try:
        object_book_id = ObjectId(book_id)
    except Exception:
        abort(400, description="Invalid Book ID format.")
    
    update_fields = {}
    # Map incoming JSON keys to MongoDB document keys
    # Example: { "title": "New Name", "author": "New Author" }
    field_mapping = {
        "BookName": "BookName",
        "BookAuthor": "BookAuthor",
        "BookISBN": "BookISBN", # Be careful updating ISBN if it's meant to be unique identifier
        "BookPages": "BookPages",
        "BookYear": "BookYear",
        # "BookEdition": "BookEdition", # Add if you use this field
    }
    
    for key, mongo_key in field_mapping.items():
        if key in data:
            update_fields[mongo_key] = data[key]
    
    if not update_fields:
        abort(400, description="No valid fields to update provided.")

    try:
        # Update the document using its _id
        result = mongo_collection.update_one({"_id": object_book_id}, {"$set": update_fields})

        if result.matched_count == 0:
            abort(404, description="Book not found.")
        
        # Check if actual modification happened
        if result.modified_count == 0 and result.matched_count == 1:
            return make_response(jsonify({"message": "Book found, but no changes were applied (data was identical).", "id": book_id}), 200)

        return make_response(jsonify({"message": "Book updated successfully.", "id": book_id}), 200)
    except Exception as e:
        app.logger.error(f"Error updating book {book_id}: {e}")
        return make_response(jsonify({"error": "Failed to update book due to a database error."}), 500)

@app.route("/api/books/<string:book_id>", methods=["DELETE"])
def delete_book(book_id):
    """
    Deletes a book by its MongoDB _id.
    """
    if mongo_collection is None:
        abort(500, description="Database not initialized.")

    # Convert book_id to ObjectId for MongoDB query
    try:
        object_book_id = ObjectId(book_id)
    except Exception:
        abort(400, description="Invalid Book ID format.")
    
    try:
        result = mongo_collection.delete_one({"_id": object_book_id})

        if result.deleted_count == 0:
            return make_response(jsonify({"error": "Book not found"}), 404)
        
        return make_response(jsonify({"message": f"Deleted {result.deleted_count} book(s) with ID '{book_id}'"}), 200)
    except Exception as e:
        app.logger.error(f"Error deleting book {book_id}: {e}")
        return make_response(jsonify({"error": "Failed to delete book due to a database error."}), 500)

# --- Main Application Logic ---
if __name__ == "__main__":
    # Get MongoDB URI from environment variable
    uri = os.getenv("DATABASE_URI")
    if not uri:
        print("failure to load env variable: DATABASE_URI environment variable is not set", file=sys.stderr)
        sys.exit(1)

    print(f"Attempting to connect to MongoDB at {uri}")

    # Connect to MongoDB
    client = None
    try:
        # PyMongo handles connection pooling automatically
        # 5-second timeout for server selection (connection establishment)
        client = MongoClient(uri, serverSelectionTimeoutMS=5000) 
        # The ping command attempts to send a command to the database to check connectivity
        client.admin.command('ping') 
        print("Successfully connected to MongoDB!")
    except ConnectionFailure as e:
        print(f"Failed to connect to MongoDB. Please ensure the database is running and accessible at '{uri}': {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to create client for MongoDB or encountered another connection error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Prepare database and collection
    try:
        mongo_collection = prepare_database(client, "exercise-2", "information")
        prepare_data(mongo_collection)
    except Exception as e:
        print(f"Error preparing database or initial data: {e}", file=sys.stderr)
        sys.exit(1)

    # Start the Flask web server
    try:
        # debug=True is useful for development as it provides a debugger and auto-reloads.
        # For production, set debug=False and use a production-ready WSGI server like Gunicorn.
        app.run(host="0.0.0.0", port=3030, debug=False)
    except Exception as e:
        app.logger.error(f"Failed to start Flask application: {e}")
        sys.exit(1)
    finally:
        # Ensure client disconnects when app stops
        if client:
            client.close()
            print("MongoDB client disconnected.")