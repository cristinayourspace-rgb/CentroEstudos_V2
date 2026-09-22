from datetime import datetime, timedelta
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session
)

from config import Config

from models import db

from models.utilizador import Utilizador
from models.aluno import Aluno
from models.necessidade import Necessidade
from models.objetivo import Objetivo
from models.nota import Nota
from models.frequencia import Frequencia
from models.teste import Teste
from models.evento import Evento
from models.configuracao_centro import ConfiguracaoCentro
from models.horario_turma import HorarioTurma
from models.turma import Turma
from models.alerta_utilizador import AlertaUtilizador

from routes.alunos import alunos_bp
from routes.frequencias import frequencias_bp
from routes.notas import notas_bp
from routes.turma import turma_bp, obter_atribuicao_salas_dia
from routes.testes import testes_bp
from routes.calendario import calendario_bp
from routes.admins import admins_bp
from routes.configuracoes import configuracoes_bp
from routes.horarios import horarios_bp

app = Flask(__name__)

import os

print("\nAPP.PY EM USO:")
print(os.path.abspath(__file__))

print("\nPASTA TEMPLATES:")
print(os.path.abspath("templates"))

app.config.from_object(Config)

db.init_app(app)

@app.context_processor
def inject_configuracao():

    configuracao = ConfiguracaoCentro.query.first()

    alerta_testes_semana = session.pop(
        "alerta_testes_semana",
        False
    )

    return dict(
        configuracao_global=configuracao,
        alerta_testes_semana=alerta_testes_semana
    )

app.register_blueprint(alunos_bp)
app.register_blueprint(frequencias_bp)
app.register_blueprint(notas_bp)
app.register_blueprint(turma_bp)
app.register_blueprint(testes_bp)
app.register_blueprint(calendario_bp)
app.register_blueprint(admins_bp)
app.register_blueprint(configuracoes_bp)
app.register_blueprint(horarios_bp)

def verificar_alerta_testes_semana(utilizador_id):

    hoje = datetime.now().date()

    # Segunda=0, terça=1, quarta=2, quinta=3.
    # Sexta-feira e fim de semana não apresentam o alerta.
    if hoje.weekday() > 3:
        return False

    inicio_semana = (
        hoje - timedelta(days=hoje.weekday())
    )

    fim_semana = inicio_semana + timedelta(days=4)

    testes = Teste.query.all()

    existe_teste = False

    for teste in testes:

        try:
            # Os testes do Centro estão guardados em YYYY-MM-DD.
            data_teste = datetime.strptime(
                teste.data_teste,
                "%Y-%m-%d"
            ).date()

        except (TypeError, ValueError):
            continue

        if inicio_semana <= data_teste <= fim_semana:
            existe_teste = True
            break

    if not existe_teste:
        return False

    data_alerta = hoje.strftime("%Y-%m-%d")

    ja_mostrado = AlertaUtilizador.query.filter_by(
        utilizador_id=utilizador_id,
        tipo="testes_semana",
        data=data_alerta
    ).first()

    if ja_mostrado:
        return False

    db.session.add(
        AlertaUtilizador(
            utilizador_id=utilizador_id,
            tipo="testes_semana",
            data=data_alerta
        )
    )

    db.session.commit()

    return True


def e_admin_geral():
    return session.get("perfil") == "administrador_geral"


def e_admin():
    return session.get("perfil") in [
        "administrador_geral",
        "administrador"
    ]


def e_colaborador():
    return session.get("perfil") == "colaborador"

with app.app_context():

    db.create_all()

    # ------------------------------------------------------------------
    # MIGRAÇÃO LEVE: garante que colunas novas existem em bases de dados
    # já criadas anteriormente (db.create_all() não altera tabelas já
    # existentes, apenas cria as que faltam).
    # ------------------------------------------------------------------
    try:
        from sqlalchemy import inspect, text

        inspetor = inspect(db.engine)
        colunas_turmas = [
            coluna["name"] for coluna in inspetor.get_columns("turmas")
        ]

        with db.engine.connect() as conexao:

            if "escola" not in colunas_turmas:
                conexao.execute(
                    text("ALTER TABLE turmas ADD COLUMN escola VARCHAR(150)")
                )

            if "diretor_turma" not in colunas_turmas:
                conexao.execute(
                    text("ALTER TABLE turmas ADD COLUMN diretor_turma VARCHAR(150)")
                )

            if "disciplinas" not in colunas_turmas:
                conexao.execute(
                    text("ALTER TABLE turmas ADD COLUMN disciplinas TEXT")
                )

            # ----------------------------------------------------------
            # MIGRAÇÃO DAS NOVAS COLUNAS DE FREQUÊNCIAS
            # ----------------------------------------------------------
            colunas_frequencias = [
                coluna["name"]
                for coluna in inspetor.get_columns("frequencias")
            ]

            if "tipo_registo" not in colunas_frequencias:
                conexao.execute(
                    text("ALTER TABLE frequencias ADD COLUMN tipo_registo VARCHAR(30)")
                )

            if "hora_inicio_estudo" not in colunas_frequencias:
                conexao.execute(
                    text("ALTER TABLE frequencias ADD COLUMN hora_inicio_estudo VARCHAR(10)")
                )

            if "tipo_saida" not in colunas_frequencias:
                conexao.execute(
                    text("ALTER TABLE frequencias ADD COLUMN tipo_saida VARCHAR(30)")
                )

            # Reaproveita disciplinas já existentes nos horários para
            # preencher a nova seleção de disciplinas das turmas sem
            # perder dados históricos.
            turmas_sem_disciplinas = conexao.execute(
                text("SELECT id, escola, nome FROM turmas WHERE disciplinas IS NULL OR TRIM(disciplinas) = ''")
            ).fetchall()

            for turma_id, escola_turma, nome_turma in turmas_sem_disciplinas:
                linhas = conexao.execute(
                    text("SELECT DISTINCT disciplina FROM horarios_turma WHERE centro_escolar = :escola AND turma = :turma AND disciplina IS NOT NULL AND TRIM(disciplina) <> ''"),
                    {"escola": escola_turma, "turma": nome_turma}
                ).fetchall()

                disciplinas_existentes = [linha[0].strip() for linha in linhas if linha[0] and linha[0].strip()]

                if disciplinas_existentes:
                    import json
                    conexao.execute(
                        text("UPDATE turmas SET disciplinas = :disciplinas WHERE id = :id"),
                        {"disciplinas": json.dumps(disciplinas_existentes, ensure_ascii=False), "id": turma_id}
                    )

            conexao.commit()

    except Exception as e:
        import sys
        print(f"[AVISO] Migração de 'turmas' não foi concluída: {e}", file=sys.stderr)

    configuracao = ConfiguracaoCentro.query.first()

    if not configuracao:

        configuracao = ConfiguracaoCentro()

        db.session.add(configuracao)

        db.session.commit()

    # =====================================
    # NECESSIDADES PEDAGÓGICAS
    # =====================================

    necessidades_padrao = [

        "Dislexia",
        "Discalculia",
        "TDAH",
        "PEA (Autismo)",
        "Ansiedade Escolar",
        "Dificuldades de Leitura",
        "Dificuldades de Escrita",
        "Dificuldades de Concentração"

    ]

    for nome in necessidades_padrao:

        existe = Necessidade.query.filter_by(
            nome=nome
        ).first()

        if not existe:

            db.session.add(
                Necessidade(nome=nome)
            )

    # =====================================
    # OBJETIVOS PEDAGÓGICOS
    # =====================================

    objetivos_padrao = [

        "Melhorar Leitura",
        "Melhorar Escrita",
        "Melhorar Organização",
        "Preparação para Testes",
        "Preparação para Exames",
        "Apoio ao Estudo",
        "Recuperação de Aprendizagens"

    ]

    for nome in objetivos_padrao:

        existe = Objetivo.query.filter_by(
            nome=nome
        ).first()

        if not existe:

            db.session.add(
                Objetivo(nome=nome)
            )

    db.session.commit()

    # =====================================
    # UTILIZADOR ADMINISTRADOR
    # =====================================

    admin = Utilizador.query.filter_by(
        email="admin@centro.pt"
    ).first()

    if not admin:

        admin = Utilizador(
            nome="Administrador Geral",
            email="admin@centro.pt",
            perfil="administrador_geral"
        )

        admin.definir_password(
            "admin123"
        )

        db.session.add(admin)
        db.session.commit()


@app.route("/")
def inicio():

    if "utilizador_id" not in session:

        return redirect(
            url_for("login")
        )

    total_alunos = Aluno.query.count()

    alunos_ativos = Aluno.query.filter_by(
        ativo=True
    ).count()

    hoje = datetime.now().strftime("%d/%m/%Y")

    alunos_em_estudo = Frequencia.query.filter(
        Frequencia.data == hoje,
        Frequencia.hora_saida.is_(None),
        Frequencia.tipo_registo == "ESTUDO",
        db.or_(
            Frequencia.observacoes.is_(None),
            ~Frequencia.observacoes.startswith("[ANULADO]")
        )
    ).with_entities(
        Frequencia.aluno_id
    ).distinct().count()

    total_frequencias = Frequencia.query.count()

    total_notas = Nota.query.count()

    media_geral = 0

    notas = Nota.query.all()

    if notas:

        media_geral = round(
            sum(
                nota.nota
                for nota in notas
            ) / len(notas),
            2
        )

    atribuicao_salas_hoje = obter_atribuicao_salas_dia()

    return render_template(
        "dashboard.html",
        total_alunos=total_alunos,
        alunos_ativos=alunos_ativos,
        alunos_em_estudo=alunos_em_estudo,
        total_frequencias=total_frequencias,
        total_notas=total_notas,
        media_geral=media_geral,
        atribuicao_salas_hoje=atribuicao_salas_hoje
    )


@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form["email"]

        password = request.form["password"]

        utilizador = Utilizador.query.filter_by(
            email=email
        ).first()

        if (
            utilizador
            and utilizador.verificar_password(password)
        ):

            session["utilizador_id"] = utilizador.id
            session["nome"] = utilizador.nome
            session["perfil"] = utilizador.perfil

            session["alerta_testes_semana"] = (
                verificar_alerta_testes_semana(
                    utilizador.id
                )
            )

            return redirect(
                url_for("inicio")
            )

    return render_template(
        "login.html"
    )


@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("login")
    )


if __name__ == "__main__":

    print("\nROTAS REGISTADAS:\n")

    for rota in app.url_map.iter_rules():
        print(rota)

    app.run(
        debug=False
    )








