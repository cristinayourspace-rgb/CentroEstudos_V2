from flask import Blueprint, render_template, request, redirect, session

from models import db
from models.aluno import Aluno
from models.nota import Nota


notas_bp = Blueprint(
    "notas",
    __name__
)


import logging

from sqlalchemy import text

from ciclos import ANO_TURMA_SQL, evolucao_notas, medias_notas


def _medias_ciclos():
    """Medias por ciclo e disciplina. So leitura. Nunca parte a pagina: devolve None se falhar."""
    try:
        linhas = db.session.execute(text(
            f"SELECT n.aluno_id, n.disciplina, n.nota, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM notas n JOIN alunos a ON a.id = n.aluno_id "
            "WHERE n.nota IS NOT NULL AND a.ativo IS NOT FALSE"
        )).mappings().all()
        return medias_notas([dict(l) for l in linhas], "todas")
    except Exception:
        db.session.rollback()
        logging.exception("Nao foi possivel calcular as medias por ciclo")
        return None


def _evolucao_ciclos():
    """Evolucao mensal das medias globais por ciclo e disciplina. So leitura. Devolve None se falhar."""
    try:
        linhas = db.session.execute(text(
            f"SELECT n.disciplina, n.nota, n.data_avaliacao, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM notas n JOIN alunos a ON a.id = n.aluno_id "
            "WHERE n.nota IS NOT NULL AND a.ativo IS NOT FALSE"
        )).mappings().all()
        return evolucao_notas([dict(l) for l in linhas])
    except Exception:
        db.session.rollback()
        logging.exception("Nao foi possivel calcular a evolucao das medias por ciclo")
        return None


@notas_bp.route("/notas", methods=["GET", "POST"])
def notas():


    if (
        session.get("perfil") == "colaborador"
        and request.method == "POST"
    ):
        return render_template(
            "acesso_negado.html"
        )

    if request.method == "POST":

        nota = Nota(
            aluno_id=request.form["aluno_id"],
            disciplina=request.form["disciplina"],
            nota=float(request.form["nota"]),
            data_avaliacao=request.form["data_avaliacao"]
        )

        db.session.add(nota)
        db.session.commit()

        return redirect("/notas")

    alunos = Aluno.query.order_by(
        Aluno.nome
    ).all()

    notas = Nota.query.order_by(
        Nota.id.desc()
    ).all()

    return render_template(
        "notas.html",
        alunos=alunos,
        notas=notas,
        medias_ciclos=_medias_ciclos(),
        evolucao_ciclos=_evolucao_ciclos()
    )


@notas_bp.route(
    "/notas/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_nota(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    nota = Nota.query.get_or_404(id)

    if request.method == "POST":

        nota.disciplina = request.form["disciplina"]

        nota.nota = float(
            request.form["nota"]
        )

        nota.data_avaliacao = request.form[
            "data_avaliacao"
        ]

        db.session.commit()

        return redirect("/notas")

    return render_template(
        "editar_nota.html",
        nota=nota
    )


@notas_bp.route("/notas/apagar/<int:id>")
def apagar_nota(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    nota = Nota.query.get_or_404(id)

    db.session.delete(nota)

    db.session.commit()

    return redirect("/notas")