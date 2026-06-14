from . import db


class Frequencia(db.Model):
    __tablename__ = "frequencias"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey("alunos.id"),
        nullable=False
    )

    data = db.Column(
        db.String(20),
        nullable=False
    )

    hora_entrada = db.Column(
        db.String(10)
    )

    hora_saida = db.Column(
        db.String(10)
    )

    duracao_horas = db.Column(
        db.Float,
        default=0
    )

    disciplinas = db.Column(
        db.Text
    )

    observacoes = db.Column(
        db.Text
    )

    aluno = db.relationship(
        "Aluno",
        backref="frequencias"
    )