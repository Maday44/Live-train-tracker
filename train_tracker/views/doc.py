from flask import Blueprint, render_template

doc = Blueprint("doc", __name__)


@doc.route("/about")
def about():
    return render_template(
        "information/about.html",
    )


@doc.route("/developer")
def developer():
    return render_template(
        "information/dev.html",
    )
