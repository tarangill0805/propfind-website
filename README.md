# PropFind — public catalogue, private property management

## Install and set your private admin account (Windows PowerShell)

Extract this ZIP into a NEW folder. Your supplied properties, enquiries and uploaded photos are included.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -r requirements.txt
py -m flask --app app set-admin
py app.py
```

The setup command asks for your email and a new password (minimum 12 characters), then asks you to confirm it. Password input stays hidden. Choose a unique password and keep it private. There is no default account or public signup. Run the same command locally if you need to reset your credentials; it replaces all previous admin accounts and invalidates their sessions.

Public website: http://127.0.0.1:5000
Private admin: http://127.0.0.1:5000/admin/login

Only the signed-in owner can add, edit, publish or delete properties and images, or manage enquiries. Public visitors can browse and contact you without an account. Visitor phone login, OTP and favourites have been removed. Historical visitor database tables are kept unused to avoid deleting old data.

For an existing deployment, back up its database and uploads first, replace the code, and run `py -m flask --app app set-admin` on the server using the existing database. Restart the server. Do not overwrite newer live property data with the ZIP's database.

A private session signing key is generated per installation in `.instance/session.key`. Keep that file private and persistent across restarts. You can instead set a private random `SECRET_KEY` environment variable (at least 32 characters). For HTTPS deployment set `COOKIE_SECURE=1` and use a production WSGI server. Debug mode is disabled. Business details remain in `config.py`.

## Validation

`py -m unittest discover -s tests -v`
