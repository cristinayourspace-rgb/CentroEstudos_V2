from . import db


# =====================================================================
# DIAS DA SEMANA — ordem fixa (não alfabética) para apresentação
# e ordenação correta nos horários.
# =====================================================================

DIAS_SEMANA = [
    "Segunda-feira",
    "Terça-feira",
    "Quarta-feira",
    "Quinta-feira",
    "Sexta-feira",
    "Sábado",
    "Domingo",
]

ORDEM_DIAS = {
    dia: indice
    for indice, dia in enumerate(DIAS_SEMANA)
}


class HorarioTurma(db.Model):
    """
    Horário semanal de uma turma.

    O horário NÃO pertence ao aluno — pertence à turma.
    Todos os alunos de uma mesma turma (dentro do mesmo centro
    escolar) partilham o mesmo conjunto de registos desta tabela.

    Os campos `centro_escolar` e `turma` são mantidos como texto
    livre (tal como `Aluno.escola` e `Aluno.turma`), o que permite
    já hoje preparar o terreno para uma futura arquitetura
    multi-tenant: basta no futuro acrescentar uma FK `centro_id`
    e passar a filtrar por ela, sem alterar a estrutura geral.
    """

    __tablename__ = "horarios_turma"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Preparado para futura migração multi-tenant
    # (hoje é apenas texto livre, tal como Aluno.escola)
    centro_escolar = db.Column(
        db.String(150),
        nullable=False
    )

    turma = db.Column(
        db.String(100),
        nullable=False
    )

    dia_semana = db.Column(
        db.String(20),
        nullable=False
    )

    hora_inicio = db.Column(
        db.String(5),
        nullable=False
    )

    hora_fim = db.Column(
        db.String(5),
        nullable=False
    )

    disciplina = db.Column(
        db.String(150),
        nullable=False
    )

    def ordem_dia(self):

        return ORDEM_DIAS.get(
            self.dia_semana,
            len(DIAS_SEMANA)
        )

    def intervalo_formatado(self):

        return f"{self.hora_inicio} às {self.hora_fim}"
