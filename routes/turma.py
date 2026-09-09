from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from models import db
from models.aluno import Aluno
from models.turma import Turma


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


# ------------------------------------------------------------------
# CRIAR TURMA
# (usado a partir do modal "Turmas" na página de Alunos)
# ------------------------------------------------------------------

@turma_bp.route("/turmas/criar", methods=["POST"])
def criar_turma():

    nome = request.form.get("nome", "").strip()
    escola = request.form.get("escola", "").strip()
    diretor_turma = request.form.get("diretor_turma", "").strip()

    if not nome or not escola:

        return redirect(
            url_for("alunos.listar_alunos", turmas_erro=1, aba="criar")
        )

    turma_existente = Turma.query.filter_by(
        nome=nome,
        escola=escola
    ).first()

    if not turma_existente:

        turma = Turma()

        turma.nome = nome
        turma.escola = escola
        turma.diretor_turma = diretor_turma or None

        db.session.add(turma)
        db.session.commit()

    return redirect(
        url_for("alunos.listar_alunos", turmas_ok=1, aba="criar")
    )


# ------------------------------------------------------------------
# ATRIBUIR TURMA A ALUNOS
# Atualiza o campo Aluno.turma (e Aluno.escola, para manter a
# coerência com a escola da turma escolhida) para todos os alunos
# selecionados. Como este campo é usado em toda a aplicação
# (listagens, horários, etc.), a alteração propaga-se automaticamente.
# ------------------------------------------------------------------

@turma_bp.route("/turmas/atribuir", methods=["POST"])
def atribuir_turma():

    turma_id = request.form.get("turma_id", "")
    aluno_ids = request.form.getlist("aluno_ids")

    turma = Turma.query.get(turma_id) if turma_id else None

    if not turma or not aluno_ids:

        return redirect(
            url_for("alunos.listar_alunos", turmas_erro=1, aba="atribuir")
        )

    for aluno_id in aluno_ids:

        aluno = Aluno.query.get(aluno_id)

        if not aluno:
            continue

        aluno.turma = turma.nome

        if turma.escola:
            aluno.escola = turma.escola

    db.session.commit()

    return redirect(
        url_for("alunos.listar_alunos", turmas_ok=1, aba="atribuir")
    )
