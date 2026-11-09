from flask import Blueprint, render_template, request, redirect, session

from models import db
from models.aluno import Aluno
from models.nota import Nota


notas_bp = Blueprint(
    "notas",
    __name__
)


import logging

from sqlalchemy import text

from ciclos import ANO_TURMA_SQL, disciplina_ciencias, evolucao_notas, medias_notas


def _medias_ciclos():
    """Medias por ciclo e disciplina. So leitura. Nunca parte a pagina: devolve None se falhar."""
    try:
        linhas = db.session.execute(text(
            f"SELECT n.aluno_id, n.disciplina, n.nota, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM notas n JOIN alunos a ON a.id = n.aluno_id "
            "WHERE n.nota IS NOT NULL AND a.ativo IS NOT FALSE"
        )).mappings().all()
        return medias_notas([dict(l) for l in linhas], "todas")
    except Exception:
        db.session.rollback()
        logging.exception("Nao foi possivel calcular as medias por ciclo")
        return None


def _evolucao_ciclos():
    """Evolucao mensal das medias globais por ciclo e disciplina. So leitura. Devolve None se falhar."""
    try:
        linhas = db.session.execute(text(
            f"SELECT n.disciplina, n.nota, n.data_avaliacao, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM notas n JOIN alunos a ON a.id = n.aluno_id "
            "WHERE n.nota IS NOT NULL AND a.ativo IS NOT FALSE"
        )).mappings().all()
        return evolucao_notas([dict(l) for l in linhas])
    except Exception:
        db.session.rollback()
        logging.exception("Nao foi possivel calcular a evolucao das medias por ciclo")
        return None


@notas_bp.route("/notas", methods=["GET", "POST"])
def notas():


    if (
        session.get("perfil") == "colaborador"
        and request.method == "POST"
    ):
        return render_template(
            "acesso_negado.html"
        )

    if request.method == "POST":

        nota = Nota(
            aluno_id=request.form["aluno_id"],
            disciplina=disciplina_ciencias(request.form["disciplina"]),
            nota=float(request.form["nota"]),
            data_avaliacao=request.form["data_avaliacao"]
        )

        db.session.add(nota)
        db.session.commit()

        return redirect("/notas")

    alunos = Aluno.query.order_by(
        Aluno.nome
    ).all()

    notas = Nota.query.order_by(
        Nota.id.desc()
    ).all()

    return render_template(
        "notas.html",
        alunos=alunos,
        notas=notas,
        medias_ciclos=_medias_ciclos(),
        evolucao_ciclos=_evolucao_ciclos()
    )


@notas_bp.route(
    "/notas/editar/<int:id>",
    methods=["GET", "POST"]
)
def editar_nota(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    nota = Nota.query.get_or_404(id)

    if request.method == "POST":

        nota.disciplina = disciplina_ciencias(request.form["disciplina"])

        nota.nota = float(
            request.form["nota"]
        )

        nota.data_avaliacao = request.form[
            "data_avaliacao"
        ]

        db.session.commit()

        return redirect("/notas")

    return render_template(
        "editar_nota.html",
        nota=nota
    )


@notas_bp.route("/notas/apagar/<int:id>")
def apagar_nota(id):

    if session.get("perfil") == "colaborador":

        return render_template(
            "acesso_negado.html"
        )

    nota = Nota.query.get_or_404(id)

    db.session.delete(nota)

    db.session.commit()

    return redirect("/notas")


# =====================================================================
# Lancamento de notas em lote (turma -> alunos -> disciplina -> data)
# =====================================================================
import json
import re
from datetime import date

from flask import jsonify

from models.teste import Teste
from models.turma import Turma
from ciclos import disciplina_norm


def _texto_simples(valor):
    return (valor or "").strip().casefold()


def _chave_disciplina(nome):
    return disciplina_norm(nome or "").casefold()


def _data_iso_valida(valor):
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", valor or ""))


def _alunos_da_turma_lote(turma):
    alunos = Aluno.query.filter_by(
        turma=turma.nome,
        escola=turma.escola
    ).order_by(Aluno.nome.asc()).all()
    return [a for a in alunos if a.ativo is not False]


def _disciplinas_da_turma_lote(turma):
    try:
        dados = json.loads(turma.disciplinas or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(dados, list):
        return []
    resultado = []
    for item in dados:
        nome = disciplina_ciencias(str(item)).strip()
        if nome and nome not in resultado:
            resultado.append(nome)
    return resultado


def _sugestoes_lote(turma, alunos, disciplina):
    chave = _chave_disciplina(disciplina)
    ids = [a.id for a in alunos]
    total = len(ids)
    hoje_iso = date.today().isoformat()

    datas = set()
    for teste in Teste.query.all():
        if _texto_simples(teste.turma) != _texto_simples(turma.nome):
            continue
        if _texto_simples(teste.escola) != _texto_simples(turma.escola):
            continue
        if _chave_disciplina(teste.disciplina) != chave:
            continue
        d = (teste.data_teste or "").strip()[:10]
        if _data_iso_valida(d) and d <= hoje_iso:
            datas.add(d)

    lancadas = {}
    if ids:
        for nota in Nota.query.filter(Nota.aluno_id.in_(ids)).all():
            if _chave_disciplina(nota.disciplina) == chave:
                d = (nota.data_avaliacao or "").strip()[:10]
                lancadas.setdefault(d, set()).add(nota.aluno_id)

    resultado = []
    for d in sorted(datas, reverse=True):
        feitas = len(lancadas.get(d, ()))
        if feitas < total:
            resultado.append({"data": d, "lancadas": feitas, "total": total})
    return resultado


@notas_bp.route("/notas/api/turmas")
def api_turmas_lote():
    turmas = sorted(
        Turma.query.all(),
        key=lambda t: ((t.escola or "").casefold(), (t.nome or "").casefold())
    )
    return jsonify([
        {
            "id": t.id,
            "rotulo": ((t.nome or "") + " \u00b7 " + t.escola) if t.escola else (t.nome or "")
        }
        for t in turmas
    ])


@notas_bp.route("/notas/api/turma/<int:id>")
def api_turma_lote(id):
    turma = Turma.query.get_or_404(id)
    alunos = _alunos_da_turma_lote(turma)
    disciplinas = _disciplinas_da_turma_lote(turma)
    chaves = {_chave_disciplina(d) for d in disciplinas}
    ids = [a.id for a in alunos]
    if ids:
        for nota in Nota.query.filter(Nota.aluno_id.in_(ids)).all():
            nome = disciplina_ciencias(nota.disciplina or "").strip()
            if nome and _chave_disciplina(nome) not in chaves:
                disciplinas.append(nome)
                chaves.add(_chave_disciplina(nome))
    return jsonify({
        "disciplinas": disciplinas,
        "alunos": [{"id": a.id, "nome": a.nome} for a in alunos]
    })


@notas_bp.route("/notas/api/lote")
def api_ler_lote():
    turma_id = request.args.get("turma_id", type=int)
    turma = Turma.query.get(turma_id) if turma_id else None
    disciplina = (request.args.get("disciplina") or "").strip()
    data = (request.args.get("data") or "").strip()
    if turma is None or not disciplina:
        return jsonify({"existentes": {}, "sugestoes": []})

    alunos = _alunos_da_turma_lote(turma)
    ids = [a.id for a in alunos]
    chave = _chave_disciplina(disciplina)

    existentes = {}
    if ids and _data_iso_valida(data):
        for nota in Nota.query.filter(Nota.aluno_id.in_(ids)).all():
            if (nota.data_avaliacao or "").strip()[:10] != data:
                continue
            if _chave_disciplina(nota.disciplina) != chave:
                continue
            existentes.setdefault(str(nota.aluno_id), {"id": nota.id, "nota": nota.nota})

    return jsonify({
        "existentes": existentes,
        "sugestoes": _sugestoes_lote(turma, alunos, disciplina)
    })


@notas_bp.route("/notas/api/lote", methods=["POST"])
def api_guardar_lote():
    if session.get("perfil") == "colaborador":
        return jsonify({"ok": False, "erro": "Sem permiss\u00e3o para guardar notas."}), 403

    dados = request.get_json(silent=True) or {}

    try:
        turma_id = int(dados.get("turma_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "erro": "Turma inv\u00e1lida."}), 400

    turma = Turma.query.get(turma_id)
    disciplina = disciplina_ciencias(str(dados.get("disciplina") or "")).strip()
    data = str(dados.get("data") or "").strip()
    pedidos = dados.get("notas")

    if turma is None or not disciplina:
        return jsonify({"ok": False, "erro": "Escolha a turma e a disciplina."}), 400
    if not _data_iso_valida(data):
        return jsonify({"ok": False, "erro": "Data inv\u00e1lida."}), 400
    if not isinstance(pedidos, dict) or not pedidos:
        return jsonify({"ok": False, "erro": "N\u00e3o h\u00e1 notas para guardar."}), 400

    alunos = {str(a.id): a for a in _alunos_da_turma_lote(turma)}
    chave = _chave_disciplina(disciplina)

    valores = {}
    for aluno_id, bruto in pedidos.items():
        aluno = alunos.get(str(aluno_id))
        if aluno is None:
            return jsonify({"ok": False, "erro": "H\u00e1 um aluno que n\u00e3o pertence a esta turma."}), 400
        texto = str(bruto).strip().replace(",", ".")
        if texto == "":
            continue
        try:
            valor = float(texto)
        except ValueError:
            return jsonify({"ok": False, "erro": "Nota inv\u00e1lida para " + str(aluno.nome) + "."}), 400
        if valor != valor or valor < 0 or valor > 100:
            return jsonify({"ok": False, "erro": "A nota de " + str(aluno.nome) + " tem de estar entre 0 e 100."}), 400
        valores[aluno.id] = valor

    if not valores:
        return jsonify({"ok": False, "erro": "N\u00e3o h\u00e1 notas para guardar."}), 400

    existentes = {}
    for nota in Nota.query.filter(Nota.aluno_id.in_(list(valores.keys()))).all():
        if (nota.data_avaliacao or "").strip()[:10] == data and _chave_disciplina(nota.disciplina) == chave:
            existentes.setdefault(nota.aluno_id, nota)

    criadas = 0
    atualizadas = 0
    for aluno_id, valor in valores.items():
        nota = existentes.get(aluno_id)
        if nota is None:
            db.session.add(Nota(
                aluno_id=aluno_id,
                disciplina=disciplina,
                nota=valor,
                data_avaliacao=data
            ))
            criadas += 1
        elif nota.nota != valor:
            nota.nota = valor
            atualizadas += 1

    db.session.commit()
    return jsonify({"ok": True, "criadas": criadas, "atualizadas": atualizadas})


@notas_bp.route("/notas/api/apagar/<int:id>", methods=["POST"])
def api_apagar_nota_lote(id):
    if session.get("perfil") == "colaborador":
        return jsonify({"ok": False, "erro": "Sem permiss\u00e3o para excluir notas."}), 403
    nota = Nota.query.get_or_404(id)
    db.session.delete(nota)
    db.session.commit()
    return jsonify({"ok": True})
