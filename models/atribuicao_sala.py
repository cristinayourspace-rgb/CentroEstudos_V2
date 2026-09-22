from . import db


class ConfiguracaoSalas(db.Model):
    __tablename__ = "configuracoes_salas"

    id = db.Column(db.Integer, primary_key=True)
    numero_salas = db.Column(db.Integer, nullable=False, default=2)


class PlaneamentoSala(db.Model):
    __tablename__ = "planeamentos_salas"

    id = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.String(20), nullable=False)
    sala_numero = db.Column(db.Integer, nullable=False)
    observacoes = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "dia_semana",
            "sala_numero",
            name="uq_planeamento_sala_dia_numero",
        ),
    )


class AtribuicaoSala(db.Model):
    __tablename__ = "atribuicoes_salas"

    id = db.Column(db.Integer, primary_key=True)
    planeamento_id = db.Column(
        db.Integer,
        db.ForeignKey("planeamentos_salas.id"),
        nullable=False,
    )
    turma_id = db.Column(
        db.Integer,
        db.ForeignKey("turmas.id"),
        nullable=True,
    )
    texto_livre = db.Column(db.String(200))
    ordem = db.Column(db.Integer, nullable=False, default=0)
