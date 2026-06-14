from . import db


class Nota(db.Model):
    __tablename__ = "notas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey("alunos.id"),
        nullable=False
    )

    disciplina = db.Column(
        db.String(100),
        nullable=False
    )

    nota = db.Column(
        db.Float,
        nullable=False
    )

    data_avaliacao = db.Column(
        db.String(20),
        nullable=False
    )

    aluno = db.relationship(
        "Aluno",
        backref="notas"
    )