from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from models import db
from models.aluno import Aluno
from models.evento import Evento
from models.teste import Teste
from routes.testes import (
    procurar_teste_duplicado,
    mensagem_teste_duplicado
)

import calendar
import unicodedata
import zlib
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


# Cor fixa por disciplina (a mesma em qualquer ano ou turma).
# O reconhecimento e feito pelo inicio do nome, sem acentos nem
# maiusculas: "Matemática A" e "MATEMATICA" -> Matemática.
# A ordem importa: "historia e geografia" antes de "historia".
DISCIPLINAS_CORES = [
    ("matematica", "Matemática", "#2563eb"),
    ("portugues", "Português", "#db2777"),
    ("ingles", "Inglês", "#7c3aed"),
    ("ciencias", "Ciências", "#16a34a"),
    ("estudo do meio", "Estudo do Meio", "#65a30d"),
    ("historia e geografia", "HGP", "#a16207"),
    ("hgp", "HGP", "#a16207"),
    ("historia", "História", "#9a3412"),
    ("geografia", "Geografia", "#0d9488"),
    ("fisico", "Físico-Química", "#0891b2"),
    ("frances", "Francês", "#c026d3"),
    ("espanhol", "Espanhol", "#ea580c"),
]

# Cores para disciplinas fora da lista acima (escolhidas de forma
# estavel a partir do nome, por isso nunca mudam).
CORES_EXTRA = [
    "#0ea5e9",
    "#84cc16",
    "#f43f5e",
    "#14b8a6",
    "#8b5cf6",
    "#f59e0b",
    "#64748b",
    "#d946ef",
]


def _normalizar_disciplina(valor):
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return " ".join(texto.lower().split())


def info_disciplina(disciplina):
    """Devolve (nome para a legenda, cor) de uma disciplina."""
    chave = _normalizar_disciplina(disciplina)

    for prefixo, nome, cor in DISCIPLINAS_CORES:
        if chave.startswith(prefixo):
            return nome, cor

    if not chave:
        return "Teste", CORES_TIPO["Teste"]

    indice = zlib.crc32(chave.encode("utf-8")) % len(CORES_EXTRA)
    return str(disciplina).strip(), CORES_EXTRA[indice]


def cor_disciplina(disciplina):
    return info_disciplina(disciplina)[1]


def legenda_disciplinas(testes):
    """Lista (nome, cor) sem repeticoes, por ordem alfabetica."""
    vistos = {}

    for teste in testes:
        nome, cor = info_disciplina(teste.disciplina)
        vistos[nome] = cor

    return sorted(vistos.items(), key=lambda par: par[0].lower())


@calendario_bp.route(
    "/calendario",
    methods=["GET", "POST"]
)
def calendario():

    if request.method == "POST":

        registo_tipo = request.form.get(
            "registo_tipo",
            "evento"
        )

        if registo_tipo == "teste":

            duplicado = procurar_teste_duplicado(
                request.form["data_teste"],
                request.form["escola"],
                request.form["turma"]
            )

            if duplicado:

                flash(
                    mensagem_teste_duplicado(duplicado)
                    + " O novo teste não foi registado.",
                    "aviso"
                )

                try:
                    mes_dup = int(duplicado.data_teste[5:7])
                    ano_dup = int(duplicado.data_teste[0:4])
                except ValueError:
                    return redirect(
                        url_for("calendario.calendario")
                    )

                return redirect(
                    url_for(
                        "calendario.calendario",
                        mes=mes_dup,
                        ano=ano_dup
                    )
                )

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
                        "cor": cor_disciplina(teste.disciplina),
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
        cores_tipo=CORES_TIPO,
        cor_disciplina=cor_disciplina,
        legenda_disciplinas=legenda_disciplinas(testes)
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
                "cor": cor_disciplina(teste.disciplina),
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
