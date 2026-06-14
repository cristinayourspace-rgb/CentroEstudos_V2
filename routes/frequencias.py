from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from urllib.parse import quote

from models import db
from models.aluno import Aluno
from models.frequencia import Frequencia
from models.evento import Evento


frequencias_bp = Blueprint(
    "frequencias",
    __name__
)


def horas_para_hhmm(horas):

    total_minutos = int(round(horas * 60))

    horas_int = total_minutos // 60
    minutos = total_minutos % 60

    return f"{horas_int:02d}:{minutos:02d}"


def preparar_historico_frequencias(historico):

    for item in historico:

        item.horas_restantes_formatadas = (
            horas_para_hhmm(
                item.aluno.horas_restantes
            )
        )

        item.duracao_formatada = (
            horas_para_hhmm(
                item.duracao_horas or 0
            )
        )


def dia_permite_frequencia():

    hoje = datetime.now()

    if hoje.weekday() in [5, 6]:

        return (
            False,
            "Hoje é fim de semana."
        )

    data_bd = hoje.strftime(
        "%Y-%m-%d"
    )

    evento = Evento.query.filter_by(
        data=data_bd,
        nao_letivo=True
    ).first()

    if evento:

        return (
            False,
            f"Dia não letivo: {evento.tipo}"
        )

    return True, ""


@frequencias_bp.route(
    "/frequencias",
    methods=["GET", "POST"]
)
def frequencias():

    mensagem = ""
    whatsapp_link = None

    if request.method == "POST":

        permitido, motivo = (
            dia_permite_frequencia()
        )

        if not permitido:

            historico = Frequencia.query.order_by(
                Frequencia.id.desc()
            ).all()

            preparar_historico_frequencias(
                historico
            )

            em_estudo = len([
                f for f in historico
                if not f.hora_saida
            ])

            concluidos = len([
                f for f in historico
                if f.hora_saida
            ])

            return render_template(
                "frequencias.html",
                historico=historico,
                mensagem=motivo,
                whatsapp_link=None,
                em_estudo=em_estudo,
                concluidos=concluidos,
                total=len(historico)
            )

        codigo = request.form["codigo"]

        aluno = Aluno.query.filter_by(
            codigo=codigo
        ).first()

        if not aluno:

            mensagem = (
                "Aluno não encontrado."
            )

        else:

            aberta = Frequencia.query.filter_by(
                aluno_id=aluno.id,
                hora_saida=None
            ).first()

            if not aberta:

                agora = datetime.now()

                frequencia = Frequencia(
                    aluno_id=aluno.id,
                    data=agora.strftime(
                        "%d/%m/%Y"
                    ),
                    hora_entrada=agora.strftime(
                        "%H:%M"
                    )
                )

                db.session.add(
                    frequencia
                )

                db.session.commit()

                mensagem = (
                    f"Entrada registada para {aluno.nome}"
                )

                telefone = (
                    aluno.telefone
                    .replace("+", "")
                    .replace(" ", "")
                )

                if not telefone.startswith(
                    "351"
                ):
                    telefone = (
                        "351" + telefone
                    )

                texto = (
                    f"{agora.strftime('%H:%M')} - "
                    f"{aluno.nome} - Entrada"
                )

                whatsapp_link = (
                    f"https://wa.me/{telefone}"
                    f"?text={quote(texto)}"
                )

            else:

                return redirect(
                    url_for(
                        "frequencias.finalizar_frequencia",
                        frequencia_id=aberta.id
                    )
                )

    historico = Frequencia.query.order_by(
        Frequencia.id.desc()
    ).all()

    preparar_historico_frequencias(
        historico
    )

    em_estudo = len([
        f for f in historico
        if not f.hora_saida
    ])

    concluidos = len([
        f for f in historico
        if f.hora_saida
    ])

    return render_template(
        "frequencias.html",
        historico=historico,
        mensagem=mensagem,
        whatsapp_link=whatsapp_link,
        em_estudo=em_estudo,
        concluidos=concluidos,
        total=len(historico)
    )


@frequencias_bp.route(
    "/frequencias/finalizar/<int:frequencia_id>",
    methods=["GET", "POST"]
)
def finalizar_frequencia(
    frequencia_id
):

    frequencia = (
        Frequencia.query.get_or_404(
            frequencia_id
        )
    )

    aluno = frequencia.aluno

    if request.method == "POST":

        disciplinas = request.form.getlist(
            "disciplinas"
        )

        outros_descricao = request.form.get(
            "outros_descricao",
            ""
        ).strip()

        if outros_descricao:

            if "Outros" in disciplinas:

                disciplinas.remove(
                    "Outros"
                )

            disciplinas.append(
                f"Outros: {outros_descricao}"
            )

        observacoes = request.form.get(
            "observacoes",
            ""
        )

        hora_saida = datetime.now()

        entrada = datetime.strptime(
            frequencia.hora_entrada,
            "%H:%M"
        )

        saida = datetime.strptime(
            hora_saida.strftime("%H:%M"),
            "%H:%M"
        )

        duracao = (
            saida - entrada
        ).total_seconds() / 3600

        frequencia.hora_saida = (
            hora_saida.strftime("%H:%M")
        )

        frequencia.duracao_horas = round(
            duracao,
            2
        )

        frequencia.disciplinas = (
            ", ".join(disciplinas)
        )

        frequencia.observacoes = (
            observacoes
        )

        aluno.horas_restantes = max(
            0,
            aluno.horas_restantes - duracao
        )

        db.session.commit()

        telefone = (
            aluno.telefone
            .replace("+", "")
            .replace(" ", "")
        )

        if not telefone.startswith(
            "351"
        ):
            telefone = (
                "351" + telefone
            )

        texto = (
            f"{hora_saida.strftime('%H:%M')} - "
            f"{aluno.nome} - Estudo terminado"
        )

        whatsapp_link = (
            f"https://wa.me/{telefone}"
            f"?text={quote(texto)}"
        )

        return render_template(
            "saida_registada.html",
            aluno=aluno,
            whatsapp_link=whatsapp_link
        )

    return render_template(
        "finalizar_frequencia.html",
        frequencia=frequencia,
        aluno=aluno
    )