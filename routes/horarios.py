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
    Mesma lógica usada em routes/calendario.py para alimentar
    os datalists de sugestão (Escola / Turma), a partir dos
    alunos já existentes.
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
    Agrupa os horários por Centro Escolar -> Turma -> lista
    ordenada por dia da semana e hora de início.
    """

    agrupados = {}

    for horario in lista_horarios:

        escola = horario.centro_escolar or "Sem Centro Escolar"
        turma = horario.turma or "Sem Turma"

        agrupados.setdefault(
            escola, {}
        ).setdefault(
            turma, []
        ).append(horario)

    for escola in agrupados:

        for turma in agrupados[escola]:

            agrupados[escola][turma].sort(
                key=lambda h: (
                    h.ordem_dia(),
                    h.hora_inicio
                )
            )

    return agrupados


# ------------------------------------------------------------------
# ROTAS
# ------------------------------------------------------------------

@horarios_bp.route("/horarios")
def horarios():

    lista_horarios = HorarioTurma.query.all()

    agrupados = agrupar_horarios(lista_horarios)

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

        horario = HorarioTurma(
            centro_escolar=request.form["centro_escolar"].strip(),
            turma=request.form["turma"].strip(),
            dia_semana=request.form["dia_semana"],
            hora_inicio=request.form["hora_inicio"],
            hora_fim=request.form["hora_fim"],
            disciplina=request.form["disciplina"].strip()
        )

        db.session.add(horario)
        db.session.commit()

        return redirect(
            url_for("horarios.horarios")
        )

    return render_template(
        "horario_form.html",
        horario=None,
        escolas=escolas,
        turmas=turmas,
        dias_semana=DIAS_SEMANA
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

    escolas, turmas = obter_escolas_e_turmas()

    if request.method == "POST":

        horario.centro_escolar = request.form["centro_escolar"].strip()
        horario.turma = request.form["turma"].strip()
        horario.dia_semana = request.form["dia_semana"]
        horario.hora_inicio = request.form["hora_inicio"]
        horario.hora_fim = request.form["hora_fim"]
        horario.disciplina = request.form["disciplina"].strip()

        db.session.commit()

        return redirect(
            url_for("horarios.horarios")
        )

    return render_template(
        "horario_form.html",
        horario=horario,
        escolas=escolas,
        turmas=turmas,
        dias_semana=DIAS_SEMANA
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

    db.session.delete(horario)
    db.session.commit()

    return redirect(
        url_for("horarios.horarios")
    )
