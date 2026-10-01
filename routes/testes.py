from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

import unicodedata
from datetime import datetime

from models import db
from models.teste import Teste


testes_bp = Blueprint(
    "testes",
    __name__
)


def normalizar_texto(valor):
    """'  Escola  BÁSICA ' -> 'escola basica'."""
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return " ".join(texto.lower().split())


def procurar_teste_duplicado(
    data_teste,
    escola,
    turma,
    ignorar_id=None
):
    """
    Devolve um teste com a mesma data, escola e turma, ou None.
    """
    chave_escola = normalizar_texto(escola)
    chave_turma = normalizar_texto(turma)

    candidatos = Teste.query.filter_by(
        data_teste=(data_teste or "").strip()
    ).all()

    for candidato in candidatos:

        if ignorar_id is not None and candidato.id == ignorar_id:
            continue

        if (
            normalizar_texto(candidato.escola) == chave_escola
            and normalizar_texto(candidato.turma) == chave_turma
        ):
            return candidato

    return None


def mensagem_teste_duplicado(duplicado):
    try:
        data_pt = datetime.strptime(
            duplicado.data_teste,
            "%Y-%m-%d"
        ).strftime("%d/%m/%Y")
    except ValueError:
        data_pt = duplicado.data_teste

    return (
        "Já existe um teste registado para "
        f"{data_pt}, turma {duplicado.turma}, "
        f"escola {duplicado.escola} "
        f"({duplicado.disciplina})."
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

    teste = Teste.query.get_or_404(id)

    if request.method == "POST":

        duplicado = procurar_teste_duplicado(
            request.form["data_teste"],
            request.form["escola"],
            request.form["turma"],
            ignorar_id=teste.id
        )

        if duplicado:

            flash(
                mensagem_teste_duplicado(duplicado)
                + " As alterações não foram guardadas.",
                "aviso"
            )

            return render_template(
                "editar_testes.html",
                teste=teste
            )

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
