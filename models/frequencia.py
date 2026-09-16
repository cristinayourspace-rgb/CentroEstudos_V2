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

    # Hora em que o aluno chegou ao Centro.
    # Nos registos antigos, continua a representar a hora de entrada
    # usada pelo sistema anterior.
    hora_entrada = db.Column(
        db.String(10)
    )

    # Hora em que o estudo terminou.
    hora_saida = db.Column(
        db.String(10)
    )

    # Duração contabilizada no pacote de horas.
    duracao_horas = db.Column(
        db.Float,
        default=0
    )

    # Disciplinas selecionadas no final do estudo.
    disciplinas = db.Column(
        db.Text
    )

    observacoes = db.Column(
        db.Text
    )

    # Novo:
    # PRESENCA = apenas presença
    # CHEGADA  = chegou, mas ainda está à espera para iniciar estudo
    # ESTUDO   = estudo iniciado
    #
    # Registos antigos ficam com NULL e continuam a ser interpretados
    # segundo a lógica histórica do sistema.
    tipo_registo = db.Column(
        db.String(30),
        nullable=True
    )

    # Novo:
    # Guarda a hora real em que começou a contagem do estudo.
    #
    # Num registo de CHEGADA:
    #   hora_entrada = chegada
    #   hora_inicio_estudo = NULL até clicar em "Iniciar estudo"
    #
    # Num registo de ESTUDO:
    #   contém a hora em que começou a contagem.
    hora_inicio_estudo = db.Column(
        db.String(10),
        nullable=True
    )

    # Novo:
    # ESTUDO_CONCLUIDO = saída normal
    # SAIDA_SOLICITADA  = saída solicitada, contabiliza 2 horas
    #
    # Registos antigos ficam com NULL.
    tipo_saida = db.Column(
        db.String(30),
        nullable=True
    )

    aluno = db.relationship(
        "Aluno",
        backref="frequencias"
    )

