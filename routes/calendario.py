from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from models import db
from models.aluno import Aluno
from models.evento import Evento
from models.teste import Teste

import calendar
from datetime import datetime


calendario_bp = Blueprint(
    "calendario",
    __name__
)


CORES_TIPO = {
    "Feriado": "#ef4444",
    "Paragem Letiva": "#f97316",
    "Férias": "#facc15",
    "Evento": "#3b82f6",
    "Reunião": "#22c55e",
    "Aviso": "#a855f7",
    "Teste": "#0ea5e9",
    "Outros": "#6b7280"
}


MESES_PT = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro"
}


@calendario_bp.route(
    "/calendario",
    methods=["GET", "POST"]
)
def calendario():

    if (
        session.get("perfil") == "colaborador"
        and request.method == "POST"
    ):
        return render_template(
            "acesso_negado.html"
        )

    if request.method == "POST":

        registo_tipo = request.form.get(
            "registo_tipo",
            "evento"
        )

        if registo_tipo == "teste":

            teste = Teste(
                escola=request.form["escola"].strip(),
                turma=request.form["turma"].strip(),
                disciplina=request.form["disciplina"].strip(),
                data_teste=request.form["data_teste"],
                matriz=request.form.get(
                    "matriz",
                    ""
                ).strip(),
                observacoes=request.form.get(
                    "observacoes",
                    ""
                ).strip()
            )

            db.session.add(teste)

        else:

            evento = Evento(
                data=request.form["data"],
                tipo=request.form["tipo"],
                titulo=request.form["titulo"],
                descricao=request.form.get(
                    "descricao",
                    ""
                ),
                nao_letivo=(
                    "nao_letivo" in request.form
                )
            )

            db.session.add(evento)

        db.session.commit()

        return redirect(
            url_for("calendario.calendario")
        )

    hoje = datetime.today()

    mes = int(
        request.args.get(
            "mes",
            hoje.month
        )
    )

    ano = int(
        request.args.get(
            "ano",
            hoje.year
        )
    )

    calendario_mes = calendar.monthcalendar(
        ano,
        mes
    )

    eventos_mes = {}

    eventos = Evento.query.order_by(
        Evento.data.asc()
    ).all()

    testes = Teste.query.order_by(
        Teste.data_teste.asc()
    ).all()

    # EVENTOS

    for evento in eventos:

        try:

            data_evento = datetime.strptime(
                evento.data,
                "%Y-%m-%d"
            )

            if (
                data_evento.month == mes
                and data_evento.year == ano
            ):

                chave = data_evento.day

                if chave not in eventos_mes:
                    eventos_mes[chave] = []

                eventos_mes[chave].append(
                    evento
                )

        except Exception:
            pass

    # TESTES

    for teste in testes:

        try:

            data_teste = datetime.strptime(
                teste.data_teste,
                "%Y-%m-%d"
            )

            if (
                data_teste.month == mes
                and data_teste.year == ano
            ):

                chave = data_teste.day

                if chave not in eventos_mes:
                    eventos_mes[chave] = []

                eventos_mes[chave].append(
                    {
                        "titulo": (
                            f"Teste - {teste.disciplina} - "
                            f"{teste.escola} - "
                            f"Turma {teste.turma}"
                        ),
                        "tipo": "Teste",
                        "data": teste.data_teste
                    }
                )

        except Exception:
            pass

    alunos = Aluno.query.order_by(
        Aluno.escola,
        Aluno.turma
    ).all()

    escolas = sorted(
        {
            aluno.escola.strip()
            for aluno in alunos
            if aluno.escola and aluno.escola.strip()
        }
    )

    turmas = sorted(
        {
            aluno.turma.strip()
            for aluno in alunos
            if aluno.turma and aluno.turma.strip()
        }
    )

    return render_template(
        "calendario.html",
        calendario_mes=calendario_mes,
        eventos=eventos_mes,
        mes=mes,
        ano=ano,
        nome_mes=MESES_PT[mes],
        hoje=datetime.today(),
        lista_eventos=eventos,
        lista_testes=testes,
        escolas=escolas,
        turmas=turmas,
        cores_tipo=CORES_TIPO
    )


@calendario_bp.route(
    "/calendario/dia/<data>"
)
def detalhe_dia(data):

    eventos = Evento.query.filter_by(
        data=data
    ).all()

    testes = Teste.query.filter_by(
        data_teste=data
    ).all()

    registos = []

    for evento in eventos:

        registos.append(
            {
                "id": evento.id,
                "titulo": evento.titulo,
                "data": evento.data,
                "tipo": evento.tipo,
                "descricao": evento.descricao,
                "nao_letivo": evento.nao_letivo,
                "origem": "evento",
                "editar_url": url_for(
                    "calendario.editar_evento",
                    id=evento.id
                ),
                "apagar_url": url_for(
                    "calendario.apagar_evento",
                    id=evento.id
                ),
                "confirmacao_apagar": (
                    "Deseja apagar este registo?"
                )
            }
        )

    for teste in testes:

        registos.append(
            {
                "id": teste.id,
                "titulo": f"Teste - {teste.disciplina}",
                "data": teste.data_teste,
                "tipo": "Teste",
                "descricao": teste.observacoes,
                "matriz": teste.matriz,
                "escola": teste.escola,
                "turma": teste.turma,
                "nao_letivo": False,
                "origem": "teste",
                "editar_url": url_for(
                    "testes.editar_teste",
                    id=teste.id
                ),
                "apagar_url": url_for(
                    "testes.apagar_teste",
                    id=teste.id
                ),
                "confirmacao_apagar": (
                    "Apagar este teste?"
                )
            }
        )

    return render_template(
        "calendario_dia.html",
        data=data,
        eventos=registos,
        cores_tipo=CORES_TIPO
    )


@calendario_bp.route(
    "/calendario/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_evento(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    evento = Evento.query.get_or_404(id)

    if request.method == "POST":

        evento.data = request.form["data"]
        evento.tipo = request.form["tipo"]
        evento.titulo = request.form["titulo"]
        evento.descricao = request.form.get(
            "descricao",
            ""
        )

        evento.nao_letivo = (
            "nao_letivo" in request.form
        )

        db.session.commit()

        return redirect(
            url_for("calendario.calendario")
        )

    return render_template(
        "editar_evento.html",
        evento=evento
    )


@calendario_bp.route(
    "/calendario/apagar/<int:id>"
)
def apagar_evento(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    evento = Evento.query.get_or_404(id)

    db.session.delete(evento)
    db.session.commit()

    return redirect(
        url_for("calendario.calendario")
    )
