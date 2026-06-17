from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash,
)

from models import db
from models.utilizador import Utilizador


admins_bp = Blueprint(
    "admins",
    __name__,
    url_prefix="/admins"
)


@admins_bp.route("", methods=["GET", "POST"])
def listar_admins():

    if session.get("perfil") != "administrador_geral":

        return render_template(
            "acesso_negado.html"
        )

    if request.method == "POST":

        email = request.form["email"].strip()

        existente = Utilizador.query.filter_by(
            email=email
        ).first()

        if existente:

            flash("Já existe um utilizador com esse email.")
            return redirect("/admins")

        admin = Utilizador(
            nome=request.form["nome"],
            email=email,
            perfil=request.form["perfil"],
            ativo=True
        )

        admin.definir_password(
            request.form["password"]
        )

        db.session.add(admin)
        db.session.commit()

        flash("Utilizador criado com sucesso.")
        return redirect("/admins")

    admins = Utilizador.query.order_by(
        Utilizador.nome
    ).all()

    return render_template(
        "admins.html",
        admins=admins
    )


@admins_bp.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_admin(id):

    if session.get("perfil") != "administrador_geral":

        return render_template(
            "acesso_negado.html"
        )

    admin = Utilizador.query.get_or_404(id)

    if request.method == "POST":

        email = request.form["email"].strip()

        conflito = Utilizador.query.filter(
            Utilizador.email == email,
            Utilizador.id != id
        ).first()

        if conflito:

            flash("Já existe outro utilizador com esse email.")
            return redirect(f"/admins/editar/{id}")

        admin.nome = request.form["nome"]
        admin.email = email
        admin.perfil = request.form["perfil"]

        if request.form["password"].strip():

            admin.definir_password(
                request.form["password"]
            )

        db.session.commit()

        flash("Utilizador atualizado com sucesso.")
        return redirect("/admins")

    return render_template(
        "editar_admin.html",
        admin=admin
    )


@admins_bp.route("/apagar/<int:id>")
def apagar_admin(id):

    if session.get("perfil") != "administrador_geral":

        return render_template(
            "acesso_negado.html"
        )

    admin = Utilizador.query.get_or_404(id)

    if admin.perfil == "administrador_geral":

        total = Utilizador.query.filter_by(
            perfil="administrador_geral"
        ).count()

        if total <= 1:
            return redirect("/admins")

    db.session.delete(admin)
    db.session.commit()

    return redirect("/admins")