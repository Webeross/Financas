from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False) # Ex: Nubank, XP Investimentos
    tipo = db.Column(db.String(50), nullable=False)  # Ex: Corrente, Investimento, Carteira
    saldo_atual = db.Column(db.Float, default=0.0)
    transacoes = db.relationship('Transacao', backref='conta', lazy=True)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False) 
    tipo = db.Column(db.String(20), nullable=False)  
    
    # --- A LINHA QUE FALTAVA ESTÁ AQUI ABAIXO ---
    # Ela cria a propriedade 'categoria' dentro de cada transação automaticamente
    transacoes = db.relationship('Transacao', backref='categoria', lazy=True)

class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    descricao = db.Column(db.String(255))
    data = db.Column(db.DateTime, default=datetime.utcnow)

class ContaAPagar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    dia_vencimento = db.Column(db.Integer, nullable=False)
    tipo = db.Column(db.String(20), nullable=False) # 'Fixa' ou 'Parcelada'
    parcela_atual = db.Column(db.Integer, default=1, nullable=True)
    total_parcelas = db.Column(db.Integer, nullable=True)
    
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    categoria = db.relationship('Categoria')