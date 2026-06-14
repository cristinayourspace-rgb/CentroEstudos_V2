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

from routes.alunos import alunos_bp
from routes.frequencias import frequencias_bp
from routes.notas import notas_bp
from routes.turma import turma_bp
from routes.testes import testes_bp
from routes.calendario import calendario_bp
from routes.admins import admins_bp
from routes.configuracoes import configuracoes_bp

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

    return dict(
        configuracao_global=configuracao
    )

app.register_blueprint(alunos_bp)
app.register_blueprint(frequencias_bp)
app.register_blueprint(notas_bp)
app.register_blueprint(turma_bp)
app.register_blueprint(testes_bp)
app.register_blueprint(calendario_bp)
app.register_blueprint(admins_bp)
app.register_blueprint(configuracoes_bp)
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

    alunos_em_estudo = Frequencia.query.filter_by(
        hora_saida=None
    ).count()

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

    return render_template(
        "dashboard.html",
        total_alunos=total_alunos,
        alunos_ativos=alunos_ativos,
        alunos_em_estudo=alunos_em_estudo,
        total_frequencias=total_frequencias,
        total_notas=total_notas,
        media_geral=media_geral
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
        debug=True
    )






