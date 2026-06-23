# PATCH: routes/alunos.py
# Função a substituir: apagar_aluno(id)
#
# ANTES:
#
# @alunos_bp.route("/alunos/apagar/<int:id>", methods=["POST"])
# def apagar_aluno(id):
#     aluno = Aluno.query.get_or_404(id)
#     db.session.delete(aluno)
#     db.session.commit()
#     return redirect("/alunos")
#
# DEPOIS (código correto):

@alunos_bp.route("/alunos/apagar/<int:id>", methods=["POST"])
def apagar_aluno(id):
    aluno = Aluno.query.get_or_404(id)

    Frequencia.query.filter_by(
        aluno_id=id
    ).delete(synchronize_session=False)

    Nota.query.filter_by(
        aluno_id=id
    ).delete(synchronize_session=False)

    Teste.query.filter_by(
        aluno_id=id
    ).delete(synchronize_session=False)

    db.session.delete(aluno)

    db.session.commit()

    return redirect("/alunos")
