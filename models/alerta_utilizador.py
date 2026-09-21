from . import db


class AlertaUtilizador(db.Model):

    __tablename__ = "alertas_utilizadores"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    utilizador_id = db.Column(
        db.Integer,
        db.ForeignKey("utilizadores.id"),
        nullable=False
    )

    tipo = db.Column(
        db.String(50),
        nullable=False
    )

    data = db.Column(
        db.String(10),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "utilizador_id",
            "tipo",
            "data",
            name="uq_alerta_utilizador_tipo_data"
        ),
    )
