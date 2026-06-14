from flask import (
    Blueprint,
    render_template
)

from models.aluno import Aluno


turma_bp = Blueprint(
    "turma",
    __name__
)


@turma_bp.route("/turmas")
def turmas():

    alunos = Aluno.query.order_by(
        Aluno.escola,
        Aluno.ano_escolar,
        Aluno.nome
    ).all()

    agrupados = {}

    for aluno in alunos:

        escola = aluno.escola or "Sem Escola"

        turma = aluno.turma or "Sem Turma"

        if escola not in agrupados:
            agrupados[escola] = {}

        if turma not in agrupados[escola]:
            agrupados[escola][turma] = []

        agrupados[escola][turma].append(
            aluno
        )

    return render_template(
        "turmas.html",
        agrupados=agrupados
    )
