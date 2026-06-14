from flask import Blueprint, render_template, request, redirect, session

from models import db
from models.aluno import Aluno
from models.necessidade import Necessidade
from models.objetivo import Objetivo
from models.nota import Nota

import qrcode
import os


alunos_bp = Blueprint(
    "alunos",
    __name__
)


def gerar_codigo():

    ultimo = Aluno.query.order_by(
        Aluno.id.desc()
    ).first()

    if not ultimo:
        return "10001"

    return str(
        int(ultimo.codigo) + 1
    )


def horas_para_hhmm(valor):

    horas = int(valor)

    minutos = int(
        round(
            (valor - horas) * 60
        )
    )

    return f"{horas:02d}:{minutos:02d}"


@alunos_bp.route("/alunos", methods=["GET", "POST"])
def listar_alunos():

    if request.method == "POST":

        codigo = gerar_codigo()

        os.makedirs(
            "static/qrcodes",
            exist_ok=True
        )

        caminho_qr = f"static/qrcodes/{codigo}.png"

        qr = qrcode.make(codigo)

        qr.save(caminho_qr)

        pacote = float(
            request.form.get(
                "pacote_horas",
                0
            ) or 0
        )

        aluno = Aluno(
            codigo=codigo,
            nome=request.form["nome"],
            data_nascimento=request.form["data_nascimento"],
            escola=request.form["escola"],
            ano_escolar=request.form["ano_escolar"],
            encarregado=request.form["encarregado"],
            telefone=request.form["telefone"],
            email=request.form["email"],
            pacote_horas=pacote,
            horas_restantes=pacote,
            observacoes_pedagogicas=request.form.get(
                "observacoes_pedagogicas",
                ""
            )
        )

        necessidades_ids = request.form.getlist(
            "necessidades"
        )

        objetivos_ids = request.form.getlist(
            "objetivos"
        )

        if necessidades_ids:

            aluno.necessidades = (
                Necessidade.query.filter(
                    Necessidade.id.in_(
                        necessidades_ids
                    )
                ).all()
            )

        if objetivos_ids:

            aluno.objetivos = (
                Objetivo.query.filter(
                    Objetivo.id.in_(
                        objetivos_ids
                    )
                ).all()
            )

        db.session.add(aluno)
        db.session.commit()

        return redirect("/alunos")

    alunos = Aluno.query.order_by(
        Aluno.nome
    ).all()

    necessidades = Necessidade.query.order_by(
        Necessidade.nome
    ).all()

    objetivos = Objetivo.query.order_by(
        Objetivo.nome
    ).all()

    return render_template(
        "alunos.html",
        alunos=alunos,
        necessidades=necessidades,
        objetivos=objetivos
    )


@alunos_bp.route("/alunos/ver/<int:id>")
def ver_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    total_horas = 0

    for f in aluno.frequencias:

        total_horas += (
            f.duracao_horas or 0
        )

    notas = Nota.query.filter_by(
        aluno_id=aluno.id
    ).order_by(
        Nota.data_avaliacao.asc()
    ).all()

    medias_dict = {}

    for nota in notas:

        disciplina = nota.disciplina

        if disciplina not in medias_dict:

            medias_dict[disciplina] = {
                "soma": 0,
                "quantidade": 0
            }

        medias_dict[disciplina]["soma"] += nota.nota
        medias_dict[disciplina]["quantidade"] += 1

    medias = []

    for disciplina, dados in medias_dict.items():

        media = round(
            dados["soma"] / dados["quantidade"],
            2
        )

        medias.append(
            {
                "disciplina": disciplina,
                "media": media
            }
        )

    labels_grafico = []
    valores_grafico = []

    for nota in notas:

        labels_grafico.append(
            nota.data_avaliacao
        )

        valores_grafico.append(
            nota.nota
        )

    return render_template(
        "ver_aluno.html",
        aluno=aluno,
        notas=notas,
        medias=medias,
        labels_grafico=labels_grafico,
        valores_grafico=valores_grafico,
        total_horas=horas_para_hhmm(
            total_horas
        ),
        saldo_horas=horas_para_hhmm(
            aluno.horas_restantes
        )
    )


@alunos_bp.route(
    "/alunos/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    if request.method == "POST":

        aluno.nome = request.form["nome"]
        aluno.data_nascimento = request.form["data_nascimento"]
        aluno.escola = request.form["escola"]
        aluno.ano_escolar = request.form["ano_escolar"]
        aluno.encarregado = request.form["encarregado"]
        aluno.telefone = request.form["telefone"]
        aluno.email = request.form["email"]

        aluno.pacote_horas = float(
            request.form.get(
                "pacote_horas",
                0
            ) or 0
        )

        aluno.observacoes_pedagogicas = (
            request.form.get(
                "observacoes_pedagogicas",
                ""
            )
        )

        necessidades_ids = request.form.getlist(
            "necessidades"
        )

        objetivos_ids = request.form.getlist(
            "objetivos"
        )

        aluno.necessidades = (
            Necessidade.query.filter(
                Necessidade.id.in_(
                    necessidades_ids
                )
            ).all()
        )

        aluno.objetivos = (
            Objetivo.query.filter(
                Objetivo.id.in_(
                    objetivos_ids
                )
            ).all()
        )

        db.session.commit()

        return redirect("/alunos")

    necessidades = Necessidade.query.order_by(
        Necessidade.nome
    ).all()

    objetivos = Objetivo.query.order_by(
        Objetivo.nome
    ).all()

    return render_template(
        "editar_aluno.html",
        aluno=aluno,
        necessidades=necessidades,
        objetivos=objetivos
    )


@alunos_bp.route("/alunos/apagar/<int:id>")
def apagar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    db.session.delete(aluno)

    db.session.commit()

    return redirect("/alunos")
