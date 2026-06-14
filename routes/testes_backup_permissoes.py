from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for
)

from models import db
from models.aluno import Aluno
from models.teste import Teste


testes_bp = Blueprint(
    "testes",
    __name__
)


@testes_bp.route(
    "/testes",
    methods=["GET", "POST"]
)
def testes():

    if request.method == "POST":

        teste = Teste(
            aluno_id=request.form["aluno_id"],
            disciplina=request.form["disciplina"],
            data_teste=request.form["data_teste"],
            matriz=request.form.get(
                "matriz",
                ""
            ),
            observacoes=request.form.get(
                "observacoes",
                ""
            )
        )

        db.session.add(teste)
        db.session.commit()

        return redirect("/testes")

    alunos = Aluno.query.order_by(
        Aluno.nome
    ).all()

    testes = Teste.query.order_by(
        Teste.data_teste
    ).all()

    return render_template(
        "testes.html",
        alunos=alunos,
        testes=testes
    )


@testes_bp.route(
    "/testes/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_teste(id):

    teste = Teste.query.get_or_404(id)

    if request.method == "POST":

        teste.aluno_id = request.form["aluno_id"]
        teste.disciplina = request.form["disciplina"]
        teste.data_teste = request.form["data_teste"]
        teste.matriz = request.form.get(
            "matriz",
            ""
        )
        teste.observacoes = request.form.get(
            "observacoes",
            ""
        )

        db.session.commit()

        return redirect(
            url_for("testes.testes")
        )

    alunos = Aluno.query.order_by(
        Aluno.nome
    ).all()

    return render_template(
        "editar_teste.html",
        teste=teste,
        alunos=alunos
    )


@testes_bp.route(
    "/testes/apagar/<int:id>"
)
def apagar_teste(id):

    teste = Teste.query.get_or_404(id)

    db.session.delete(teste)
    db.session.commit()

    return redirect(
        url_for("testes.testes")
    )