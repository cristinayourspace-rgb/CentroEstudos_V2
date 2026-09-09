from collections import OrderedDict

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
from models.horario_turma import (
    HorarioTurma,
    DIAS_SEMANA
)


horarios_bp = Blueprint(
    "horarios",
    __name__
)


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def obter_escolas_e_turmas():
    """
    Alimenta os datalists de sugestão (Escola / Turma), a partir
    dos alunos já existentes.
    """

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

    return escolas, turmas


def agrupar_horarios(lista_horarios):
    """
    Agrupa os registos por Centro Escolar -> Turma -> Dia da Semana.

    A tabela da página apresenta uma linha por dia e coloca todas as
    disciplinas desse dia numa única lista.

    A estrutura da base de dados mantém-se inalterada:
    existe um registo HorarioTurma por disciplina.
    """

    agrupados = OrderedDict()

    for horario in lista_horarios:

        escola = horario.centro_escolar or "Sem Centro Escolar"
        turma = horario.turma or "Sem Turma"
        dia = horario.dia_semana

        agrupados.setdefault(
            escola, OrderedDict()
        ).setdefault(
            turma, OrderedDict()
        ).setdefault(
            dia,
            []
        ).append(horario)

    for escola in agrupados:

        for turma in agrupados[escola]:

            dias = agrupados[escola][turma]

            dias_ordenados = OrderedDict()

            for dia in DIAS_SEMANA:

                if dia in dias:
                    itens = dias[dia]

                    itens.sort(
                        key=lambda h: (
                            h.hora_inicio or "",
                            h.disciplina.lower() if h.disciplina else ""
                        )
                    )

                    dias_ordenados[dia] = itens

            # Preserva eventuais dias antigos/inválidos que possam
            # existir na base, sem os perder.
            for dia, itens in dias.items():

                if dia not in dias_ordenados:

                    itens.sort(
                        key=lambda h: (
                            h.hora_inicio or "",
                            h.disciplina.lower() if h.disciplina else ""
                        )
                    )

                    dias_ordenados[dia] = itens

            agrupados[escola][turma] = dias_ordenados

    return agrupados


def preparar_dados_para_formulario():
    """
    Reconstroi o estado dos dias a partir do POST, para que os dados
    preenchidos permaneçam visíveis quando existir um erro de validação.
    """

    dados = {}

    for indice, nome_dia in enumerate(DIAS_SEMANA):

        if request.form.get(f"dia_ativo_{indice}") != "1":
            continue

        dados[nome_dia] = {
            "hora_inicio": request.form.get(
                f"hora_inicio_{indice}",
                ""
            ).strip(),

            "hora_fim": request.form.get(
                f"hora_fim_{indice}",
                ""
            ).strip(),

            "disciplinas": [
                disciplina.strip()
                for disciplina in request.form.getlist(
                    f"disciplinas_{indice}[]"
                )
            ]
        }

    return dados


def recolher_dados_formulario():
    """
    Lê e valida o formulário semanal.

    Para cada dia ativado podem existir várias disciplinas, mas apenas
    um horário de entrada e um horário de saída para o dia.
    """

    dias = []
    erros = []

    for indice, nome_dia in enumerate(DIAS_SEMANA):

        ativo = request.form.get(
            f"dia_ativo_{indice}"
        ) == "1"

        if not ativo:
            continue

        hora_inicio = request.form.get(
            f"hora_inicio_{indice}",
            ""
        ).strip()

        hora_fim = request.form.get(
            f"hora_fim_{indice}",
            ""
        ).strip()

        disciplinas = [
            disciplina.strip()
            for disciplina in request.form.getlist(
                f"disciplinas_{indice}[]"
            )
            if disciplina.strip()
        ]

        if not hora_inicio:
            erros.append(
                f"Defina a hora de entrada de {nome_dia}."
            )

        if not hora_fim:
            erros.append(
                f"Defina a hora de saída de {nome_dia}."
            )

        if (
            hora_inicio
            and hora_fim
            and hora_fim <= hora_inicio
        ):
            erros.append(
                f"A hora de saída de {nome_dia} deve ser posterior à hora de entrada."
            )

        if not disciplinas:
            erros.append(
                f"Adicione pelo menos uma disciplina em {nome_dia}."
            )

        if (
            hora_inicio
            and hora_fim
            and disciplinas
            and hora_fim > hora_inicio
        ):
            dias.append(
                {
                    "dia_semana": nome_dia,
                    "hora_inicio": hora_inicio,
                    "hora_fim": hora_fim,
                    "disciplinas": disciplinas,
                }
            )

    return dias, erros


def guardar_horario_semanal(
    centro_escolar,
    turma,
    dados_dias
):
    """
    Mantém uma única configuração semanal por Centro Escolar + Turma.

    A tabela atual é reaproveitada: cada disciplina continua a ser um
    registo separado, mas os horários de entrada/saída são iguais para
    todas as disciplinas do mesmo dia.

    Não é necessária alteração da estrutura da base de dados.
    """

    existentes = HorarioTurma.query.filter_by(
        centro_escolar=centro_escolar,
        turma=turma
    ).all()

    for horario in existentes:
        db.session.delete(horario)

    for dia in dados_dias:

        for disciplina in dia["disciplinas"]:

            horario = HorarioTurma(
                centro_escolar=centro_escolar,
                turma=turma,
                dia_semana=dia["dia_semana"],
                hora_inicio=dia["hora_inicio"],
                hora_fim=dia["hora_fim"],
                disciplina=disciplina
            )

            db.session.add(horario)

    db.session.commit()


def obter_horario_turma(
    centro_escolar,
    turma
):
    """
    Devolve o horário de uma turma já agrupado por dia.
    """

    lista = HorarioTurma.query.filter_by(
        centro_escolar=centro_escolar,
        turma=turma
    ).all()

    agrupado = OrderedDict()

    for dia in DIAS_SEMANA:

        itens = [
            horario
            for horario in lista
            if horario.dia_semana == dia
        ]

        if itens:

            itens.sort(
                key=lambda h: (
                    h.disciplina.lower()
                    if h.disciplina else ""
                )
            )

            agrupado[dia] = itens

    return agrupado


# ------------------------------------------------------------------
# ROTAS
# ------------------------------------------------------------------

@horarios_bp.route("/horarios")
def horarios():

    lista_horarios = HorarioTurma.query.all()

    agrupados = agrupar_horarios(
        lista_horarios
    )

    return render_template(
        "horarios.html",
        agrupados=agrupados
    )


@horarios_bp.route(
    "/horarios/novo",
    methods=["GET", "POST"]
)
def novo_horario():

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    escolas, turmas = obter_escolas_e_turmas()

    if request.method == "POST":

        centro_escolar = request.form.get(
            "centro_escolar",
            ""
        ).strip()

        turma = request.form.get(
            "turma",
            ""
        ).strip()

        dados_dias, erros = recolher_dados_formulario()

        if not centro_escolar:
            erros.insert(0, "Preencha o Centro Escolar.")

        if not turma:
            erros.insert(0, "Preencha a Turma.")

        if not dados_dias and not erros:
            erros.append(
                "Ative pelo menos um dia e preencha-o completamente."
            )

        if erros:

            return render_template(
                "horario_form.html",
                horario=None,
                escolas=escolas,
                turmas=turmas,
                dias_semana=DIAS_SEMANA,
                dados_existentes=preparar_dados_para_formulario(),
                erro=" ".join(erros)
            )

        guardar_horario_semanal(
            centro_escolar,
            turma,
            dados_dias
        )

        return redirect(
            url_for("horarios.horarios")
        )

    return render_template(
        "horario_form.html",
        horario=None,
        escolas=escolas,
        turmas=turmas,
        dias_semana=DIAS_SEMANA,
        erro=None
    )


@horarios_bp.route(
    "/horarios/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_horario(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    horario = HorarioTurma.query.get_or_404(id)

    horarios_turma = HorarioTurma.query.filter_by(
        centro_escolar=horario.centro_escolar,
        turma=horario.turma
    ).all()

    escolas, turmas = obter_escolas_e_turmas()

    if request.method == "POST":

        centro_escolar = request.form.get(
            "centro_escolar",
            ""
        ).strip()

        turma = request.form.get(
            "turma",
            ""
        ).strip()

        dados_dias, erros = recolher_dados_formulario()

        if not centro_escolar:
            erros.insert(0, "Preencha o Centro Escolar.")

        if not turma:
            erros.insert(0, "Preencha a Turma.")

        if not dados_dias and not erros:
            erros.append(
                "Ative pelo menos um dia e preencha-o completamente."
            )

        if erros:

            return render_template(
                "horario_form.html",
                horario=horario,
                horarios_turma=horarios_turma,
                escolas=escolas,
                turmas=turmas,
                dias_semana=DIAS_SEMANA,
                dados_existentes=preparar_dados_para_formulario(),
                erro=" ".join(erros)
            )

        guardar_horario_semanal(
            centro_escolar,
            turma,
            dados_dias
        )

        # Se a escola/turma foram alteradas, os registos antigos
        # foram eliminados pelo guardar_horario_semanal do novo grupo
        # apenas quando este grupo já existia. Os registos antigos são
        # tratados abaixo.
        grupo_antigo = HorarioTurma.query.filter_by(
            centro_escolar=horario.centro_escolar,
            turma=horario.turma
        ).all()

        # A referência "horario" pode já ter sido eliminada pelo
        # guardar_horario_semanal. Como o objetivo é editar o grupo
        # inteiro, garantimos que nenhum registo antigo permanece.
        for item in grupo_antigo:

            if (
                item.centro_escolar != centro_escolar
                or item.turma != turma
            ):

                db.session.delete(item)

        db.session.commit()

        return redirect(
            url_for("horarios.horarios")
        )

    # Agrupa os dados existentes para preencher o formulário.
    dados_existentes = {}

    for dia in DIAS_SEMANA:

        itens = [
            h
            for h in horarios_turma
            if h.dia_semana == dia
        ]

        if itens:

            dados_existentes[dia] = {
                "hora_inicio": itens[0].hora_inicio,
                "hora_fim": itens[0].hora_fim,
                "disciplinas": [
                    h.disciplina
                    for h in sorted(
                        itens,
                        key=lambda x: (
                            x.disciplina.lower()
                            if x.disciplina else ""
                        )
                    )
                ]
            }

    return render_template(
        "horario_form.html",
        horario=horario,
        horarios_turma=horarios_turma,
        dados_existentes=dados_existentes,
        escolas=escolas,
        turmas=turmas,
        dias_semana=DIAS_SEMANA,
        erro=None
    )


@horarios_bp.route(
    "/horarios/eliminar/<int:id>"
)
def eliminar_horario(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    horario = HorarioTurma.query.get_or_404(id)

    # Um horário é agora tratado como o horário semanal da turma:
    # eliminar uma linha elimina todo o horário dessa turma.
    horarios_turma = HorarioTurma.query.filter_by(
        centro_escolar=horario.centro_escolar,
        turma=horario.turma
    ).all()

    for item in horarios_turma:
        db.session.delete(item)

    db.session.commit()

    return redirect(
        url_for("horarios.horarios")
    )
