from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    session
)

from werkzeug.utils import secure_filename

import os
from uuid import uuid4

from models import db
from models.configuracao_centro import ConfiguracaoCentro


configuracoes_bp = Blueprint(
    "configuracoes",
    __name__,
    url_prefix="/configuracoes"
)


EXTENSOES_LOGO_PERMITIDAS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def extensao_permitida(nome_ficheiro):

    return (
        "."
        in nome_ficheiro
        and nome_ficheiro.rsplit(
            ".",
            1
        )[1].lower()
        in EXTENSOES_LOGO_PERMITIDAS
    )

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session
)

from werkzeug.utils import secure_filename

from uuid import uuid4

from models import db
from models.configuracao_centro import ConfiguracaoCentro

import cloudinary.uploader

from utils.cloudinary_config import *


configuracoes_bp = Blueprint(
    "configuracoes",
    __name__,
    url_prefix="/configuracoes"
)


EXTENSOES_LOGO_PERMITIDAS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def extensao_permitida(nome_ficheiro):

    return (
        "."
        in nome_ficheiro
        and nome_ficheiro.rsplit(
            ".",
            1
        )[1].lower()
        in EXTENSOES_LOGO_PERMITIDAS
    )


@configuracoes_bp.route(
    "",
    methods=["GET", "POST"]
)
def configuracoes():

    if session.get("perfil") != "administrador_geral":

        return render_template(
            "acesso_negado.html"
        )

    configuracao = ConfiguracaoCentro.query.first()

    if not configuracao:

        configuracao = ConfiguracaoCentro()

        db.session.add(configuracao)
        db.session.commit()

    if request.method == "POST":

        configuracao.nome_centro = request.form.get(
            "nome_centro",
            ""
        )

        configuracao.morada = request.form.get(
            "morada",
            ""
        )

        configuracao.codigo_postal = request.form.get(
            "codigo_postal",
            ""
        )

        configuracao.telefone = request.form.get(
            "telefone",
            ""
        )

        configuracao.whatsapp = request.form.get(
            "whatsapp",
            ""
        )

        configuracao.email = request.form.get(
            "email",
            ""
        )

        ficheiro_logo = request.files.get(
            "logo"
        )

        if (
            ficheiro_logo
            and ficheiro_logo.filename
            and extensao_permitida(
                ficheiro_logo.filename
            )
        ):

            nome_original = secure_filename(
                ficheiro_logo.filename
            )

            extensao = nome_original.rsplit(
                ".",
                1
            )[1].lower()

            public_id = (
                f"centros/default/logos/"
                f"logo_{uuid4().hex}"
            )

            resultado = (
                cloudinary.uploader.upload(
                    ficheiro_logo,
                    folder="centros/default/logos",
                    public_id=f"logo_{uuid4().hex}",
                    overwrite=True,
                    resource_type="image"
                )
            )

            configuracao.logo = (
                resultado["secure_url"]
            )

        db.session.commit()

        return redirect(
            "/configuracoes"
        )

    return render_template(
        "configuracoes.html",
        configuracao=configuracao
    )