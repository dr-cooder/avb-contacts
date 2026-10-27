"""Fill an empty database with the sample contacts from the Figma mockup.

Usage:  python seed.py

It does nothing if there are already contacts, so running it twice is
harmless and won't overwrite real data.
"""

from app import app
import db

SAMPLE_CONTACTS = [
    ("Andra", "Inde", ["andra.inde@example.com"]),
    ("Archibald", "Burns", ["archie@example.com", "a.burns@example.org"]),
    ("Berk", "Carruth", []),
    ("Craggy", "Bramble", ["craggy.bramble@gmail.com", "cbramble@marcham.com", "craggy3029@yahoo.com"]),
    ("Davita", "de Juares", ["davita@example.com"]),
    ("Dione", "Gibbett", ["dgibbett@example.com"]),
    ("Federico", "Baynham", ["federico.baynham@example.com"]),
    ("Fifi", "Soitoux", ["fifi@example.fr"]),
    ("Florinda", "O'Connell", ["florinda.oconnell@example.ie"]),
    ("Gerry", "Deaville", ["gerry@example.com"]),
    ("Gorden", "Maleney", ["gmaleney@example.com"]),
    ("Jackie", "Gritton", ["jackie.gritton@example.com"]),
    ("Killy", "Akitt", ["killy@example.com"]),
    ("Lavinie", "Nevett", ["lnevett@example.com"]),
    ("Meggie", "Stetson", ["meggie.stetson@example.com"]),
    ("Nedi", "Cray", ["nedi@example.com"]),
    ("Raddie", "Sear", ["raddie.sear@example.com"]),
    ("Sarina", "Scrace", ["sarina@example.com"]),
    ("Theobald", "Marczyk", ["theo.marczyk@example.com"]),
    ("Tudor", "Marcham", ["tudor@marcham.com", "cbramble@marcham.com"]),
]

if __name__ == "__main__":
    # Database code needs an "app context" to know which database to use.
    # Flask creates one automatically during a web request; a script like
    # this one has to create it by hand.
    with app.app_context():
        if db.list_contacts():
            print("Database already has contacts; not seeding.")
        else:
            for first, last, emails in SAMPLE_CONTACTS:
                db.create_contact(first, last, emails)
            print(f"Added {len(SAMPLE_CONTACTS)} sample contacts.")
