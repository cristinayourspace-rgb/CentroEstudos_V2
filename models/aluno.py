from . import db


# =====================================
# TABELA INTERMÉDIA
# ALUNO x NECESSIDADES
# =====================================

aluno_necessidades = db.Table(
    "aluno_necessidades",

    db.Column(
        "aluno_id",
        db.Integer,
        db.ForeignKey("alunos.id")
    ),

    db.Column(
        "necessidade_id",
        db.Integer,
        db.ForeignKey("necessidades.id")
    )
)


# =====================================
# TABELA INTERMÉDIA
# ALUNO x OBJETIVOS
# =====================================

aluno_objetivos = db.Table(
    "aluno_objetivos",

    db.Column(
        "aluno_id",
        db.Integer,
        db.ForeignKey("alunos.id")
    ),

    db.Column(
        "objetivo_id",
        db.Integer,
        db.ForeignKey("objetivos.id")
    )
)


class Aluno(db.Model):

    __tablename__ = "alunos"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    codigo = db.Column(
        db.String(5),
        unique=True,
        nullable=False
    )

    nome = db.Column(
        db.String(150),
        nullable=False
    )

    data_nascimento = db.Column(
        db.String(20)
    )

    escola = db.Column(
        db.String(150)
    )

    ano_escolar = db.Column(
        db.String(50)
    )

    turma = db.Column(
        db.String(100)
    )

    encarregado = db.Column(
        db.String(150),
        nullable=False
    )

    telefone = db.Column(
        db.String(30),
        nullable=False
    )

    email = db.Column(
        db.String(150)
    )

    pacote_horas = db.Column(
        db.Float,
        default=0
    )

    horas_restantes = db.Column(
        db.Float,
        default=0
    )

    ativo = db.Column(
        db.Boolean,
        default=True
    )

    # =====================================
    # PERFIL PEDAGÓGICO
    # =====================================

    observacoes_pedagogicas = db.Column(
        db.Text
    )

    necessidades = db.relationship(
        "Necessidade",
        secondary=aluno_necessidades,
        lazy="subquery",
        backref=db.backref(
            "alunos",
            lazy=True
        )
    )

    objetivos = db.relationship(
        "Objetivo",
        secondary=aluno_objetivos,
        lazy="subquery",
        backref=db.backref(
            "alunos",
            lazy=True
        )
    )

    testes = db.relationship(
        "Teste",
        backref="aluno",
        lazy=True
    )