from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

from models import db
from models.aluno import Aluno
from models.frequencia import Frequencia
from models.evento import Evento


frequencias_bp = Blueprint("frequencias", __name__)

FUSO_PORTUGAL = ZoneInfo("Europe/Lisbon")

PRESENCA_MARKER = "PRESENÇA"
ANULADO_MARKER = "[ANULADO]"

TIPO_PRESENCA = "PRESENCA"
TIPO_CHEGADA = "CHEGADA"
TIPO_ESTUDO = "ESTUDO"

SAIDA_ESTUDO_CONCLUIDO = "ESTUDO_CONCLUIDO"
SAIDA_SOLICITADA = "SAIDA_SOLICITADA"

HORA_RESET_DIARIO = time(19, 1)


def agora_portugal():
    return datetime.now(FUSO_PORTUGAL).replace(tzinfo=None)


def periodo_diario_atual(agora=None):
    agora = agora or agora_portugal()

    if agora.time() >= HORA_RESET_DIARIO:
        return None

    return agora.strftime("%d/%m/%Y")


def eh_registo_do_dia_atual(frequencia, agora=None):
    data_atual = periodo_diario_atual(agora)
    return data_atual is not None and frequencia.data == data_atual


def horas_para_hhmm(horas):
    total_minutos = int(round((horas or 0) * 60))
    horas_int = total_minutos // 60
    minutos = total_minutos % 60
    return f"{horas_int:02d}:{minutos:02d}"


def eh_presenca(frequencia):
    return (
        frequencia.tipo_registo == TIPO_PRESENCA
        or frequencia.disciplinas == PRESENCA_MARKER
    )


def esta_anulada(frequencia):
    return bool(
        frequencia.observacoes
        and frequencia.observacoes.startswith(ANULADO_MARKER)
    )


def eh_chegada_em_espera(frequencia):
    """
    Verdadeiro quando o aluno chegou, mas ainda não iniciou o estudo.

    Registos antigos sem tipo_registo não são considerados chegadas,
    preservando o comportamento histórico.
    """
    return (
        frequencia.tipo_registo == TIPO_CHEGADA
        and frequencia.hora_saida is None
        and frequencia.hora_inicio_estudo is None
        and not esta_anulada(frequencia)
    )


def eh_sessao_estudo_aberta(frequencia):
    """
    Apenas uma sessão em que o estudo já começou pode aparecer
    como 'Em estudo'.

    Uma chegada em espera NÃO é uma sessão de estudo aberta.
    """
    if frequencia.hora_saida is not None:
        return False

    if eh_presenca(frequencia) or esta_anulada(frequencia):
        return False

    if eh_chegada_em_espera(frequencia):
        return False

    if frequencia.tipo_registo == TIPO_ESTUDO:
        return True

    # Compatibilidade com registos antigos:
    # antes da nova estrutura, qualquer registo não-presença
    # aberto representava uma sessão de estudo.
    if frequencia.tipo_registo is None:
        return True

    return False


def obter_inicio_estudo(frequencia):
    """
    Devolve a hora real de início do estudo.

    Nos novos registos usa hora_inicio_estudo.
    Nos registos antigos usa hora_entrada.
    """
    return frequencia.hora_inicio_estudo or frequencia.hora_entrada


def obter_aberta_do_aluno(aluno_id):
    encerrar_sessoes_abertas_apos_reset()

    data_atual = agora_portugal().strftime("%d/%m/%Y")

    frequencias = Frequencia.query.filter_by(
        aluno_id=aluno_id,
        data=data_atual,
        hora_saida=None
    ).order_by(Frequencia.id.desc()).all()

    for frequencia in frequencias:
        if eh_sessao_estudo_aberta(frequencia):
            return frequencia

    return None


def obter_chegada_em_espera_do_aluno(aluno_id):
    encerrar_sessoes_abertas_apos_reset()

    data_atual = agora_portugal().strftime("%d/%m/%Y")

    frequencias = Frequencia.query.filter_by(
        aluno_id=aluno_id,
        data=data_atual,
        hora_saida=None
    ).order_by(Frequencia.id.desc()).all()

    for frequencia in frequencias:
        if eh_chegada_em_espera(frequencia):
            return frequencia

    return None


def encerrar_sessoes_abertas_apos_reset(agora=None):
    """
    Fecha apenas sessões em que o estudo já começou.

    Chegadas que ficaram em espera não recebem horas de estudo.
    """
    agora = agora or agora_portugal()
    deve_encerrar = agora.time() >= HORA_RESET_DIARIO
    data_atual = agora.strftime("%d/%m/%Y")

    abertas = [
        f
        for f in Frequencia.query.filter_by(hora_saida=None).all()
        if eh_sessao_estudo_aberta(f)
    ]

    alterou = False

    for frequencia in abertas:
        if not deve_encerrar and frequencia.data == data_atual:
            continue

        inicio_texto = obter_inicio_estudo(frequencia)

        try:
            entrada = datetime.strptime(
                inicio_texto,
                "%H:%M"
            )
            saida_hora = "19:00"
            saida = datetime.strptime(
                saida_hora,
                "%H:%M"
            )
            duracao = (saida - entrada).total_seconds() / 3600
        except (TypeError, ValueError):
            continue

        if duracao < 0:
            duracao = 0

        frequencia.hora_saida = saida_hora
        frequencia.duracao_horas = round(duracao, 2)
        frequencia.tipo_saida = SAIDA_ESTUDO_CONCLUIDO

        aluno = frequencia.aluno
        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - duracao
        )

        alterou = True

    if alterou:
        db.session.commit()


def obter_resumo_diario():
    agora = agora_portugal()
    data_atual = periodo_diario_atual(agora)

    encerrar_sessoes_abertas_apos_reset(agora)

    if data_atual is None:
        return {
            "em_estudo": 0,
            "em_espera": 0,
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
            1
            for f in registos_validos
            if eh_sessao_estudo_aberta(f)
        ),
        "em_espera": sum(
            1
            for f in registos_validos
            if eh_chegada_em_espera(f)
        ),
        "concluidos": sum(
            1
            for f in registos_validos
            if f.hora_saida
        ),
        "total": len(registos_validos)
    }


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
        item.eh_chegada_em_espera = eh_chegada_em_espera(item)
        item.eh_sessao_estudo_aberta = eh_sessao_estudo_aberta(item)


def obter_historico():

    data_atual = agora_portugal().strftime(
        "%d/%m/%Y"
    )

    historico = Frequencia.query.filter_by(
        data=data_atual
    ).order_by(
        Frequencia.id.desc()
    ).all()

    preparar_historico_frequencias(historico)

    return historico



def obter_alunos_infrequentes():

    hoje = agora_portugal().date()

    # Última entrada de cada aluno.
    ultimas_entradas = {}

    frequencias = Frequencia.query.all()

    for frequencia in frequencias:

        if esta_anulada(frequencia):
            continue

        # Apenas registos que representam uma entrada.
        if not frequencia.hora_entrada:
            continue

        if not frequencia.aluno_id:
            continue

        try:
            data_entrada = datetime.strptime(
                frequencia.data,
                "%d/%m/%Y"
            ).date()

        except (TypeError, ValueError):
            continue

        anterior = ultimas_entradas.get(
            frequencia.aluno_id
        )

        if anterior is None or data_entrada > anterior:
            ultimas_entradas[
                frequencia.aluno_id
            ] = data_entrada

    # Carrega uma vez os dias não letivos.
    eventos_nao_letivos = {
        evento.data
        for evento in Evento.query.filter_by(
            nao_letivo=True
        ).all()
    }

    resultado = []

    alunos = Aluno.query.filter_by(
        ativo=True
    ).all()

    for aluno in alunos:

        ultima_entrada = ultimas_entradas.get(
            aluno.id
        )

        # Alunos sem qualquer entrada anterior
        # não entram nesta lista.
        if not ultima_entrada:
            continue

        dias_ausencia = 0

        dia = ultima_entrada + timedelta(days=1)

        while dia <= hoje:

            # Segunda a sexta.
            if dia.weekday() < 5:

                data_bd = dia.strftime(
                    "%Y-%m-%d"
                )

                # Sábados, domingos e dias não letivos
                # não contam.
                if data_bd not in eventos_nao_letivos:
                    dias_ausencia += 1

            dia += timedelta(days=1)

        # Mais de 3 dias de funcionamento.
        if dias_ausencia > 3:

            resultado.append({
                "nome": aluno.nome,
                "dias_ausencia": dias_ausencia
            })

    resultado.sort(
        key=lambda item: item["nome"].casefold()
    )

    return resultado


def dia_permite_frequencia():
    hoje = agora_portugal()

    if hoje.time() >= HORA_RESET_DIARIO:
        return (
            False,
            "O período diário encerrou às 19:01. "
            "Novos registos ficam disponíveis no dia seguinte."
        )

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


def criar_whatsapp_link(aluno, texto):
    telefone = (
        aluno.telefone.replace("+", "").replace(" ", "")
        if aluno.telefone
        else ""
    )

    if not telefone:
        return None

    if not telefone.startswith("351"):
        telefone = "351" + telefone

    return (
        f"https://wa.me/{telefone}"
        f"?text={quote(texto)}"
    )


@frequencias_bp.route(
    "/frequencias",
    methods=["GET", "POST"]
)
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
                em_espera=resumo["em_espera"],
                concluidos=resumo["concluidos"],
                total=resumo["total"],
                alunos_infrequentes=obter_alunos_infrequentes()
            )

        codigo = request.form.get(
            "codigo",
            ""
        ).strip()

        modo_registo = request.form.get(
            "modo_registo",
            "horas"
        )

        aluno = Aluno.query.filter_by(
            codigo=codigo
        ).first()

        if not aluno:
            mensagem = "Aluno não encontrado."

        elif modo_registo == "presenca":
            agora = agora_portugal()
            data_hoje = agora.strftime("%d/%m/%Y")

            ja_registado = Frequencia.query.filter_by(
                aluno_id=aluno.id,
                data=data_hoje
            ).first()

            if ja_registado:
                mensagem = (
                    f"A presença de {aluno.nome} "
                    f"já está registada em {data_hoje}."
                )
            else:
                frequencia = Frequencia(
                    aluno_id=aluno.id,
                    data=data_hoje,
                    hora_entrada=None,
                    hora_saida=None,
                    duracao_horas=0,
                    disciplinas=PRESENCA_MARKER,
                    observacoes="Presença registada.",
                    tipo_registo=TIPO_PRESENCA
                )

                db.session.add(frequencia)
                db.session.commit()

                mensagem = (
                    f"Presença registada para {aluno.nome} "
                    f"em {data_hoje}."
                )

        elif modo_registo == "chegada":
            chegada_existente = obter_chegada_em_espera_do_aluno(
                aluno.id
            )

            estudo_aberto = obter_aberta_do_aluno(
                aluno.id
            )

            if chegada_existente:
                mensagem = (
                    f"{aluno.nome} já está em espera."
                )

            elif estudo_aberto:
                mensagem = (
                    f"{aluno.nome} já está em estudo. "
                    "Utilize o registo de saída."
                )

            else:
                agora = agora_portugal()

                frequencia = Frequencia(
                    aluno_id=aluno.id,
                    data=agora.strftime("%d/%m/%Y"),
                    hora_entrada=agora.strftime("%H:%M"),
                    hora_saida=None,
                    duracao_horas=0,
                    disciplinas=None,
                    observacoes="Chegada registada.",
                    tipo_registo=TIPO_CHEGADA,
                    hora_inicio_estudo=None,
                    tipo_saida=None
                )

                db.session.add(frequencia)
                db.session.commit()

                mensagem = (
                    f"Chegada registada para {aluno.nome}."
                )

                texto = (
                    f"{agora.strftime('%H:%M')} - "
                    f"{aluno.nome} - Entrada"
                )

                whatsapp_link = criar_whatsapp_link(
                    aluno,
                    texto
                )

        else:
            chegada_em_espera = obter_chegada_em_espera_do_aluno(
                aluno.id
            )

            if chegada_em_espera:
                mensagem = (
                    f"{aluno.nome} está em espera. "
                    "Utilize o botão 'Iniciar estudo' para começar "
                    "a contar as horas."
                )
            else:
                aberta = obter_aberta_do_aluno(
                    aluno.id
                )

                if not aberta:
                    agora = agora_portugal()

                    frequencia = Frequencia(
                        aluno_id=aluno.id,
                        data=agora.strftime("%d/%m/%Y"),
                        hora_entrada=agora.strftime("%H:%M"),
                        hora_saida=None,
                        duracao_horas=0,
                        disciplinas=None,
                        observacoes="Entrada registada.",
                        tipo_registo=TIPO_ESTUDO,
                        hora_inicio_estudo=agora.strftime("%H:%M"),
                        tipo_saida=None
                    )

                    db.session.add(frequencia)
                    db.session.commit()

                    mensagem = (
                        f"Entrada registada para {aluno.nome}"
                    )

                    texto = (
                        f"{agora.strftime('%H:%M')} - "
                        f"{aluno.nome} - Entrada"
                    )

                    whatsapp_link = criar_whatsapp_link(
                        aluno,
                        texto
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
        em_espera=resumo["em_espera"],
        concluidos=resumo["concluidos"],
        total=resumo["total"],
        alunos_infrequentes=obter_alunos_infrequentes()
    )


@frequencias_bp.route(
    "/frequencias/iniciar-estudo/<int:frequencia_id>",
    methods=["POST"]
)
def iniciar_estudo(frequencia_id):
    permitido, motivo = dia_permite_frequencia()

    if not permitido:
        flash(motivo)
        return redirect(url_for("frequencias.frequencias"))

    frequencia = Frequencia.query.get_or_404(
        frequencia_id
    )

    if not eh_chegada_em_espera(frequencia):
        flash(
            "Este registo já não está em espera."
        )
        return redirect(url_for("frequencias.frequencias"))

    aluno = frequencia.aluno

    estudo_existente = obter_aberta_do_aluno(
        aluno.id
    )

    if estudo_existente:
        flash(
            f"{aluno.nome} já possui um estudo em curso."
        )
        return redirect(url_for("frequencias.frequencias"))

    agora = agora_portugal()

    frequencia.tipo_registo = TIPO_ESTUDO
    frequencia.hora_inicio_estudo = agora.strftime("%H:%M")
    frequencia.observacoes = "Estudo iniciado após chegada."

    db.session.commit()

    flash(
        f"Estudo iniciado para {aluno.nome} às "
        f"{agora.strftime('%H:%M')}."
    )

    return redirect(
        url_for("frequencias.frequencias")
    )


@frequencias_bp.route(
    "/frequencias/finalizar/<int:frequencia_id>",
    methods=["GET", "POST"]
)
def finalizar_frequencia(frequencia_id):
    encerrar_sessoes_abertas_apos_reset()

    frequencia = Frequencia.query.get_or_404(
        frequencia_id
    )

    aluno = frequencia.aluno

    if eh_presenca(frequencia):
        flash(
            "Uma presença não é uma sessão de estudo."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    if esta_anulada(frequencia):
        flash("Este registo está anulado.")
        return redirect(
            url_for("frequencias.frequencias")
        )

    if frequencia.hora_saida:
        flash("Esta sessão já foi encerrada.")
        return redirect(
            url_for("frequencias.frequencias")
        )

    if eh_chegada_em_espera(frequencia):
        flash(
            "O aluno ainda está em espera. "
            "Inicie primeiro o estudo."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    tipo_saida = request.form.get(
        "tipo_saida",
        SAIDA_ESTUDO_CONCLUIDO
    )

    etapa = request.form.get(
        "etapa",
        ""
    )

    # Primeira etapa:
    # apenas apresenta a página para escolher disciplinas.
    # Nenhum dado é gravado nesta fase.
    if request.method == "POST" and etapa != "finalizacao":
        return render_template(
            "finalizar_frequencia.html",
            frequencia=frequencia,
            aluno=aluno,
            tipo_saida=tipo_saida
        )

    # GET também apresenta a página de finalização.
    if request.method == "GET":
        return render_template(
            "finalizar_frequencia.html",
            frequencia=frequencia,
            aluno=aluno,
            tipo_saida=tipo_saida
        )

    # Segunda etapa:
    # recolhe as disciplinas e conclui efetivamente o registo.
    disciplinas = request.form.getlist(
        "disciplinas"
    )

    outros_descricao = request.form.get(
        "outros_descricao",
        ""
    ).strip()

    if outros_descricao:
        if "Outros" in disciplinas:
            disciplinas.remove("Outros")

        disciplinas.append(
            f"Outros: {outros_descricao}"
        )

    observacoes = request.form.get(
        "observacoes",
        ""
    ).strip()

    agora = agora_portugal()
    hora_saida_texto = agora.strftime("%H:%M")

    # Saída solicitada:
    # duração fixa de 2 horas e sem WhatsApp.
    if tipo_saida == SAIDA_SOLICITADA:
        frequencia.hora_saida = hora_saida_texto
        frequencia.duracao_horas = 2.0
        frequencia.disciplinas = ", ".join(
            disciplinas
        )
        frequencia.tipo_registo = TIPO_ESTUDO
        frequencia.tipo_saida = SAIDA_SOLICITADA

        if observacoes:
            frequencia.observacoes = (
                "Saída solicitada. "
                + observacoes
            )
        else:
            frequencia.observacoes = (
                "Saída solicitada."
            )

        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - 2.0
        )

        db.session.commit()

        return render_template(
            "saida_registada.html",
            aluno=aluno,
            whatsapp_link=None,
            saida_solicitada=True,
            duracao=2.0
        )

    # Estudo concluído:
    # calcula a duração real desde o início do estudo.
    inicio_texto = obter_inicio_estudo(
        frequencia
    )

    try:
        entrada = datetime.strptime(
            inicio_texto,
            "%H:%M"
        )
    except (TypeError, ValueError):
        flash(
            "Não foi possível calcular a duração "
            "desta sessão."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    saida = datetime.strptime(
        hora_saida_texto,
        "%H:%M"
    )

    duracao = (
        saida - entrada
    ).total_seconds() / 3600

    if duracao < 0:
        flash(
            "A hora de saída não pode ser anterior "
            "à hora de início do estudo."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    frequencia.hora_saida = hora_saida_texto
    frequencia.duracao_horas = round(
        duracao,
        2
    )
    frequencia.disciplinas = ", ".join(
        disciplinas
    )
    frequencia.observacoes = observacoes
    frequencia.tipo_registo = TIPO_ESTUDO
    frequencia.tipo_saida = SAIDA_ESTUDO_CONCLUIDO

    aluno.horas_restantes = max(
        0,
        (aluno.horas_restantes or 0) - duracao
    )

    db.session.commit()

    texto_disciplinas = (
        ", ".join(disciplinas)
        if disciplinas
        else "Disciplina não indicada"
    )

    texto = (
        f"{hora_saida_texto} - "
        f"{aluno.nome} - Estudo concluído - "
        f"{texto_disciplinas}"
    )

    whatsapp_link = criar_whatsapp_link(
        aluno,
        texto
    )

    return render_template(
        "saida_registada.html",
        aluno=aluno,
        whatsapp_link=whatsapp_link,
        saida_solicitada=False,
        duracao=duracao
    )
@frequencias_bp.route(
    "/frequencias/anular/<int:frequencia_id>",
    methods=["POST"]
)
def anular_frequencia(frequencia_id):
    if not utilizador_pode_alterar_registos():
        return render_template(
            "acesso_negado.html"
        )

    frequencia = Frequencia.query.get_or_404(
        frequencia_id
    )

    if eh_presenca(frequencia):
        flash(
            "Uma presença não precisa de ser anulada "
            "como horas de estudo."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    if esta_anulada(frequencia):
        flash("Este registo já está anulado.")
        return redirect(
            url_for("frequencias.frequencias")
        )

    duracao_original = round(
        frequencia.duracao_horas or 0,
        2
    )

    if frequencia.hora_saida and duracao_original > 0:
        aluno = frequencia.aluno

        aluno.horas_restantes = min(
            aluno.pacote_horas or float("inf"),
            (aluno.horas_restantes or 0) + duracao_original
        )

    observacao_original = (
        frequencia.observacoes or ""
    ).strip()

    detalhe = (
        f"Duração original: "
        f"{horas_para_hhmm(duracao_original)}."
    )

    if observacao_original:
        frequencia.observacoes = (
            f"{ANULADO_MARKER} "
            f"{detalhe} "
            f"{observacao_original}"
        )
    else:
        frequencia.observacoes = (
            f"{ANULADO_MARKER} {detalhe}"
        )

    frequencia.duracao_horas = 0

    db.session.commit()

    flash(
        f"Registo de {frequencia.aluno.nome} anulado. "
        "As horas foram devolvidas ao pacote."
    )

    return redirect(
        url_for("frequencias.frequencias")
    )


@frequencias_bp.route(
    "/frequencias/corrigir/<int:frequencia_id>",
    methods=["POST"]
)
def corrigir_frequencia(frequencia_id):
    if not utilizador_pode_alterar_registos():
        return render_template(
            "acesso_negado.html"
        )

    frequencia = Frequencia.query.get_or_404(
        frequencia_id
    )

    if eh_presenca(frequencia) or esta_anulada(frequencia):
        flash(
            "Este registo não pode ser corrigido "
            "como sessão de estudo."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    if frequencia.tipo_saida == SAIDA_SOLICITADA:
        flash(
            "Uma saída solicitada tem sempre 2 horas "
            "contabilizadas e não pode ser corrigida."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    if not frequencia.hora_entrada or not frequencia.hora_saida:
        flash(
            "Só é possível corrigir uma sessão de estudo "
            "já encerrada."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    nova_entrada = request.form.get(
        "hora_entrada",
        ""
    ).strip()

    nova_saida = request.form.get(
        "hora_saida",
        ""
    ).strip()

    try:
        entrada = datetime.strptime(
            nova_entrada,
            "%H:%M"
        )

        saida = datetime.strptime(
            nova_saida,
            "%H:%M"
        )
    except ValueError:
        flash(
            "Indique horas válidas no formato HH:MM."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    if saida <= entrada:
        flash(
            "A hora de saída deve ser posterior "
            "à hora de entrada."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    nova_duracao = (
        saida - entrada
    ).total_seconds() / 3600

    nova_duracao = round(
        nova_duracao,
        2
    )

    duracao_anterior = round(
        frequencia.duracao_horas or 0,
        2
    )

    diferenca = (
        duracao_anterior - nova_duracao
    )

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

    if frequencia.hora_inicio_estudo:
        frequencia.hora_inicio_estudo = nova_entrada

    frequencia.hora_saida = nova_saida
    frequencia.duracao_horas = nova_duracao

    db.session.commit()

    flash(
        f"Registo de {aluno.nome} corrigido para "
        f"{horas_para_hhmm(nova_duracao)} de estudo."
    )

    return redirect(
        url_for("frequencias.frequencias")
    )


@frequencias_bp.route(
    "/frequencias/eliminar/<int:frequencia_id>",
    methods=["POST"]
)
def eliminar_frequencia(frequencia_id):
    if session.get("perfil") != "administrador_geral":
        return render_template(
            "acesso_negado.html"
        )

    frequencia = Frequencia.query.get_or_404(
        frequencia_id
    )

    nome_aluno = frequencia.aluno.nome
    aluno = frequencia.aluno

    if eh_presenca(frequencia):
        db.session.delete(frequencia)
        db.session.commit()

        flash(
            f"Presença de {nome_aluno} eliminada."
        )

        return redirect(
            url_for("frequencias.frequencias")
        )

    if esta_anulada(frequencia):
        db.session.delete(frequencia)
        db.session.commit()

        flash(
            f"Registo anulado de {nome_aluno} eliminado."
        )

        return redirect(
            url_for("frequencias.frequencias")
        )

    # Qualquer registo que tenha horas contabilizadas
    # devolve essas horas ao aluno antes de ser eliminado.
    duracao_contabilizada = round(
        frequencia.duracao_horas or 0,
        2
    )

    if duracao_contabilizada > 0:
        aluno.horas_restantes = (
            aluno.horas_restantes or 0
        ) + duracao_contabilizada

    db.session.delete(frequencia)
    db.session.commit()

    if duracao_contabilizada > 0:
        flash(
            f"Registo de {nome_aluno} eliminado. "
            f"{horas_para_hhmm(duracao_contabilizada)} "
            "foram devolvidas às horas restantes."
        )
    else:
        flash(
            f"Registo de {nome_aluno} eliminado."
        )

    return redirect(
        url_for("frequencias.frequencias")
    )


@frequencias_bp.route(
    "/frequencias/encerrar-todos",
    methods=["POST"]
)
def encerrar_todos_frequencias():
    if session.get("perfil") not in [
        "administrador",
        "administrador_geral"
    ]:
        return render_template(
            "acesso_negado.html"
        )

    encerrar_sessoes_abertas_apos_reset()

    abertas = [
        f
        for f in Frequencia.query.filter_by(
            hora_saida=None
        ).all()
        if eh_sessao_estudo_aberta(f)
    ]

    if not abertas:
        flash(
            "Nenhuma frequência em estudo encontrada."
        )
        return redirect(
            url_for("frequencias.frequencias")
        )

    total_encerradas = 0

    for frequencia in abertas:
        aluno = frequencia.aluno
        hora_saida = agora_portugal()

        inicio_texto = obter_inicio_estudo(
            frequencia
        )

        try:
            entrada = datetime.strptime(
                inicio_texto,
                "%H:%M"
            )
        except (TypeError, ValueError):
            continue

        saida = datetime.strptime(
            hora_saida.strftime("%H:%M"),
            "%H:%M"
        )

        duracao = (
            saida - entrada
        ).total_seconds() / 3600

        if duracao < 0:
            continue

        frequencia.hora_saida = (
            hora_saida.strftime("%H:%M")
        )

        frequencia.duracao_horas = round(
            duracao,
            2
        )

        frequencia.tipo_saida = (
            SAIDA_ESTUDO_CONCLUIDO
        )

        aluno.horas_restantes = max(
            0,
            (aluno.horas_restantes or 0) - duracao
        )

        total_encerradas += 1

    db.session.commit()

    flash(
        f"Foram encerradas {total_encerradas} "
        "frequências em estudo."
    )

    return redirect(
        url_for("frequencias.frequencias")
    )

