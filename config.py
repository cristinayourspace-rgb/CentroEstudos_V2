import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = "centro_estudos_v2_2026"

    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{os.path.join(BASE_DIR, 'database', 'centro.db')}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False