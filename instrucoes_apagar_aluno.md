# Correção: Apagar Aluno — routes/alunos.py

## Problema
`UPDATE frequencias SET aluno_id = NULL` → PostgreSQL bloqueia porque `aluno_id` é NOT NULL.

## Solução
Apagar manualmente os registos dependentes antes de apagar o aluno.

## Alteração a fazer em routes/alunos.py

### LOCALIZAR esta função:

```python
@alunos_bp.route("/alunos/apagar/<int:id>", methods=["POST"])
def apagar_aluno(id):
    aluno = Aluno.query.get_or_404(id)

    db.session.delete(aluno)
    db.session.commit()

    return redirect("/alunos")
```

### SUBSTITUIR por:

```python
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
```

## O que NÃO foi alterado
- Imports (Frequencia, Nota, Teste já existiam)
- Models (aluno.py, frequencia.py, nota.py, teste.py, horario_turma.py)
- Qualquer outra função ou rota
- Sem cascade, delete-orphan, ondelete ou migrations

## Ordem de eliminação (importante)
1. Frequências do aluno
2. Notas do aluno
3. Testes do aluno
4. O aluno em si
5. Commit único no final

## Teste obrigatório após aplicar
1. Criar aluno de teste
2. Adicionar nota, frequência e teste a esse aluno
3. Apagar o aluno
4. Verificar que desaparecem: aluno + nota + frequência + teste
5. Confirmar: sem erro 500
