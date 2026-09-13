import json
import re
import unicodedata

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


turma_bp = Blueprint("turma", __name__)


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
    "10.º Ano": ["Português", "Matemática A", "Matemática B", "MACS", "Inglês", "Biologia e Geologia", "Física e Química A", "História A", "Geografia A", "Economia A", "Filosofia"],
    "11.º Ano": ["Português", "Matemática A", "Matemática B", "MACS", "Inglês", "Biologia e Geologia", "Física e Química A", "História A", "Geografia A", "Economia A", "Filosofia"],
    "12.º Ano": ["Português", "Matemática A", "Matemática B", "MACS", "Inglês", "Biologia e Geologia", "Física e Química A", "História A", "Geografia A", "Economia A", "Filosofia"],
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

    return render_template(
        "turmas.html",
        turmas=todas,
        alunos_por_turma=por_turma,
        disciplinas_da_turma=disciplinas_da_turma,
        dias_semana=DIAS_SEMANA,
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
