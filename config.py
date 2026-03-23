# config.py
import os
from dotenv import load_dotenv

# Lade Umgebungsvariablen aus der .env Datei (primär für lokale Entwicklung)
# Diese Zeile wird auf Railway keine .env-Datei finden, was OK ist, da dort Umgebungsvariablen anders gesetzt werden.
basedir = os.path.abspath(os.path.dirname(__file__))
print(f"DEBUG [config.py]: Lade .env aus basedir: {basedir}") # DEBUG
if os.path.exists(os.path.join(basedir, '.env')):
    print("DEBUG [config.py]: .env Datei GEFUNDEN, wird geladen.") # DEBUG
    load_dotenv(os.path.join(basedir, '.env'))
else:
    print("DEBUG [config.py]: .env Datei NICHT gefunden (erwartet auf Railway).") # DEBUG


class Config:
    print("DEBUG [config.py]: Innerhalb der Config-Klasse, VOR dem Lesen von Umgebungsvariablen.") # DEBUG

    SECRET_KEY = os.environ.get('SECRET_KEY') or 'ein-sehr-geheimer-fallback-schluessel'
    print(f"DEBUG [config.py]: SECRET_KEY gelesen als: {'SET (Länge: ' + str(len(SECRET_KEY)) + ')' if SECRET_KEY != '1234' else 'Fallback verwendet'}") # DEBUG
    
    DATABASE_URL_FROM_ENV = os.environ.get('DATABASE_URL')
    print(f"DEBUG [config.py]: ROHER Wert für DATABASE_URL aus os.environ: '{DATABASE_URL_FROM_ENV}' (Typ: {type(DATABASE_URL_FROM_ENV)})") # DEBUG

    SQLALCHEMY_DATABASE_URI = DATABASE_URL_FROM_ENV # Zuweisung
    
    if SQLALCHEMY_DATABASE_URI and isinstance(SQLALCHEMY_DATABASE_URI, str) and SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        print(f"DEBUG [config.py]: Ersetze 'postgres://' in '{SQLALCHEMY_DATABASE_URI}'") # DEBUG
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace("postgres://", "postgresql://", 1)
        print(f"DEBUG [config.py]: SQLALCHEMY_DATABASE_URI nach replace: '{SQLALCHEMY_DATABASE_URI}'") # DEBUG
    elif not SQLALCHEMY_DATABASE_URI:
        print("DEBUG [config.py]: SQLALCHEMY_DATABASE_URI ist leer oder None VOR der postgres:// Prüfung.") # DEBUG
    elif not isinstance(SQLALCHEMY_DATABASE_URI, str):
        print(f"DEBUG [config.py]: SQLALCHEMY_DATABASE_URI ist kein String, sondern Typ {type(SQLALCHEMY_DATABASE_URI)}.") # DEBUG


    print(f"DEBUG [config.py]: Finale SQLALCHEMY_DATABASE_URI, die gesetzt wird: '{SQLALCHEMY_DATABASE_URI}'") # DEBUG
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERFORMANCE_BENCHMARK = 80.0
print("DEBUG [config.py]: config.py wurde vollständig geladen.") # DEBUG
