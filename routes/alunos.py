from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    send_file,
)

from models import db
from models.aluno import (
    Aluno,
    aluno_necessidades,
    aluno_objetivos,
)
from models.frequencia import Frequencia
from models.necessidade import Necessidade
from models.objetivo import Objetivo
from models.nota import Nota
from models.teste import Teste

from models.configuracao_centro import ConfiguracaoCentro

from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing, PolyLine, Circle, String, Line, Rect
from reportlab.graphics import renderPDF

import qrcode
import os
from datetime import date


alunos_bp = Blueprint(
    "alunos",
    __name__
)


# ------------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------------

def gerar_codigo():

    ultimo = Aluno.query.order_by(
        Aluno.id.desc()
    ).first()

    if not ultimo:
        return "10001"

    return str(int(ultimo.codigo) + 1)


def horas_para_hhmm(valor):

    total_minutos = int(round(valor * 60))
    horas = total_minutos // 60
    minutos = total_minutos % 60

    return f"{horas:02d}:{minutos:02d}"


def texto_normalizado(valor):

    return str(valor or "").strip().lower()


def preparar_dados_grafico(notas):
    notas = sorted(
        notas,
        key=lambda n: n.data_avaliacao
    )

    labels_grafico = sorted(
        {
            nota.data_avaliacao.strftime("%Y-%m-%d")
            if hasattr(nota.data_avaliacao, "strftime")
            else str(nota.data_avaliacao)
            for nota in notas
        }
    )

    disciplinas = {}

    for nota in notas:

        dt_str = (
            nota.data_avaliacao.strftime("%Y-%m-%d")
            if hasattr(nota.data_avaliacao, "strftime")
            else str(nota.data_avaliacao)
        )

        if nota.disciplina not in disciplinas:
            disciplinas[nota.disciplina] = {}

        disciplinas[nota.disciplina][dt_str] = nota.nota

    return labels_grafico, disciplinas


def desenhar_grafico_reportlab(labels, disciplinas_dict, largura=500, altura=200):
    """
    Desenha um gráfico de linhas usando apenas reportlab.
    Devolve um objeto Drawing pronto a inserir no PDF.
    """

    margem_esq = 50
    margem_dir = 20
    margem_topo = 20
    margem_base = 40

    area_w = largura - margem_esq - margem_dir
    area_h = altura - margem_topo - margem_base

    drawing = Drawing(largura, altura)

    # Fundo branco
    drawing.add(Rect(0, 0, largura, altura, fillColor=colors.white, strokeColor=colors.white))

    # Determinar min/max das notas
    todos_valores = [
        v
        for d in disciplinas_dict.values()
        for v in d.values()
        if v is not None
    ]

    if not todos_valores:
        return drawing

    nota_min = max(0, min(todos_valores) - 1)
    nota_max = min(20, max(todos_valores) + 1)
    intervalo = nota_max - nota_min if nota_max != nota_min else 1

    n_labels = len(labels)
    if n_labels < 2:
        x_step = area_w
    else:
        x_step = area_w / (n_labels - 1)

    def x_para(i):
        return margem_esq + i * x_step

    def y_para(nota):
        return margem_base + ((nota - nota_min) / intervalo) * area_h

    # Grelha horizontal
    for grid_val in range(int(nota_min), int(nota_max) + 1, 2):
        gy = y_para(grid_val)
        drawing.add(Line(
            margem_esq, gy, largura - margem_dir, gy,
            strokeColor=colors.lightgrey, strokeWidth=0.5
        ))
        drawing.add(String(
            margem_esq - 5, gy - 3, str(grid_val),
            fontSize=7, fillColor=colors.grey,
            textAnchor='end'
        ))

    # Eixo X — datas
    for i, label in enumerate(labels):
        gx = x_para(i)
        drawing.add(Line(
            gx, margem_base - 3, gx, margem_base,
            strokeColor=colors.grey, strokeWidth=0.5
        ))
        data_curta = label[5:] if len(label) >= 7 else label  # MM-DD
        drawing.add(String(
            gx, margem_base - 12, data_curta,
            fontSize=6, fillColor=colors.grey,
            textAnchor='middle'
        ))

    # Paleta de cores para as disciplinas
    palette = [
        colors.HexColor("#2563eb"),
        colors.HexColor("#dc2626"),
        colors.HexColor("#16a34a"),
        colors.HexColor("#d97706"),
        colors.HexColor("#7c3aed"),
        colors.HexColor("#db2777"),
    ]

    legend_y = altura - 12

    for idx, (nome_disciplina, valores) in enumerate(disciplinas_dict.items()):
        cor = palette[idx % len(palette)]

        serie = []
        ultimo_valor = None
        for data_str in labels:
            v = valores.get(data_str)
            if v is not None:
                ultimo_valor = v
            serie.append(ultimo_valor)

        # Linha
        pontos = []
        for i, val in enumerate(serie):
            if val is not None:
                pontos.extend([x_para(i), y_para(val)])

        if len(pontos) >= 4:
            drawing.add(PolyLine(
                pontos,
                strokeColor=cor,
                strokeWidth=1.5,
                fillColor=None
            ))

        # Pontos (círculos)
        for i, val in enumerate(serie):
            if val is not None:
                drawing.add(Circle(
                    x_para(i), y_para(val), 3,
                    fillColor=cor, strokeColor=colors.white, strokeWidth=1
                ))

        # Legenda
        lx = margem_esq + idx * 100
        drawing.add(Line(
            lx, legend_y, lx + 15, legend_y,
            strokeColor=cor, strokeWidth=2
        ))
        drawing.add(String(
            lx + 18, legend_y - 3, nome_disciplina,
            fontSize=7, fillColor=colors.black
        ))

    # Título
    drawing.add(String(
        largura / 2, altura - 8, "Evolução das Notas",
        fontSize=9, fillColor=colors.black,
        textAnchor='middle'
    ))

    return drawing


# ------------------------------------------------------------------
# ROTAS
# ------------------------------------------------------------------

@alunos_bp.route("/alunos")
def listar_alunos():

    alunos = Aluno.query.order_by(
        Aluno.nome.asc()
    ).all()

    necessidades = Necessidade.query.order_by(
        Necessidade.nome.asc()
    ).all()

    objetivos = Objetivo.query.order_by(
        Objetivo.nome.asc()
    ).all()

    alunos_agrupados = {}

    for aluno in alunos:

        escola = aluno.escola or "Sem Escola"
        turma = aluno.turma or "Sem Turma"

        if escola not in alunos_agrupados:
            alunos_agrupados[escola] = {}

        if turma not in alunos_agrupados[escola]:
            alunos_agrupados[escola][turma] = []

        alunos_agrupados[escola][turma].append(aluno)

    return render_template(
        "alunos.html",
        alunos=alunos,
        alunos_agrupados=alunos_agrupados,
        necessidades=necessidades,
        objetivos=objetivos,
    )


@alunos_bp.route("/alunos/ver/<int:id>")
def ver_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    notas = Nota.query.filter_by(
        aluno_id=aluno.id
    ).order_by(Nota.data_avaliacao.asc()).all()

    hoje = date.today().strftime("%Y-%m-%d")

    proximos_testes = Teste.query.filter(
        Teste.data_teste >= hoje
    ).order_by(Teste.data_teste.asc()).all()

    total_horas = sum(
        (f.duracao_horas or 0) for f in aluno.frequencias
    )

    labels_grafico, disciplinas = preparar_dados_grafico(notas)

    # --------------------------------------------------
    # MÉDIAS POR DISCIPLINA
    # --------------------------------------------------

    medias_dict = {}

    for nota in notas:

        if nota.disciplina not in medias_dict:

            medias_dict[nota.disciplina] = {
                "soma": 0,
                "quantidade": 0,
            }

        medias_dict[nota.disciplina]["soma"] += nota.nota
        medias_dict[nota.disciplina]["quantidade"] += 1

    medias = []

    for disciplina, dados in medias_dict.items():

        media = round(
            dados["soma"] / dados["quantidade"],
            2
        )

        medias.append(
            {
                "disciplina": disciplina,
                "media": media,
            }
        )

    # --------------------------------------------------
    # GRÁFICO
    # --------------------------------------------------

    datasets_grafico = []

    for nome_disciplina, valores in disciplinas.items():

        serie = []
        ultimo_valor = None

        for data_str in labels_grafico:

            valor = valores.get(data_str)

            if valor is not None:
                ultimo_valor = valor

            serie.append(ultimo_valor)

        datasets_grafico.append(
            {
                "label": nome_disciplina,
                "data": serie,
                "fill": False,
                "tension": 0.2,
            }
        )

    return render_template(
        "ver_aluno.html",
        aluno=aluno,
        notas=notas,
        proximos_testes=proximos_testes,
        total_horas=total_horas,
        labels_grafico=labels_grafico,
        disciplinas=disciplinas,
        medias=medias,
        datasets_grafico=datasets_grafico,
    )


@alunos_bp.route("/alunos/editar/<int:id>", methods=["GET", "POST"])
def editar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    necessidades = Necessidade.query.order_by(Necessidade.nome.asc()).all()
    objetivos = Objetivo.query.order_by(Objetivo.nome.asc()).all()

    if request.method == "POST":

        aluno.nome = request.form.get("nome", "").strip()
        aluno.escola = request.form.get("escola", "").strip()
        aluno.ano_escolar = request.form.get("ano_escolar", "").strip()
        aluno.turma = request.form.get("turma", "").strip()
        aluno.encarregado = request.form.get("encarregado", "").strip()
        aluno.telefone = request.form.get("telefone", "").strip()

        db.session.commit()

        return redirect(f"/alunos/ver/{aluno.id}")

    return render_template(
        "editar_aluno.html",
        aluno=aluno,
        necessidades=necessidades,
        objetivos=objetivos,
    )


@alunos_bp.route("/alunos/apagar/<int:id>", methods=["POST"])
def apagar_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    db.session.delete(aluno)
    db.session.commit()

    return redirect("/alunos")


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------

@alunos_bp.route("/alunos/pdf/<int:id>")
def pdf_aluno(id):

    aluno = Aluno.query.get_or_404(id)

    configuracao = ConfiguracaoCentro.query.first()

    notas = Nota.query.filter_by(
        aluno_id=aluno.id
    ).order_by(Nota.data_avaliacao.asc()).all()

    hoje = date.today().strftime("%Y-%m-%d")

    proximos_testes = Teste.query.filter(
        Teste.data_teste >= hoje
    ).order_by(Teste.data_teste.asc()).all()

    total_horas = sum(
        (f.duracao_horas or 0) for f in aluno.frequencias
    )

    # Médias por disciplina
    medias_dict = {}

    for nota in notas:

        if nota.disciplina not in medias_dict:
            medias_dict[nota.disciplina] = {"soma": 0, "quantidade": 0}

        medias_dict[nota.disciplina]["soma"] += nota.nota
        medias_dict[nota.disciplina]["quantidade"] += 1

    medias = [
        (
            disciplina,
            round(
                dados["soma"] / dados["quantidade"],
                2
            ) if dados["quantidade"] > 0 else 0
        )
        for disciplina, dados in medias_dict.items()
    ]

    # ------------------------------------------------------------------
    # Canvas
    # ------------------------------------------------------------------

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    largura, altura = A4
    pagina = 1
    y = altura - 50

    # ------------------------------------------------------------------
    # Funções internas
    # ------------------------------------------------------------------

    def nova_pagina():

        nonlocal y, pagina

        pdf.setFont("Helvetica", 9)
        pdf.drawRightString(largura - 40, 20, f"Página {pagina}")
        pdf.showPage()

        pagina += 1
        y = altura - 50

    def escrever(texto, espacamento=16):

        nonlocal y

        if y < 60:
            nova_pagina()

        pdf.drawString(50, y, str(texto))
        y -= espacamento

    # ------------------------------------------------------------------
    # CABEÇALHO
    # ------------------------------------------------------------------

    if configuracao and configuracao.logo:

        caminho_logo = os.path.join("static", "logos", configuracao.logo)

        if os.path.exists(caminho_logo):
            try:
                pdf.drawImage(
                    caminho_logo,
                    50,
                    altura - 100,
                    width=80,
                    height=80,
                    preserveAspectRatio=True,
                )
            except Exception:
                pass

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(
        150,
        altura - 60,
        configuracao.nome_centro if configuracao else "Centro de Estudos",
    )

    y = altura - 130

    # ------------------------------------------------------------------
    # DADOS DO ALUNO
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("DADOS DO ALUNO")

    pdf.setFont("Helvetica", 11)
    escrever(f"Código: {aluno.codigo}")
    escrever(f"Nome: {aluno.nome}")
    escrever(f"Escola: {aluno.escola}")
    escrever(f"Ano Escolar: {aluno.ano_escolar}")
    escrever(f"Turma: {aluno.turma}")

    y -= 10

    # ------------------------------------------------------------------
    # CONTACTOS
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("CONTACTOS")

    pdf.setFont("Helvetica", 11)
    escrever(f"Encarregado: {aluno.encarregado}")
    escrever(f"Telefone: {aluno.telefone}")

    y -= 10

    # ------------------------------------------------------------------
    # GRÁFICO DE EVOLUÇÃO
    # ------------------------------------------------------------------

    if notas:

        labels_grafico, disciplinas = preparar_dados_grafico(notas)

        if y < 260:
            nova_pagina()

        grafico_altura = 220
        grafico = desenhar_grafico_reportlab(labels_grafico, disciplinas, largura=500, altura=grafico_altura)
        renderPDF.draw(grafico, pdf, 50, y - grafico_altura)

        y -= grafico_altura + 10

    y -= 10

    # ------------------------------------------------------------------
    # MÉDIAS POR DISCIPLINA
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("MÉDIAS POR DISCIPLINA")

    pdf.setFont("Helvetica", 11)

    if medias:
        for disciplina, media in medias:
            escrever(f"{disciplina}: {media}")
    else:
        escrever("Sem notas registadas.")

    y -= 10

    # ------------------------------------------------------------------
    # HISTÓRICO DE NOTAS
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("HISTÓRICO DE NOTAS")

    pdf.setFont("Helvetica", 11)

    if notas:
        for nota in notas:

            data_str = (
                nota.data_avaliacao.strftime("%d/%m/%Y")
                if hasattr(nota.data_avaliacao, "strftime")
                else str(nota.data_avaliacao)
            )

            escrever(f"{data_str}  |  {nota.disciplina}  |  {nota.nota}")
    else:
        escrever("Sem notas registadas.")

    y -= 10

    # ------------------------------------------------------------------
    # PRÓXIMOS TESTES
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("PRÓXIMOS TESTES")

    pdf.setFont("Helvetica", 11)

    if proximos_testes:
        for teste in proximos_testes:

            data_str = (
                teste.data_teste.strftime("%d/%m/%Y")
                if hasattr(teste.data_teste, "strftime")
                else str(teste.data_teste)
            )

            texto_teste = (
                teste.matriz
                or teste.observacoes
                or ""
            )

            escrever(
                f"{data_str}  |  {teste.disciplina}  |  {texto_teste}"
            )

    else:
        escrever("Sem testes agendados.")

    y -= 10

    # ------------------------------------------------------------------
    # HISTÓRICO DE FREQUÊNCIAS
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica-Bold", 14)
    escrever("HISTÓRICO DE FREQUÊNCIAS")

    pdf.setFont("Helvetica", 10)

    if aluno.frequencias:

        escrever(
            "Data | Entrada | Saída | Duração | Disciplinas"
        )

        escrever(
            "------------------------------------------------------------"
        )

        for freq in aluno.frequencias:

            data_str = str(freq.data or "")
            entrada = str(freq.hora_entrada or "")
            saida = str(freq.hora_saida or "")

            hhmm = horas_para_hhmm(
                freq.duracao_horas or 0
            )

            disciplinas_freq = str(freq.disciplinas or "")
            observacoes = str(freq.observacoes or "")

            escrever(
                f"{data_str} | {entrada} | {saida} | {hhmm}"
            )

            if disciplinas_freq:
                escrever(f"Disciplinas: {disciplinas_freq}", 12)

            if observacoes:
                escrever(f"Obs: {observacoes}", 12)

            y -= 4

        y -= 6
        escrever(f"Total de horas: {horas_para_hhmm(total_horas)}")

    else:

        escrever("Sem frequências registadas.")

    y -= 10

    # ------------------------------------------------------------------
    # FECHO DA ÚLTIMA PÁGINA
    # ------------------------------------------------------------------

    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(largura - 40, 20, f"Página {pagina}")

    # ------------------------------------------------------------------
    # GUARDAR E DEVOLVER
    # ------------------------------------------------------------------

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"aluno_{aluno.codigo}.pdf",
    )
