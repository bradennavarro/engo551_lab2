import csv
import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

def main():
    books = open("books.csv")
    library = csv.reader(books)
    next(library, None) # Skips the header
    for isbn, title, author, year in library:
        command = text('INSERT INTO library (isbn, title, author, year) VALUES (:isbn, :title, :author, :year);')
        db.execute(command, {"isbn": str(isbn), "title": str(title), "author": str(author), "year": int(year)})
    db.commit()

if __name__ == "__main__":
    main()
