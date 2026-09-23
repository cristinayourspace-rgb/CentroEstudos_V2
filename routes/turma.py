import json
import re
import unicodedata
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

from models import db
from models.aluno import Aluno
from models.turma import Turma
from models.horario_turma import HorarioTurma, DIAS_SEMANA
from models.atribuicao_sala import (
    ConfiguracaoSalas,
    PlaneamentoSala,
    AtribuicaoSala,
)


turma_bp = Blueprint("turma", __name__)

DIAS_ATRIBUICAO_SALAS = [
    ("segunda", "Segunda-feira"),
    ("terca", "Terça-feira"),
    ("quarta", "Quarta-feira"),
    ("quinta", "Quinta-feira"),
    ("sexta", "Sexta-feira"),
]


DISCIPLINAS_POR_ANO = {
    "1.º Ano": ["Português", "Matemática", "Estudo do Meio"],
    "2.º Ano": ["Português", "Matemática", "Estudo do Meio"],
    "3.º Ano": ["Português", "Matemática", "Estudo do Meio", "Inglês"],
    "4.º Ano": ["Português", "Matemática", "Estudo do Meio", "Inglês"],
    "5.º Ano": ["Português", "Matemática", "Inglês", "História e Geografia de Portugal", "Ciências Naturais"],
    "6.º Ano": ["Português", "Matemática", "Inglês", "História e Geografia de Portugal", "Ciências Naturais"],
    "7.º Ano": ["Português", "Matemática", "Inglês", "Francês", "Espanhol", "Alemão", "História", "Geografia", "Ciências Naturais", "Físico-Química"],
    "8.º Ano": ["Português", "Matemática", "Inglês", "Francês", "Espanhol", "Alemão", "História", "Geografia", "Ciências Naturais", "Físico-Química"],
    "9.º Ano": ["Português", "Matemática", "Inglês", "Francês", "Espanhol", "Alemão", "História", "Geografia", "Ciências Naturais", "Físico-Química"],
    "10.º Ano": ["Outros"],
    "11.º Ano": ["Outros"],
    "12.º Ano": ["Outros"],
}
ANOS_ESCOLARES = list(DISCIPLINAS_POR_ANO.keys())


def chave_texto(valor):
    texto = (valor or "").strip().lower()
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def chave_turma(valor):
    texto = re.sub(r"\s+", "", chave_texto(valor))
    m = re.match(r"^(\d+)(.*)$", texto)
    if m:
        return (0, int(m.group(1)), re.sub(r"[^a-z0-9]+", "", m.group(2)))
    return (1, 0, texto)


def disciplinas_da_turma(turma):
    try:
        dados = json.loads(turma.disciplinas or "[]")
        if isinstance(dados, list):
            return [str(x).strip() for x in dados if str(x).strip()]
    except (TypeError, ValueError):
        pass
    return []


def preparar_form_turma(turma=None):
    disciplinas = disciplinas_da_turma(turma) if turma else []
    return {
        "turma": turma,
        "anos_escolares": ANOS_ESCOLARES,
        "disciplinas_por_ano": DISCIPLINAS_POR_ANO,
        "disciplinas_selecionadas": disciplinas,
        "escolas": sorted({(a.escola or "").strip() for a in Aluno.query.all() if (a.escola or "").strip()} | {(t.escola or "").strip() for t in Turma.query.all() if (t.escola or "").strip()}, key=chave_texto),
    }


def _ler_disciplinas_formulario():
    selecionadas = []
    for d in request.form.getlist("disciplinas"):
        d = d.strip()
        if d and d not in selecionadas:
            selecionadas.append(d)
    outro = request.form.get("disciplina_outro", "").strip()
    if outro and outro not in selecionadas:
        selecionadas.append(outro)
    return selecionadas


def _ordenar_turmas(turmas):
    return sorted(turmas, key=lambda t: (chave_texto(t.escola), chave_turma(t.nome)))


def _chave_dia_atual():
    indice = datetime.now().weekday()
    if indice > 4:
        return None
    return DIAS_ATRIBUICAO_SALAS[indice][0]


def _montar_sala(planeamento, turmas_por_id):
    atribuicoes = []

    if planeamento:
        linhas = AtribuicaoSala.query.filter_by(
            planeamento_id=planeamento.id
        ).order_by(
            AtribuicaoSala.ordem.asc(),
            AtribuicaoSala.id.asc()
        ).all()

        for linha in linhas:
            nome = ""
            if linha.turma_id and linha.turma_id in turmas_por_id:
                turma = turmas_por_id[linha.turma_id]
                nome = turma.nome
            elif linha.texto_livre:
                nome = linha.texto_livre

            if nome:
                atribuicoes.append({
                    "id": linha.id,
                    "nome": nome,
                    "turma_id": linha.turma_id,
                    "texto_livre": linha.texto_livre or "",
                })

    return {
        "numero": planeamento.sala_numero if planeamento else None,
        "observacoes": planeamento.observacoes if planeamento else "",
        "atribuicoes": atribuicoes,
    }


def obter_atribuicao_salas_dia(dia=None):
    config = ConfiguracaoSalas.query.first()

    if not config or config.numero_salas < 1:
        return None

    if dia is None:
        dia = _chave_dia_atual()

    if dia is None:
        return {
            "dia": "fim_de_semana",
            "titulo": "Fim de semana",
            "salas": [],
            "numero_salas": config.numero_salas,
        }

    titulo = dict(DIAS_ATRIBUICAO_SALAS).get(dia, dia)
    planeamentos = {
        p.sala_numero: p
        for p in PlaneamentoSala.query.filter_by(dia_semana=dia).all()
    }

    turmas_por_id = {
        t.id: t
        for t in Turma.query.all()
    }

    salas = []
    for numero in range(1, config.numero_salas + 1):
        sala = _montar_sala(
            planeamentos.get(numero),
            turmas_por_id,
        )
        sala["numero"] = numero
        salas.append(sala)

    return {
        "dia": dia,
        "titulo": titulo,
        "salas": salas,
        "numero_salas": config.numero_salas,
    }


def obter_atribuicao_salas_semanal():
    config = ConfiguracaoSalas.query.first()

    if not config or config.numero_salas < 1:
        return {
            "configurada": False,
            "numero_salas": 0,
            "dias": [],
        }

    turmas_por_id = {
        t.id: t
        for t in Turma.query.all()
    }

    todos = {}
    for chave, _titulo in DIAS_ATRIBUICAO_SALAS:
        todos[chave] = {
            p.sala_numero: p
            for p in PlaneamentoSala.query.filter_by(
                dia_semana=chave
            ).all()
        }

    dias = []

    for chave, titulo in DIAS_ATRIBUICAO_SALAS:
        salas = []

        for numero in range(1, config.numero_salas + 1):
            planeamento = todos.get(chave, {}).get(numero)
            sala = _montar_sala(planeamento, turmas_por_id)
            sala["numero"] = numero
            salas.append(sala)

        dias.append({
            "chave": chave,
            "titulo": titulo,
            "salas": salas,
        })

    return {
        "configurada": True,
        "numero_salas": config.numero_salas,
        "dias": dias,
    }


@turma_bp.route("/turmas/ver-horarios")
def ver_horarios_consulta():
    """Consulta os horÃ¡rios existentes, sem criar nem alterar dados."""

    horarios = HorarioTurma.query.all()

    # Segunda a sexta, pela ordem correta.
    ordem_dias = {
        "Segunda-feira": 0,
        "TerÃ§a-feira": 1,
        "Quarta-feira": 2,
        "Quinta-feira": 3,
        "Sexta-feira": 4,
    }

    def chave_texto_local(valor):
        return (valor or "").strip().casefold()

    def chave_turma_local(valor):
        import re

        texto_turma = (valor or "").strip().upper()
        partes = re.match(r"^(\d+)\s*([A-Za-zÀ-ÿ].*)?$", texto_turma)

        if partes:
            numero = int(partes.group(1))
            letra = (partes.group(2) or "").strip()
            return (0, numero, letra.casefold())

        return (1, texto_turma.casefold())

    # Agrupa: escola -> turma -> dia -> perÃ­odo.
    escolas = {}

    for horario in horarios:
        escola = (horario.centro_escolar or "Sem escola").strip()
        turma = (horario.turma or "Sem turma").strip()
        dia = (horario.dia_semana or "").strip()
        inicio = (horario.hora_inicio or "").strip()
        fim = (horario.hora_fim or "").strip()
        disciplina = (horario.disciplina or "").strip()

        if dia not in ordem_dias:
            continue

        escolas.setdefault(escola, {})
        escolas[escola].setdefault(turma, {})
        escolas[escola][turma].setdefault((dia, inicio, fim), [])

        if disciplina and disciplina not in escolas[escola][turma][(dia, inicio, fim)]:
            escolas[escola][turma][(dia, inicio, fim)].append(disciplina)

    resultado = []

    for escola_nome in sorted(escolas, key=chave_texto_local):
        turmas = []

        for turma_nome in sorted(escolas[escola_nome], key=chave_turma_local):
            periodos = []

            for (dia, inicio, fim), disciplinas in escolas[escola_nome][turma_nome].items():
                periodos.append({
                    "dia": dia,
                    "inicio": inicio,
                    "fim": fim,
                    "disciplinas": sorted(disciplinas, key=chave_texto_local),
                })

            periodos.sort(
                key=lambda p: (
                    ordem_dias.get(p["dia"], 99),
                    p["inicio"],
                    p["fim"],
                )
            )

            turmas.append({
                "nome": turma_nome,
                "periodos": periodos,
            })

        resultado.append({
            "nome": escola_nome,
            "turmas": turmas,
        })

    return render_template(
        "ver_horarios.html",
        escolas=resultado,
    )

@turma_bp.route("/turmas/atribuicao-salas", methods=["GET", "POST"])
def atribuicao_salas():
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")

    turmas = _ordenar_turmas(Turma.query.all())

    if request.method == "POST":
        try:
            numero_salas = int(request.form.get("numero_salas", "0"))
        except ValueError:
            numero_salas = 0

        if numero_salas < 1 or numero_salas > 20:
            dados = obter_atribuicao_salas_semanal()
            return render_template(
                "atribuicao_salas.html",
                **dados,
                turmas=turmas,
                erro="Indique um número de salas entre 1 e 20.",
            )

        config = ConfiguracaoSalas.query.first()
        if not config:
            config = ConfiguracaoSalas(numero_salas=numero_salas)
            db.session.add(config)
        else:
            config.numero_salas = numero_salas

        antigos = PlaneamentoSala.query.all()

        for planeamento in antigos:
            AtribuicaoSala.query.filter_by(
                planeamento_id=planeamento.id
            ).delete(synchronize_session=False)
            db.session.delete(planeamento)

        padrao = re.compile(
            r"^turma__([a-z]+)__(\d+)__(\d+)$"
        )

        for chave_dia, _titulo in DIAS_ATRIBUICAO_SALAS:
            for sala_numero in range(1, numero_salas + 1):
                planeamento = PlaneamentoSala(
                    dia_semana=chave_dia,
                    sala_numero=sala_numero,
                    observacoes=request.form.get(
                        f"observacoes__{chave_dia}__{sala_numero}",
                        "",
                    ).strip() or None,
                )
                db.session.add(planeamento)
                db.session.flush()

                indices = set()

                for chave in request.form.keys():
                    match = padrao.match(chave)
                    if not match:
                        continue

                    dia_lido, sala_lida, indice = match.groups()

                    if dia_lido == chave_dia and int(sala_lida) == sala_numero:
                        indices.add(int(indice))

                for indice in sorted(indices):
                    turma_id = request.form.get(
                        f"turma__{chave_dia}__{sala_numero}__{indice}",
                        "",
                    ).strip()

                    texto = request.form.get(
                        f"texto__{chave_dia}__{sala_numero}__{indice}",
                        "",
                    ).strip()

                    if turma_id:
                        try:
                            turma_id_int = int(turma_id)
                        except ValueError:
                            turma_id_int = None

                        if turma_id_int and Turma.query.get(turma_id_int):
                            db.session.add(
                                AtribuicaoSala(
                                    planeamento_id=planeamento.id,
                                    turma_id=turma_id_int,
                                    ordem=indice,
                                )
                            )
                            continue

                    if texto:
                        db.session.add(
                            AtribuicaoSala(
                                planeamento_id=planeamento.id,
                                texto_livre=texto[:200],
                                ordem=indice,
                            )
                        )

        db.session.commit()

        return redirect(
            url_for(
                "turma.turmas",
                salas_guardadas=1,
            )
        )

    dados = obter_atribuicao_salas_semanal()

    return render_template(
        "atribuicao_salas.html",
        **dados,
        turmas=turmas,
        erro=None,
    )


@turma_bp.route("/turmas/atribuicao-salas/eliminar", methods=["POST"])
def eliminar_atribuicao_salas():
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")

    for planeamento in PlaneamentoSala.query.all():
        AtribuicaoSala.query.filter_by(
            planeamento_id=planeamento.id
        ).delete(synchronize_session=False)
        db.session.delete(planeamento)

    config = ConfiguracaoSalas.query.first()
    if config:
        db.session.delete(config)

    db.session.commit()

    return redirect(
        url_for(
            "turma.turmas",
            salas_eliminadas=1,
        )
    )


@turma_bp.route("/turmas")
def turmas():
    todas = _ordenar_turmas(Turma.query.all())
    alunos = Aluno.query.all()
    por_turma = {}
    for aluno in alunos:
        chave = ((aluno.escola or "").strip(), (aluno.turma or "").strip())
        por_turma.setdefault(chave, []).append(aluno)
    for lista in por_turma.values():
        lista.sort(key=lambda a: chave_texto(a.nome))

    turmas_com_horario = {
        (h.centro_escolar, h.turma)
        for h in HorarioTurma.query.all()
    }

    return render_template(
        "turmas.html",
        turmas=todas,
        alunos_por_turma=por_turma,
        disciplinas_da_turma=disciplinas_da_turma,
        dias_semana=DIAS_SEMANA,
        turmas_com_horario=turmas_com_horario,
        atribuicao_salas=obter_atribuicao_salas_semanal(),
    )


@turma_bp.route("/turmas/criar", methods=["GET", "POST"])
def criar_turma():
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        escola = request.form.get("escola", "").strip()
        ano_escolar = request.form.get("ano_escolar", "").strip()
        diretor_turma = request.form.get("diretor_turma", "").strip()
        disciplinas = _ler_disciplinas_formulario()

        if not nome or not escola or not ano_escolar:
            return render_template("turma_form.html", **preparar_form_turma(), erro="Preencha a escola, o ano escolar e o nome da turma.")
        if not disciplinas:
            return render_template("turma_form.html", **preparar_form_turma(), erro="Assinale pelo menos uma disciplina ou preencha a opção Outros.")
        if Turma.query.filter_by(nome=nome, escola=escola).first():
            return render_template("turma_form.html", **preparar_form_turma(), erro="Já existe uma turma com esse nome nessa escola.")

        turma = Turma(nome=nome, escola=escola, ano_escolar=ano_escolar, diretor_turma=diretor_turma or None, disciplinas=json.dumps(disciplinas, ensure_ascii=False))
        db.session.add(turma)
        db.session.commit()
        return redirect(url_for("turma.turma_detalhe", id=turma.id, criado=1))

    return render_template("turma_form.html", **preparar_form_turma(), erro=None)


@turma_bp.route("/turmas/editar/<int:id>", methods=["GET", "POST"])
def editar_turma(id):
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")
    turma = Turma.query.get_or_404(id)
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        escola = request.form.get("escola", "").strip()
        ano_escolar = request.form.get("ano_escolar", "").strip()
        diretor_turma = request.form.get("diretor_turma", "").strip()
        disciplinas = _ler_disciplinas_formulario()
        duplicada = Turma.query.filter(Turma.id != turma.id, Turma.nome == nome, Turma.escola == escola).first()
        if not nome or not escola or not ano_escolar:
            return render_template("turma_form.html", **preparar_form_turma(turma), erro="Preencha a escola, o ano escolar e o nome da turma.")
        if not disciplinas:
            return render_template("turma_form.html", **preparar_form_turma(turma), erro="Assinale pelo menos uma disciplina ou preencha a opção Outros.")
        if duplicada:
            return render_template("turma_form.html", **preparar_form_turma(turma), erro="Já existe uma turma com esse nome nessa escola.")
        nome_antigo, escola_antiga = turma.nome, turma.escola
        turma.nome, turma.escola, turma.ano_escolar = nome, escola, ano_escolar
        turma.diretor_turma = diretor_turma or None
        turma.disciplinas = json.dumps(disciplinas, ensure_ascii=False)
        # Mantém alunos e horários coerentes quando nome/escola da turma muda.
        for aluno in Aluno.query.filter_by(turma=nome_antigo, escola=escola_antiga).all():
            aluno.turma, aluno.escola = nome, escola
        for h in HorarioTurma.query.filter_by(turma=nome_antigo, centro_escolar=escola_antiga).all():
            h.turma, h.centro_escolar = nome, escola
        db.session.commit()
        return redirect(url_for("turma.turma_detalhe", id=turma.id, atualizado=1))
    return render_template("turma_form.html", **preparar_form_turma(turma), erro=None)


@turma_bp.route("/turmas/ver/<int:id>")
def turma_detalhe(id):
    turma = Turma.query.get_or_404(id)
    alunos = Aluno.query.filter_by(turma=turma.nome, escola=turma.escola).order_by(Aluno.nome.asc()).all()
    horarios = HorarioTurma.query.filter_by(centro_escolar=turma.escola, turma=turma.nome).all()
    return render_template("turma_detalhe.html", turma=turma, alunos=alunos, disciplinas=disciplinas_da_turma(turma), horarios=horarios, dias_semana=DIAS_SEMANA)


@turma_bp.route("/turmas/eliminar/<int:id>", methods=["POST"])
def eliminar_turma(id):
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")
    turma = Turma.query.get_or_404(id)
    alunos = Aluno.query.filter_by(turma=turma.nome, escola=turma.escola).all()
    horarios = HorarioTurma.query.filter_by(centro_escolar=turma.escola, turma=turma.nome).all()
    # Não elimina alunos; apenas retira a atribuição da turma.
    for aluno in alunos:
        aluno.turma = None
    for horario in horarios:
        db.session.delete(horario)
    db.session.delete(turma)
    db.session.commit()
    return redirect(url_for("turma.turmas", eliminado=1))


@turma_bp.route("/turmas/atribuir", methods=["GET", "POST"])
def atribuir_turma():
    if session.get("perfil") == "colaborador":
        return render_template("acesso_negado.html")
    turmas = _ordenar_turmas(Turma.query.all())
    alunos = Aluno.query.order_by(Aluno.nome.asc()).all()
    if request.method == "POST":
        turma_id = request.form.get("turma_id", "")
        aluno_ids = request.form.getlist("aluno_ids")
        turma = Turma.query.get(turma_id) if turma_id else None
        if not turma or not aluno_ids:
            return render_template("atribuir_turmas.html", turmas=turmas, alunos=alunos, erro="Escolha uma turma e pelo menos um aluno.")
        for aluno_id in aluno_ids:
            aluno = Aluno.query.get(aluno_id)
            if aluno:
                aluno.turma = turma.nome
                aluno.escola = turma.escola
        db.session.commit()
        return redirect(url_for("turma.turma_detalhe", id=turma.id, atribuicao=1))
    return render_template("atribuir_turmas.html", turmas=turmas, alunos=alunos, erro=None)
