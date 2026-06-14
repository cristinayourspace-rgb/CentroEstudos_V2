from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from models import db
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

    return redirect(
        url_for("calendario.calendario")
    )


@testes_bp.route(
    "/testes/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_teste(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    teste = Teste.query.get_or_404(id)

    if request.method == "POST":

        teste.aluno_id = None
        teste.escola = request.form["escola"].strip()
        teste.turma = request.form["turma"].strip()
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
            url_for(
                "calendario.calendario",
                mes=int(teste.data_teste[5:7]),
                ano=int(teste.data_teste[0:4])
            )
        )

    return render_template(
        "editar_testes.html",
        teste=teste
    )


@testes_bp.route(
    "/testes/apagar/<int:id>"
)
def apagar_teste(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    teste = Teste.query.get_or_404(id)

    db.session.delete(teste)
    db.session.commit()

    return redirect(
        url_for("calendario.calendario")
    )
