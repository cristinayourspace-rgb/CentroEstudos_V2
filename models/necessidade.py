from . import db


class Necessidade(db.Model):
    __tablename__ = "necessidades"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )