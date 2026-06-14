from flask import Blueprint, render_template, request, redirect, session

from models import db
from models.aluno import Aluno
from models.nota import Nota


notas_bp = Blueprint(
    "notas",
    __name__
)


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
        notas=notas
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