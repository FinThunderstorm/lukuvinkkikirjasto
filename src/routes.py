"""Module containing all routes of the server"""
from app import app
from flask import redirect, render_template, request, session, abort
from werkzeug.security import check_password_hash, generate_password_hash
from isbnlib import is_isbn10, is_isbn13
from os import getenv
from secrets import token_hex
from repositories.tag_repository import TagRepository
from repositories.user_repository import UserRepository
from repositories.bookmark_repository import BookmarkRepository
if getenv("MODE") != "test":
    from db import db

app.secret_key = getenv("SECRET")

if getenv("MODE") != "test":
    tag_repository = TagRepository(db)
    user_repository = UserRepository(db)
    bookmark_repository = BookmarkRepository(db)

    def update_session(username, route="/"):
        session["user_id"] = user_repository.find_user_id(username)
        session["username"] = username
        session["csrf_token"] = token_hex(16)
        return redirect(route)

    @app.route("/")
    def index():
        try:
            bookmarks = bookmark_repository.get_all_bookmarks(session["user_id"])
            bookmark_tags = tag_repository.get_all_users_marked_tags(
                session["user_id"])

            tags_dict = {}
            for tag in bookmark_tags:
                if tag.bookmark_id not in tags_dict:
                    tags_dict[tag.bookmark_id] = [tag.tag_name]
                else:
                    tags_dict[tag.bookmark_id].append(tag.tag_name)
            return render_template("index.html", bookmarks=bookmarks, tags=tags_dict)
        except KeyError:
            bookmarks = None
            bookmark_tags = None
            return render_template("login.html", error="User not logged in")

    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/log", methods=["POST"])
    def log():
        username = request.form["username"]
        password = request.form["password"]
        hash_value = user_repository.find_password(username)
        if hash_value is not None:
            if check_password_hash(hash_value[0], password):
                return update_session(username)
        return render_template("login.html",
                               error="Username and password not matching")

    @app.route("/logout")
    def logout():
        try:
            del session["user_id"]
            del session["username"]
            del session["csrf_token"]
        except KeyError:
            pass
        return redirect("/")

    @app.route("/create")
    def create():
        return render_template("create.html")

    @app.route("/create_account", methods=["POST"])
    def create_account():
        username = request.form["username"]
        password = request.form["password"]
        password_confirm = request.form["passwordConfirm"]

        user_id = user_repository.find_user_id(username)
        if user_id is not None:
            return render_template("create.html", error="Username taken",
                                   user=username)
        if password != password_confirm:
            return render_template("create.html",
                                   error="Passwords not identical",
                                   user=username)

        password = generate_password_hash(password_confirm)
        user_repository.insert_user(username, password)
        return update_session(username)

    @app.route("/add_bookmark")
    def add_bookmark():
        user_id = session["user_id"]
        return render_template("add_bookmark.html",
                               tags=tag_repository.get_user_tags(user_id))

    @app.route("/add", methods=["POST"])
    def add():
        if session["csrf_token"] != request.form["csrf_token"]:
            abort(403)
        book_type = request.form["type"]
        title = request.form["title"]
        description = request.form["description"]
        author = request.form["author"]
        tags_to_add = request.form.getlist("tag")
        if book_type == "book":
            isbn = request.form["ISBN"]
            if is_isbn10(isbn) or is_isbn13(isbn):
                new_bookmark_id = bookmark_repository.insert_book(
                    session["user_id"],
                    title,
                    description,
                    author,
                    isbn
                )
            else:
                return render_template("add_bookmark.html", title=title,
                                       description=description, author=author,
                                       isbn=isbn, error="Invalid ISBN")
        elif book_type == "video":
            link = request.form["link"]
            new_bookmark_id = bookmark_repository.insert_video(
                session["user_id"],
                title,
                description,
                author,
                link)

        elif book_type == "blog":
            link = request.form["link"]
            new_bookmark_id = bookmark_repository.insert_blog(
                session["user_id"],
                title,
                description,
                author,
                link)

        elif book_type == "podcast":
            link = request.form["link"]
            episode_name = request.form["episode"]
            new_bookmark_id = bookmark_repository.insert_podcast(
                session["user_id"],
                episode_name,
                title,
                description,
                author,
                link)

        elif book_type == "scientific_article":
            pt = request.form["publication_title"]
            doi = request.form["doi"]
            publisher = request.form["publisher"]
            year = request.form["year"]
            new_bookmark_id = bookmark_repository.insert_scientific_article(
                session["user_id"],
                title,
                pt,
                description,
                author,
                doi,
                year,
                publisher)

        if tags_to_add:
            for tag in tags_to_add:
                tag_repository.mark_tag_to_bookmark(
                    session["user_id"], int(tag), new_bookmark_id)
        return redirect("/")

    @app.route("/tag", methods=["POST"])
    def tags():
        tag_name = request.form["new_tag_name"]
        tag_repository.create_new_tag(session["user_id"], tag_name)
        return redirect("/add_bookmark")

    @app.route("/bookmark_tag", methods=["POST"])
    def bookmark_tag():
        tag_id = request.form["tag_id"]
        bookmark_id = request.form["bookmark_id"]
        tag_repository.mark_tag_to_bookmark(
            session["user_id"], tag_id, bookmark_id)
        return redirect("/")
