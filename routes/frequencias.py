from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime, time
from zoneinfo import ZoneInfo

FUSO_PORTUGAL = ZoneInfo('Europe/Lisbon')
from urllib.parse import quote

from models import db
from models.aluno import Aluno
from models.frequencia import Frequencia
from models.evento import Evento


frequencias_bp = Blueprint("frequencias", __name__)

PRESENCA_MARKER = "PRESENÇA"
ANULADO_MARKER = "[ANULADO]"

# O "dia de trabalho" termina às 19:01.
# Depois desse horário, as contagens do ecrã devem aparecer a zero.
HORA_RESET_DIARIO = time(19, 1)


def periodo_diario_atual(agora=None):
    """Devolve a data contabilizada no ecrã ou None após as 19:01."""
    agora = agora or datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)

    if agora.time() >= HORA_RESET_DIARIO:
        return None

    return agora.strftime("%d/%m/%Y")


def eh_registo_do_dia_atual(frequencia, agora=None):
    data_atual = periodo_diario_atual(agora)
    return data_atual is not None and frequencia.data == data_atual


def encerrar_sessoes_abertas_apos_reset(agora=None):
    """
    Fecha sessões de estudo que ficaram abertas quando o período diário terminou.
    Não elimina histórico nem remove registos da base de dados.
    A função é executada quando há uma nova utilização da aplicação.
    """
    agora = agora or datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)
    deve_encerrar = agora.time() >= HORA_RESET_DIARIO
    data_atual = agora.strftime("%d/%m/%Y")

    abertas = [
        f for f in Frequencia.query.filter_by(hora_saida=None).all()
        if eh_sessao_estudo_aberta(f)
    ]

    alterou = False

    for frequencia in abertas:
        # Uma sessão aberta de um dia anterior nunca pode continuar
        # para o novo dia. Também fechamos às 19:00 quando o período
        # diário termina, preservando sempre o histórico.
        if not deve_encerrar and frequencia.data == data_atual:
            continue

        try:
            entrada = datetime.strptime(
                frequencia.hora_entrada,
                "%H:%M"
            )
            saida_hora = "19:00"
            saida = datetime.strptime(saida_hora, "%H:%M")
            duracao = (saida - entrada).total_seconds() / 3600
        except (TypeError, ValueError):
            continue

        if duracao < 0:
            duracao = 0

        frequencia.hora_saida = saida_hora
        frequencia.duracao_horas = round(duracao, 2)

        aluno = frequencia.aluno
        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - duracao
        )

        alterou = True

    if alterou:
        db.session.commit()


def obter_resumo_diario():
    """
    Calcula exclusivamente as contagens apresentadas no Dashboard
    e no cartão de resumo da página Frequências.

    Os registos históricos permanecem intactos na base de dados.
    """
    agora = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)
    data_atual = periodo_diario_atual(agora)

    # Primeiro fechamos sessões que não podem continuar abertas.
    # Às 19:01 o ecrã passa imediatamente a mostrar zero.
    encerrar_sessoes_abertas_apos_reset(agora)

    if data_atual is None:
        return {
            "em_estudo": 0,
            "concluidos": 0,
            "total": 0
        }

    registos_do_dia = Frequencia.query.filter_by(
        data=data_atual
    ).all()

    registos_validos = [
        f for f in registos_do_dia
        if not esta_anulada(f)
    ]

    return {
        "em_estudo": sum(
            1 for f in registos_validos
            if eh_sessao_estudo_aberta(f)
        ),
        "concluidos": sum(
            1 for f in registos_validos
            if f.hora_saida
        ),
        "total": len(registos_validos)
    }




def horas_para_hhmm(horas):
    total_minutos = int(round((horas or 0) * 60))
    horas_int = total_minutos // 60
    minutos = total_minutos % 60
    return f"{horas_int:02d}:{minutos:02d}"


def eh_presenca(frequencia):
    return frequencia.disciplinas == PRESENCA_MARKER


def esta_anulada(frequencia):
    return bool(
        frequencia.observacoes
        and frequencia.observacoes.startswith(ANULADO_MARKER)
    )


def eh_sessao_estudo_aberta(frequencia):
    return (
        frequencia.hora_saida is None
        and not eh_presenca(frequencia)
        and not esta_anulada(frequencia)
    )


def preparar_historico_frequencias(historico):
    for item in historico:
        item.horas_restantes_formatadas = horas_para_hhmm(
            item.aluno.horas_restantes
        )
        item.duracao_formatada = horas_para_hhmm(
            item.duracao_horas or 0
        )
        item.eh_presenca = eh_presenca(item)
        item.esta_anulada = esta_anulada(item)


def obter_historico():
    historico = Frequencia.query.order_by(Frequencia.id.desc()).all()
    preparar_historico_frequencias(historico)
    return historico


def obter_aberta_do_aluno(aluno_id):
    encerrar_sessoes_abertas_apos_reset()

    data_atual = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None).strftime("%d/%m/%Y")

    frequencias = Frequencia.query.filter_by(
        aluno_id=aluno_id,
        data=data_atual,
        hora_saida=None
    ).order_by(Frequencia.id.desc()).all()

    for frequencia in frequencias:
        if eh_sessao_estudo_aberta(frequencia):
            return frequencia

    return None


def dia_permite_frequencia():
    hoje = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)

    if hoje.time() >= HORA_RESET_DIARIO:
        return False, "O período diário encerrou às 19:01. Novos registos ficam disponíveis no dia seguinte."

    if hoje.weekday() in [5, 6]:
        return False, "Hoje é fim de semana."

    data_bd = hoje.strftime("%Y-%m-%d")

    evento = Evento.query.filter_by(
        data=data_bd,
        nao_letivo=True
    ).first()

    if evento:
        return False, f"Dia não letivo: {evento.tipo}"

    return True, ""


def utilizador_pode_alterar_registos():
    return session.get("perfil") in [
        "administrador",
        "administrador_geral"
    ]


@frequencias_bp.route("/frequencias", methods=["GET", "POST"])
def frequencias():
    mensagem = ""
    whatsapp_link = None

    if request.method == "POST":
        permitido, motivo = dia_permite_frequencia()

        if not permitido:
            historico = obter_historico()
            resumo = obter_resumo_diario()

            return render_template(
                "frequencias.html",
                historico=historico,
                mensagem=motivo,
                whatsapp_link=None,
                em_estudo=resumo["em_estudo"],
                concluidos=resumo["concluidos"],
                total=resumo["total"]
            )

        codigo = request.form.get("codigo", "").strip()
        modo_registo = request.form.get("modo_registo", "horas")

        aluno = Aluno.query.filter_by(codigo=codigo).first()

        if not aluno:
            mensagem = "Aluno não encontrado."

        elif modo_registo == "presenca":
            agora = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)
            data_hoje = agora.strftime("%d/%m/%Y")

            # Se já existe qualquer registo para o aluno nessa data,
            # a presença já está contabilizada.
            ja_registado = Frequencia.query.filter_by(
                aluno_id=aluno.id,
                data=data_hoje
            ).first()

            if ja_registado:
                mensagem = (
                    f"A presença de {aluno.nome} já está registada em {data_hoje}."
                )
            else:
                frequencia = Frequencia(
                    aluno_id=aluno.id,
                    data=data_hoje,
                    hora_entrada=None,
                    hora_saida=None,
                    duracao_horas=0,
                    disciplinas=PRESENCA_MARKER,
                    observacoes="Presença registada."
                )

                db.session.add(frequencia)
                db.session.commit()

                mensagem = (
                    f"Presença registada para {aluno.nome} em {data_hoje}."
                )

        else:
            aberta = obter_aberta_do_aluno(aluno.id)

            if not aberta:
                agora = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)

                frequencia = Frequencia(
                    aluno_id=aluno.id,
                    data=agora.strftime("%d/%m/%Y"),
                    hora_entrada=agora.strftime("%H:%M")
                )

                db.session.add(frequencia)
                db.session.commit()

                mensagem = f"Entrada registada para {aluno.nome}"

                telefone = (
                    aluno.telefone.replace("+", "").replace(" ", "")
                )

                if not telefone.startswith("351"):
                    telefone = "351" + telefone

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

    historico = obter_historico()
    resumo = obter_resumo_diario()

    return render_template(
        "frequencias.html",
        historico=historico,
        mensagem=mensagem,
        whatsapp_link=whatsapp_link,
        em_estudo=resumo["em_estudo"],
        concluidos=resumo["concluidos"],
        total=resumo["total"]
    )


@frequencias_bp.route(
    "/frequencias/finalizar/<int:frequencia_id>",
    methods=["GET", "POST"]
)
def finalizar_frequencia(frequencia_id):
    encerrar_sessoes_abertas_apos_reset()

    frequencia = Frequencia.query.get_or_404(frequencia_id)
    aluno = frequencia.aluno

    if request.method == "POST":
        disciplinas = request.form.getlist("disciplinas")

        outros_descricao = request.form.get(
            "outros_descricao", ""
        ).strip()

        if outros_descricao:
            if "Outros" in disciplinas:
                disciplinas.remove("Outros")
            disciplinas.append(f"Outros: {outros_descricao}")

        observacoes = request.form.get("observacoes", "")

        hora_saida = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)

        try:
            entrada = datetime.strptime(
                frequencia.hora_entrada,
                "%H:%M"
            )
        except (TypeError, ValueError):
            flash("Não foi possível calcular a duração desta sessão.")
            return redirect(url_for("frequencias.frequencias"))

        saida = datetime.strptime(
            hora_saida.strftime("%H:%M"),
            "%H:%M"
        )

        duracao = (saida - entrada).total_seconds() / 3600

        if duracao < 0:
            flash("A hora de saída não pode ser anterior à hora de entrada.")
            return redirect(url_for("frequencias.frequencias"))

        frequencia.hora_saida = hora_saida.strftime("%H:%M")
        frequencia.duracao_horas = round(duracao, 2)
        frequencia.disciplinas = ", ".join(disciplinas)
        frequencia.observacoes = observacoes

        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - duracao
        )

        db.session.commit()

        telefone = (
            aluno.telefone.replace("+", "").replace(" ", "")
        )

        if not telefone.startswith("351"):
            telefone = "351" + telefone

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


@frequencias_bp.route(
    "/frequencias/anular/<int:frequencia_id>",
    methods=["POST"]
)
def anular_frequencia(frequencia_id):
    if not utilizador_pode_alterar_registos():
        return render_template("acesso_negado.html")

    frequencia = Frequencia.query.get_or_404(frequencia_id)

    if eh_presenca(frequencia):
        flash("Uma presença não precisa de ser anulada como horas de estudo.")
        return redirect(url_for("frequencias.frequencias"))

    if esta_anulada(frequencia):
        flash("Este registo já está anulado.")
        return redirect(url_for("frequencias.frequencias"))

    duracao_original = frequencia.duracao_horas or 0

    if frequencia.hora_saida and duracao_original > 0:
        aluno = frequencia.aluno
        aluno.horas_restantes = min(
            aluno.pacote_horas or float("inf"),
            (aluno.horas_restantes or 0) + duracao_original
        )

    observacao_original = (frequencia.observacoes or "").strip()
    detalhe = f"Duração original: {horas_para_hhmm(duracao_original)}."

    if observacao_original:
        frequencia.observacoes = (
            f"{ANULADO_MARKER} {detalhe} {observacao_original}"
        )
    else:
        frequencia.observacoes = f"{ANULADO_MARKER} {detalhe}"

    frequencia.duracao_horas = 0

    db.session.commit()

    flash(
        f"Registo de {frequencia.aluno.nome} anulado. "
        "As horas foram devolvidas ao pacote."
    )

    return redirect(url_for("frequencias.frequencias"))


@frequencias_bp.route(
    "/frequencias/corrigir/<int:frequencia_id>",
    methods=["POST"]
)
def corrigir_frequencia(frequencia_id):
    if not utilizador_pode_alterar_registos():
        return render_template("acesso_negado.html")

    frequencia = Frequencia.query.get_or_404(frequencia_id)

    if eh_presenca(frequencia) or esta_anulada(frequencia):
        flash("Este registo não pode ser corrigido como sessão de estudo.")
        return redirect(url_for("frequencias.frequencias"))

    if not frequencia.hora_entrada or not frequencia.hora_saida:
        flash("Só é possível corrigir uma sessão de estudo já encerrada.")
        return redirect(url_for("frequencias.frequencias"))

    nova_entrada = request.form.get("hora_entrada", "").strip()
    nova_saida = request.form.get("hora_saida", "").strip()

    try:
        entrada = datetime.strptime(nova_entrada, "%H:%M")
        saida = datetime.strptime(nova_saida, "%H:%M")
    except ValueError:
        flash("Indique horas válidas no formato HH:MM.")
        return redirect(url_for("frequencias.frequencias"))

    if saida <= entrada:
        flash("A hora de saída deve ser posterior à hora de entrada.")
        return redirect(url_for("frequencias.frequencias"))

    nova_duracao = (saida - entrada).total_seconds() / 3600
    nova_duracao = round(nova_duracao, 2)
    duracao_anterior = round(frequencia.duracao_horas or 0, 2)

    diferenca = duracao_anterior - nova_duracao
    aluno = frequencia.aluno

    if diferenca > 0:
        aluno.horas_restantes = min(
            aluno.pacote_horas or float("inf"),
            (aluno.horas_restantes or 0) + diferenca
        )
    elif diferenca < 0:
        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) + diferenca
        )

    frequencia.hora_entrada = nova_entrada
    frequencia.hora_saida = nova_saida
    frequencia.duracao_horas = nova_duracao

    db.session.commit()

    flash(
        f"Registo de {aluno.nome} corrigido para "
        f"{horas_para_hhmm(nova_duracao)} de estudo."
    )

    return redirect(url_for("frequencias.frequencias"))


@frequencias_bp.route(
    "/frequencias/eliminar/<int:frequencia_id>",
    methods=["POST"]
)
def eliminar_frequencia(frequencia_id):
    if session.get("perfil") != "administrador_geral":
        return render_template("acesso_negado.html")

    frequencia = Frequencia.query.get_or_404(frequencia_id)

    # Guardamos o nome antes do delete/commit para evitar
    # DetachedInstanceError ao aceder a frequencia.aluno depois do commit.
    nome_aluno = frequencia.aluno.nome

    if eh_presenca(frequencia):
        db.session.delete(frequencia)
        db.session.commit()
        flash(f"Presença de {nome_aluno} eliminada.")
        return redirect(url_for("frequencias.frequencias"))

    if esta_anulada(frequencia):
        db.session.delete(frequencia)
        db.session.commit()
        flash(f"Registo anulado de {nome_aluno} eliminado.")
        return redirect(url_for("frequencias.frequencias"))

    if frequencia.hora_saida and (frequencia.duracao_horas or 0) > 0:
        flash(
            "Para apagar uma sessão com horas contabilizadas, primeiro anule o registo."
        )
        return redirect(url_for("frequencias.frequencias"))

    db.session.delete(frequencia)
    db.session.commit()
    flash(f"Registo de {nome_aluno} eliminado.")

    return redirect(url_for("frequencias.frequencias"))


@frequencias_bp.route(
    "/frequencias/encerrar-todos",
    methods=["POST"]
)
def encerrar_todos_frequencias():
    if session.get("perfil") not in [
        "administrador",
        "administrador_geral"
    ]:
        return render_template("acesso_negado.html")

    encerrar_sessoes_abertas_apos_reset()

    abertas = [
        f for f in Frequencia.query.filter_by(hora_saida=None).all()
        if eh_sessao_estudo_aberta(f)
    ]

    if not abertas:
        flash("Nenhuma frequência em aberto encontrada.")
        return redirect(url_for("frequencias.frequencias"))

    total_encerradas = 0

    for frequencia in abertas:
        aluno = frequencia.aluno
        hora_saida = datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)

        try:
            entrada = datetime.strptime(
                frequencia.hora_entrada,
                "%H:%M"
            )
        except (TypeError, ValueError):
            continue

        saida = datetime.strptime(
            hora_saida.strftime("%H:%M"),
            "%H:%M"
        )

        duracao = (saida - entrada).total_seconds() / 3600

        if duracao < 0:
            continue

        frequencia.hora_saida = hora_saida.strftime("%H:%M")
        frequencia.duracao_horas = round(duracao, 2)

        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - duracao
        )

        total_encerradas += 1

    db.session.commit()

    flash(
        f"Foram encerradas {total_encerradas} frequências em aberto."
    )

    return redirect(url_for("frequencias.frequencias"))
