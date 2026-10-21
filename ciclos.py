"""Divisao por ciclo (1.o, 2.o, 3.o) e medias de notas por ciclo e disciplina.

So leitura. A logica e pura (sem Flask) para poder ser testada.
O blueprint cria-se com criar_blueprint_ciclos(db, proteger=login_required).
"""
import re
import unicodedata
from collections import defaultdict

CICLOS = ("1.\u00ba ciclo", "2.\u00ba ciclo", "3.\u00ba ciclo")
SEM_CICLO = "Sem ciclo"

# Equivalencias de disciplinas (proposta). Valores nao listados ficam como estao.
CANON = {
    "matematica": "Matem\u00e1tica", "matmatica": "Matem\u00e1tica",
    "portugues": "Portugu\u00eas",
    "ingles": "Ingl\u00eas", "ing": "Ingl\u00eas",
    "ciencias": "Ci\u00eancias", "ciencias naturais": "Ci\u00eancias",
    "fisico quimica": "F\u00edsico-Qu\u00edmica",
    "hgp": "HGP", "historia e geografia de portugal": "HGP",
    "historia": "Hist\u00f3ria", "geografia": "Geografia",
    "espanhol": "Espanhol", "frances": "Franc\u00eas",
    "estudo do meio": "Estudo do Meio",
}


def _norm(texto):
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9/]+", " ", t).strip()


def disciplina_norm(texto):
    return CANON.get(_norm(texto), (texto or "").strip() or "Sem disciplina")


def ano_de(texto):
    m = re.match(r"\s*(\d{1,2})", texto or "")
    return int(m.group(1)) if m else None


def ciclo_de(ano):
    if ano is None:
        return SEM_CICLO
    if 1 <= ano <= 4:
        return CICLOS[0]
    if 5 <= ano <= 6:
        return CICLOS[1]
    if 7 <= ano <= 9:
        return CICLOS[2]
    return SEM_CICLO


def resolver(ano_turma, nome_turma):
    """Devolve (ciclo, origem). origem: ano_da_turma, deduzido_do_nome ou sem_ano."""
    ano = ano_de(ano_turma)
    if ano is not None:
        return ciclo_de(ano), "ano_da_turma"
    ano = ano_de(nome_turma)
    if ano is not None:
        return ciclo_de(ano), "deduzido_do_nome"
    return SEM_CICLO, "sem_ano"


def resumo_alunos(linhas):
    """linhas: dicts com 'id', 'turma' e 'ano_turma'."""
    por_ciclo = {c: 0 for c in CICLOS + (SEM_CICLO,)}
    origem = defaultdict(int)
    mapa = {}
    for l in linhas:
        c, o = resolver(l.get("ano_turma"), l.get("turma"))
        por_ciclo[c] += 1
        origem[o] += 1
        mapa[str(l["id"])] = c
    return {
        "total": len(linhas),
        "por_ciclo": por_ciclo,
        "origem_ano": dict(origem),
        "mapa": mapa,
    }


def medias_notas(linhas, metodo="todas"):
    """linhas: dicts com 'aluno_id', 'disciplina', 'nota', 'turma' e 'ano_turma'."""
    acum = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    origem = defaultdict(int)
    notas_ciclo = defaultdict(int)
    todas = []
    for l in linhas:
        if l.get("nota") is None:
            continue
        c, o = resolver(l.get("ano_turma"), l.get("turma"))
        origem[o] += 1
        notas_ciclo[c] += 1
        valor = float(l["nota"])
        todas.append(valor)
        acum[c][disciplina_norm(l.get("disciplina"))][l["aluno_id"]].append(valor)

    ciclos = {}
    for c in CICLOS:
        disciplinas = []
        for disc, por_aluno in sorted(acum[c].items()):
            notas = [n for lst in por_aluno.values() for n in lst]
            if metodo == "por_aluno":
                medias = [sum(v) / len(v) for v in por_aluno.values()]
                media = sum(medias) / len(medias)
            else:
                media = sum(notas) / len(notas)
            disciplinas.append({
                "disciplina": disc,
                "media": round(media, 2),
                "notas": len(notas),
                "alunos": len(por_aluno),
            })
        ciclos[c] = {"notas": notas_ciclo[c], "disciplinas": disciplinas}

    return {
        "metodo": metodo,
        "ciclos": ciclos,
        "sem_ciclo": {"notas": notas_ciclo[SEM_CICLO]},
        "origem_ano": dict(origem),
        "nota_minima": min(todas) if todas else None,
        "nota_maxima": max(todas) if todas else None,
    }


def _mes_da_data(valor):
    """Devolve (ano, mes) a partir de 'AAAA-MM-DD...' ou 'DD/MM/AAAA' (ou com '-'); None se ilegivel."""
    import re
    s = str(valor or "").strip()
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        ano, mes = int(m.group(1)), int(m.group(2))
    else:
        m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
        if not m:
            return None
        mes, ano = int(m.group(2)), int(m.group(3))
    if not (1 <= mes <= 12) or not (1900 <= ano <= 2200):
        return None
    return ano, mes


def evolucao_notas(linhas):
    """linhas: dicts com 'disciplina', 'nota', 'turma', 'ano_turma' e 'data_avaliacao'.
    Media GLOBAL (todas as notas de todos os alunos) por ciclo, disciplina e mes."""
    acum = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    sem_data = 0
    for l in linhas:
        if l.get("nota") is None:
            continue
        c, _o = resolver(l.get("ano_turma"), l.get("turma"))
        if c not in CICLOS:
            continue
        ym = _mes_da_data(l.get("data_avaliacao"))
        if ym is None:
            sem_data += 1
            continue
        acum[c][disciplina_norm(l.get("disciplina"))][ym].append(float(l["nota"]))

    ciclos = {}
    for c in CICLOS:
        todos = [ym for por_mes in acum[c].values() for ym in por_mes.keys()]
        if not todos:
            ciclos[c] = {"meses": [], "rotulos": [], "series": []}
            continue
        ano, mes = min(todos)
        fim = max(todos)
        meses = []
        while (ano, mes) <= fim:
            meses.append((ano, mes))
            mes += 1
            if mes > 12:
                ano, mes = ano + 1, 1
        series = []
        for disc, por_mes in sorted(acum[c].items()):
            medias = []
            contagens = []
            for ym in meses:
                v = por_mes.get(ym)
                if v:
                    medias.append(round(sum(v) / len(v), 2))
                    contagens.append(len(v))
                else:
                    medias.append(None)
                    contagens.append(0)
            series.append({"disciplina": disc, "medias": medias, "contagens": contagens})
        ciclos[c] = {
            "meses": ["%04d-%02d" % ym for ym in meses],
            "rotulos": ["%02d/%04d" % (ym[1], ym[0]) for ym in meses],
            "series": series,
        }
    return {"ciclos": ciclos, "sem_data": sem_data}


ANO_TURMA_SQL = (
    "(SELECT t.ano_escolar FROM turmas t WHERE t.escola = a.escola AND t.nome = a.turma "
    "ORDER BY (t.ano_escolar IS NULL) LIMIT 1)"
)


def criar_blueprint_ciclos(db, proteger=None):
    from flask import Blueprint, jsonify, request
    from sqlalchemy import text

    proteger = proteger or (lambda f: f)
    bp = Blueprint("ciclos", __name__)

    @bp.get("/api/ciclos/alunos")
    @proteger
    def alunos_por_ciclo():
        linhas = db.session.execute(text(
            f"SELECT a.id, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM alunos a WHERE a.ativo IS NOT FALSE"
        )).mappings().all()
        return jsonify(resumo_alunos([dict(l) for l in linhas]))

    @bp.get("/api/ciclos/medias-notas")
    @proteger
    def medias():
        metodo = request.args.get("metodo", "todas")
        if metodo not in ("todas", "por_aluno"):
            return jsonify({"erro": "metodo deve ser 'todas' ou 'por_aluno'"}), 422
        linhas = db.session.execute(text(
            f"SELECT n.aluno_id, n.disciplina, n.nota, a.turma, {ANO_TURMA_SQL} AS ano_turma "
            "FROM notas n JOIN alunos a ON a.id = n.aluno_id "
            "WHERE n.nota IS NOT NULL AND a.ativo IS NOT FALSE"
        )).mappings().all()
        return jsonify(medias_notas([dict(l) for l in linhas], metodo))

    return bp