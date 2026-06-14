from . import db


class Teste(db.Model):

    __tablename__ = "testes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    aluno_id = db.Column(
        db.Integer,
        db.ForeignKey("alunos.id"),
        nullable=True
    )

    escola = db.Column(
        db.String(150),
        default=""
    )

    turma = db.Column(
        db.String(100),
        default=""
    )

    disciplina = db.Column(
        db.String(100),
        nullable=False
    )

    data_teste = db.Column(
        db.String(20),
        nullable=False
    )

    matriz = db.Column(
        db.Text
    )

    observacoes = db.Column(
        db.Text
    )
