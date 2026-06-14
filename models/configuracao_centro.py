from models import db


class ConfiguracaoCentro(db.Model):

    __tablename__ = "configuracao_centro"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome_centro = db.Column(
        db.String(200),
        default=""
    )

    morada = db.Column(
        db.String(300),
        default=""
    )

    codigo_postal = db.Column(
        db.String(20),
        default=""
    )

    telefone = db.Column(
        db.String(50),
        default=""
    )

    whatsapp = db.Column(
        db.String(50),
        default=""
    )

    email = db.Column(
        db.String(200),
        default=""
    )

    logo = db.Column(
        db.String(300),
        default=""
    )