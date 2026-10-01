import os
import secrets
import sqlite3
from datetime import datetime
from urllib.parse import urlsplit
from functools import wraps
from pathlib import Path
import smtplib
from email.message import EmailMessage

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for
)

import click

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import (
    ALLOWED_EXTENSIONS,
    BUSINESS,
    DATABASE,
    UPLOAD_FOLDER
)


# =========================================================
# APP SETUP
# =========================================================

app = Flask(__name__)

# Each installation gets a private signing key; never use a public default.
def installation_secret():
    configured = os.environ.get("SECRET_KEY")
    if configured:
        if len(configured) < 32 or configured == "change-this-secret-key-before-production":
            raise RuntimeError("SECRET_KEY must be a private random value of at least 32 characters.")
        return configured
    folder = Path(__file__).resolve().parent / ".instance"
    folder.mkdir(mode=0o700, exist_ok=True)
    key_file = folder / "session.key"
    try:
        with key_file.open("x") as handle:
            key_file.chmod(0o600)
            handle.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    return key_file.read_text().strip()


app.config.update(
    SECRET_KEY=installation_secret(),
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
    UPLOAD_FOLDER=str(UPLOAD_FOLDER),
    MAX_CONTENT_LENGTH=25 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

Path(DATABASE).parent.mkdir(exist_ok=True)
Path(UPLOAD_FOLDER).mkdir(parents=True, exist_ok=True)


# =========================================================
# DATABASE SCHEMA
# =========================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    property_type TEXT NOT NULL,
    purpose TEXT NOT NULL,
    price INTEGER NOT NULL,
    location TEXT NOT NULL,
    city TEXT NOT NULL,
    address TEXT,
    area INTEGER,
    bedrooms INTEGER,
    bathrooms INTEGER,
    parking TEXT,
    furnishing TEXT,
    status TEXT NOT NULL,
    description TEXT,
    features TEXT,
    maps_url TEXT,
    contact_phone TEXT,
    featured INTEGER DEFAULT 0,
    published INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS property_images (
    id INTEGER PRIMARY KEY,
    property_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    alt_text TEXT,
    FOREIGN KEY(property_id)
        REFERENCES properties(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS enquiries (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    message TEXT,
    property_id INTEGER,
    is_read INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(property_id)
        REFERENCES properties(id)
        ON DELETE SET NULL
);
"""


# =========================================================
# DATABASE CONNECTION
# =========================================================

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)

    if connection:
        connection.close()


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():
    connection = sqlite3.connect(DATABASE)

    connection.executescript(SCHEMA)

    connection.commit()
    connection.close()


# =========================================================
# CSRF PROTECTION
# =========================================================

def csrf_token():
    session.setdefault(
        "csrf",
        secrets.token_urlsafe(24)
    )

    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.globals["business"] = BUSINESS


@app.before_request
def protect_post():

    if request.method == "POST":

        if not session.get("csrf") or request.form.get("csrf_token") != session["csrf"]:

            abort(400, "Invalid form token")


# =========================================================
# ADMIN LOGIN PROTECTION
# =========================================================

def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        if current_admin() is None:

            return redirect(
                url_for(
                    "admin_login",
                    next=request.path
                )
            )

        return view(*args, **kwargs)

    return wrapped


# =========================================================
# HELPERS
# =========================================================

def allowed(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def slugify(value):

    cleaned = "".join(
        c.lower() if c.isalnum() else "-"
        for c in value
    ).strip("-")

    return cleaned or secrets.token_hex(4)


def money(value):

    return f"₹{int(value or 0):,}"


# =========================================================
# PROPERTY IMAGE HELPER
# =========================================================

def add_images_to_properties(rows):
    """
    Adds property images to every property.

    This allows _card.html to use:

        property.images
    """

    properties = []

    for row in rows:

        property_data = dict(row)

        property_data["images"] = db().execute(
            """
            SELECT *
            FROM property_images
            WHERE property_id=?
            ORDER BY id ASC
            """,
            (row["id"],)
        ).fetchall()

        properties.append(property_data)

    return properties


# =========================================================
# EMAIL
# =========================================================

def send_enquiry_email(
    name,
    phone,
    email,
    message,
    property_title="General Enquiry"
):

    try:

        msg = EmailMessage()

        msg["Subject"] = (
            f"New PropFind Enquiry - {property_title}"
        )

        msg["From"] = os.environ["EMAIL_ADDRESS"]
        msg["To"] = os.environ["EMAIL_ADDRESS"]

        msg.set_content(
            f"""New enquiry received on PropFind.

Property: {property_title}

Name: {name}
Phone: {phone}
Email: {email}

Message:
{message}
"""
        )

        with smtplib.SMTP_SSL(
            "smtp.gmail.com",
            465
        ) as smtp:

            smtp.login(
                os.environ["EMAIL_ADDRESS"],
                os.environ["EMAIL_APP_PASSWORD"]
            )

            smtp.send_message(msg)

    except Exception as e:

        print(
            "Email notification failed:",
            e
        )


# =========================================================
# JINJA FILTERS
# =========================================================

app.jinja_env.filters["money"] = money


# =========================================================
# GLOBAL TEMPLATE VARIABLES
# =========================================================

def safe_next(value, fallback="/"):
    """Accept local absolute paths only, never external redirect targets."""
    if not value or "\\" in value or any(ord(c) < 32 for c in value):
        return fallback
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return fallback
    return value


def current_admin():
    row = db().execute("SELECT * FROM admins WHERE id=?", (session.get("admin_id"),)).fetchone()
    if row and secrets.compare_digest(session.get("admin_version", ""), row["password_hash"]):
        return row
    session.pop("admin_id", None)
    session.pop("admin_version", None)
    return None


@app.context_processor
def globals_for_templates():
    return {"admin": current_admin() is not None, "year": datetime.now().year}


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    featured_rows = db().execute(
        """
        SELECT *
        FROM properties
        WHERE published=1
        AND featured=1
        ORDER BY created_at DESC
        LIMIT 3
        """
    ).fetchall()

    latest_rows = db().execute(
        """
        SELECT *
        FROM properties
        WHERE published=1
        ORDER BY created_at DESC
        LIMIT 6
        """
    ).fetchall()

    # Add uploaded images
    featured = add_images_to_properties(
        featured_rows
    )

    latest = add_images_to_properties(
        latest_rows
    )

    return render_template(
        "index.html",
        featured=featured,
        latest=latest
    )


# =========================================================
# ALL PROPERTIES
# =========================================================

@app.route("/properties")
def properties():

    filters = {
        key: request.args.get(
            key,
            ""
        ).strip()

        for key in (
            "q",
            "purpose",
            "property_type",
            "city",
            "status"
        )
    }

    query = """
        SELECT *
        FROM properties
        WHERE published=1
    """

    values = []

    # Search
    if filters["q"]:

        query += """
            AND (
                title LIKE ?
                OR location LIKE ?
                OR city LIKE ?
            )
        """

        values += [
            f"%{filters['q']}%"
        ] * 3

    # Filters
    for key in (
        "purpose",
        "property_type",
        "city",
        "status"
    ):

        if filters[key]:

            query += f" AND {key} = ?"

            values.append(
                filters[key]
            )

    # Minimum price
    if request.args.get("min_price"):

        query += " AND price >= ?"

        values.append(
            request.args["min_price"]
        )

    # Maximum price
    if request.args.get("max_price"):

        query += " AND price <= ?"

        values.append(
            request.args["max_price"]
        )

    # Sorting
    if request.args.get("sort") == "low":

        query += " ORDER BY price ASC"

    elif request.args.get("sort") == "high":

        query += " ORDER BY price DESC"

    else:

        query += " ORDER BY created_at DESC"

    items = db().execute(
        query,
        values
    ).fetchall()

    # Add images to property cards
    items = add_images_to_properties(
        items
    )

    return render_template(
        "properties.html",
        properties=items,
        filters=filters
    )


# =========================================================
# PROPERTY DETAILS
# =========================================================

@app.route(
    "/property/<slug>",
    methods=["GET", "POST"]
)
def property_detail(slug):

    item = db().execute(
        """
        SELECT *
        FROM properties
        WHERE slug=?
        AND published=1
        """,
        (slug,)
    ).fetchone()

    if not item:

        abort(404)

    # Enquiry
    if request.method == "POST":

        name = request.form["name"]

        phone = request.form["phone"]

        email = request.form.get(
            "email",
            ""
        )

        message = request.form.get(
            "message",
            ""
        )

        db().execute(
            """
            INSERT INTO enquiries(
                name,
                phone,
                email,
                message,
                property_id,
                created_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                name,
                phone,
                email,
                message,
                item["id"],
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )
        )

        db().commit()

        # Email notification
        send_enquiry_email(
            name,
            phone,
            email,
            message,
            item["title"]
        )

        flash(
            "Thanks. Our property advisor will contact you shortly.",
            "success"
        )

        return redirect(
            url_for(
                "property_detail",
                slug=slug
            )
        )

    # Property images
    images = db().execute(
        """
        SELECT *
        FROM property_images
        WHERE property_id=?
        ORDER BY id ASC
        """,
        (item["id"],)
    ).fetchall()

    # Similar properties
    similar_rows = db().execute(
        """
        SELECT *
        FROM properties
        WHERE published=1
        AND id!=?
        AND property_type=?
        LIMIT 3
        """,
        (
            item["id"],
            item["property_type"]
        )
    ).fetchall()

    similar = add_images_to_properties(
        similar_rows
    )

    return render_template(
        "property_detail.html",
        property=item,
        images=images,
        similar=similar
    )


# =========================================================
# ABOUT
# =========================================================

@app.route("/about")
def about():
    return render_template("about.html")


# =========================================================
# CONTACT
# =========================================================

@app.route(
    "/contact",
    methods=["GET", "POST"]
)
def contact():

    if request.method == "POST":

        db().execute(
            """
            INSERT INTO enquiries(
                name,
                phone,
                email,
                message,
                created_at
            )
            VALUES(?,?,?,?,?)
            """,
            (
                request.form["name"],
                request.form["phone"],
                request.form.get(
                    "email",
                    ""
                ),
                request.form.get(
                    "message",
                    ""
                ),
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )
        )

        db().commit()

        flash(
            "Your enquiry is with our team.",
            "success"
        )

        return redirect(
            url_for("contact")
        )

    return render_template(
        "contact.html"
    )



# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        admin = db().execute(
            """
            SELECT *
            FROM admins
            WHERE email=?
            """,
            (
                request.form.get("email", "").strip().lower(),
            )
        ).fetchone()

        if (
            admin
            and check_password_hash(
                admin["password_hash"],
                request.form.get("password", "")
            )
        ):

            session.clear()

            session["admin_id"] = admin["id"]
            session["admin_version"] = admin["password_hash"]

            session["csrf"] = (
                secrets.token_urlsafe(24)
            )

            return redirect(
                safe_next(request.args.get("next"), url_for("admin_dashboard"))
            )

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template(
        "admin/login.html"
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.post("/admin/logout")
@admin_required
def admin_logout():

    session.clear()

    return redirect(
        url_for("admin_login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    counts = {
        key: db().execute(sql).fetchone()[0]

        for key, sql in {

            "total":
                "SELECT COUNT(*) FROM properties",

            "published":
                "SELECT COUNT(*) FROM properties WHERE published=1",

            "drafts":
                "SELECT COUNT(*) FROM properties WHERE published=0",

            "sale":
                "SELECT COUNT(*) FROM properties WHERE purpose='Sale'",

            "rent":
                "SELECT COUNT(*) FROM properties WHERE purpose='Rent'",

            "enquiries":
                "SELECT COUNT(*) FROM enquiries"

        }.items()
    }

    recent = db().execute(
        """
        SELECT *
        FROM enquiries
        ORDER BY created_at DESC
        LIMIT 5
        """
    ).fetchall()

    return render_template(
        "admin/dashboard.html",
        counts=counts,
        recent=recent
    )


# =========================================================
# ADMIN PROPERTIES
# =========================================================

@app.route("/admin/properties")
@admin_required
def admin_properties():

    properties_list = db().execute(
        """
        SELECT *
        FROM properties
        ORDER BY created_at DESC
        """
    ).fetchall()

    return render_template(
        "admin/properties.html",
        properties=properties_list
    )


# =========================================================
# PROPERTY FORM DATA
# =========================================================

def property_fields(form):

    return (
        form["title"],

        slugify(form["title"])
        + "-"
        + secrets.token_hex(2),

        form["property_type"],

        form["purpose"],

        int(
            form["price"] or 0
        ),

        form["location"],

        form["city"],

        form.get(
            "address",
            ""
        ),

        int(
            form.get(
                "area"
            ) or 0
        ),

        int(
            form.get(
                "bedrooms"
            ) or 0
        ),

        int(
            form.get(
                "bathrooms"
            ) or 0
        ),

        form.get(
            "parking",
            ""
        ),

        form.get(
            "furnishing",
            ""
        ),

        form["status"],

        form.get(
            "description",
            ""
        ),

        form.get(
            "features",
            ""
        ),

        form.get(
            "maps_url",
            ""
        ),

        form.get(
            "contact_phone",
            BUSINESS["phone"]
        ),

        int(
            "featured" in form
        ),

        int(
            "published" in form
        )
    )


# =========================================================
# ADD / EDIT PROPERTY
# =========================================================

@app.route(
    "/admin/properties/new",
    methods=["GET", "POST"]
)
@app.route(
    "/admin/properties/<int:property_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def property_form(property_id=None):

    item = (
        db().execute(
            """
            SELECT *
            FROM properties
            WHERE id=?
            """,
            (property_id,)
        ).fetchone()
        if property_id
        else None
    )

    if property_id is not None and item is None:
        abort(404)

    if request.method == "POST":

        fields = property_fields(
            request.form
        )

        connection = db()

        # EDIT
        if item:

            connection.execute(
                """
                UPDATE properties SET
                    title=?,
                    slug=?,
                    property_type=?,
                    purpose=?,
                    price=?,
                    location=?,
                    city=?,
                    address=?,
                    area=?,
                    bedrooms=?,
                    bathrooms=?,
                    parking=?,
                    furnishing=?,
                    status=?,
                    description=?,
                    features=?,
                    maps_url=?,
                    contact_phone=?,
                    featured=?,
                    published=?
                WHERE id=?
                """,
                fields + (
                    property_id,
                )
            )

        # NEW PROPERTY
        else:

            connection.execute(
                """
                INSERT INTO properties(
                    title,
                    slug,
                    property_type,
                    purpose,
                    price,
                    location,
                    city,
                    address,
                    area,
                    bedrooms,
                    bathrooms,
                    parking,
                    furnishing,
                    status,
                    description,
                    features,
                    maps_url,
                    contact_phone,
                    featured,
                    published,
                    created_at
                )
                VALUES(
                    ?,?,?,?,?,?,?,?,?,?,
                    ?,?,?,?,?,?,?,?,?,?,
                    ?
                )
                """,
                fields + (
                    datetime.now().isoformat(
                        timespec="seconds"
                    ),
                )
            )

        saved_id = (
            property_id
            or connection.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]
        )

        # Upload property images
        for image in request.files.getlist(
            "images"
        ):

            if (
                image
                and allowed(
                    image.filename
                )
            ):

                filename = (
                    secrets.token_hex(8)
                    + "-"
                    + secure_filename(
                        image.filename
                    )
                )

                image.save(
                    Path(
                        UPLOAD_FOLDER
                    ) / filename
                )

                connection.execute(
                    """
                    INSERT INTO property_images(
                        property_id,
                        filename,
                        alt_text
                    )
                    VALUES(?,?,?)
                    """,
                    (
                        saved_id,
                        filename,
                        request.form["title"]
                    )
                )

        connection.commit()

        flash(
            "Property saved.",
            "success"
        )

        return redirect(
            url_for("admin_properties")
        )

    # Existing images
    images = (
        db().execute(
            """
            SELECT *
            FROM property_images
            WHERE property_id=?
            ORDER BY id ASC
            """,
            (property_id,)
        ).fetchall()
        if item
        else []
    )

    return render_template(
        "admin/property_form.html",
        property=item,
        images=images
    )


# =========================================================
# DELETE PROPERTY
# =========================================================

@app.post(
    "/admin/properties/<int:property_id>/delete"
)
@admin_required
def delete_property(property_id):

    db().execute(
        "DELETE FROM properties WHERE id=?",
        (property_id,)
    )

    db().commit()

    return redirect(
        url_for("admin_properties")
    )


# =========================================================
# DELETE PROPERTY IMAGE
# =========================================================

@app.post(
    "/admin/images/<int:image_id>/delete"
)
@admin_required
def delete_image(image_id):

    image = db().execute(
        """
        SELECT *
        FROM property_images
        WHERE id=?
        """,
        (image_id,)
    ).fetchone()

    if image:

        Path(
            UPLOAD_FOLDER,
            image["filename"]
        ).unlink(
            missing_ok=True
        )

        db().execute(
            """
            DELETE FROM property_images
            WHERE id=?
            """,
            (image_id,)
        )

        db().commit()

    return redirect(
        request.referrer
        or url_for("admin_properties")
    )


# =========================================================
# ADMIN ENQUIRIES
# =========================================================

@app.route("/admin/enquiries")
@admin_required
def enquiries():

    enquiry_list = db().execute(
        """
        SELECT
            e.*,
            p.title
        FROM enquiries e
        LEFT JOIN properties p
            ON p.id=e.property_id
        ORDER BY e.created_at DESC
        """
    ).fetchall()

    return render_template(
        "admin/enquiries.html",
        enquiries=enquiry_list
    )


# =========================================================
# MARK ENQUIRY AS READ
# =========================================================

@app.post(
    "/admin/enquiries/<int:enquiry_id>/read"
)
@admin_required
def mark_read(enquiry_id):

    db().execute(
        """
        UPDATE enquiries
        SET is_read=1
        WHERE id=?
        """,
        (enquiry_id,)
    )

    db().commit()

    return redirect(
        url_for("enquiries")
    )


# =========================================================
# DELETE ENQUIRY
# =========================================================

@app.post(
    "/admin/enquiries/<int:enquiry_id>/delete"
)
@admin_required
def delete_enquiry(enquiry_id):

    db().execute(
        """
        DELETE FROM enquiries
        WHERE id=?
        """,
        (enquiry_id,)
    )

    db().commit()

    return redirect(
        url_for("enquiries")
    )


# =========================================================
# SITEMAP
# =========================================================

@app.route("/sitemap.xml")
def sitemap():

    properties_list = db().execute(
        """
        SELECT slug
        FROM properties
        WHERE published=1
        """
    ).fetchall()

    return (
        render_template(
            "sitemap.xml",
            properties=properties_list
        ),
        200,
        {
            "Content-Type":
                "application/xml"
        }
    )


# =========================================================
# ROBOTS.TXT
# =========================================================

@app.route("/robots.txt")
def robots():

    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Sitemap: "
        + url_for(
            "sitemap",
            _external=True
        ),
        200,
        {
            "Content-Type":
                "text/plain"
        }
    )


@app.cli.command("set-admin")
@click.option("--email", prompt="Your admin email")
@click.password_option(confirmation_prompt=True)
def set_admin(email, password):
    """Set the sole owner account locally. No public signup or default password."""
    email = email.strip().lower()
    if "@" not in email or len(password) < 12:
        raise click.ClickException("Use a valid email and a password of at least 12 characters.")
    connection = db()
    connection.execute("DELETE FROM admins")
    connection.execute("INSERT INTO admins(email,password_hash) VALUES (?,?)",
                       (email, generate_password_hash(password)))
    connection.commit()
    click.echo("Private admin account saved. Previous admin sessions are invalidated.")


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

with app.app_context():
    init_db()


# =========================================================
# RUN APP
# =========================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )