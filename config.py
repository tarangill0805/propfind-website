from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database" / "realestate.db"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"

# Edit business identity here; templates read from this single configuration object.
BUSINESS = {
    "name": "Propfind Estates",
    "tagline": "Spaces with a sense of belonging.",
    "phone": "+91 9417566773",
    "email": "propfindofficial@gmail.com",
    "address": "Sector 68, near Jubilee Walk, Mohali, Punjab",
    "whatsapp": "91 9417566773",
    "logo": "NS",
    "social": {"instagram": "#", "facebook": "#", "linkedin": "#"},
}
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
