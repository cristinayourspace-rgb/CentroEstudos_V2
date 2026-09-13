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

    escola = db.Column(
        db.String(150)
    )

    diretor_turma = db.Column(
        db.String(150)
    )

    observacoes = db.Column(
        db.Text
    )

    # Disciplinas selecionadas para esta turma.
    # Guardadas como JSON para permitir várias disciplinas e a opção Outros
    # sem alterar a estrutura existente das tabelas de horários.
    disciplinas = db.Column(
        db.Text
    )