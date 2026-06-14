from . import db


class Objetivo(db.Model):
    __tablename__ = "objetivos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )