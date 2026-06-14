from models import db
from werkzeug.security import generate_password_hash, check_password_hash


class Utilizador(db.Model):
    __tablename__ = "utilizadores"

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password_hash = db.Column(db.String(255), nullable=False)

    perfil = db.Column(db.String(30), nullable=False)

    ativo = db.Column(db.Boolean, default=True)

    def definir_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verificar_password(self, password):
        return check_password_hash(self.password_hash, password)