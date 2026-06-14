from . import db


class Evento(db.Model):

    __tablename__ = "eventos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    titulo = db.Column(
        db.String(200),
        nullable=False
    )

    data = db.Column(
        db.String(20),
        nullable=False
    )

    tipo = db.Column(
        db.String(50),
        default="Teste"
    )

    nao_letivo = db.Column(
        db.Boolean,
        default=False
    )

    descricao = db.Column(
        db.Text
    )
