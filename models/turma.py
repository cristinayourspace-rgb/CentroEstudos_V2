from . import db


class Turma(db.Model):

    __tablename__ = "turmas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    ano_escolar = db.Column(
        db.String(20)
    )

    observacoes = db.Column(
        db.Text
    )