from flask import Blueprint, request, jsonify, render_template, make_response
from sqlalchemy import func
from .models import db, Conta, Categoria, Transacao

# Blueprint da API JSON
api = Blueprint('api', __name__)

@api.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "message": "API de finanças operante!"})

@api.route('/contas', methods=['POST'])
def criar_conta():
    dados = request.get_json()
    nova_conta = Conta(
        nome=dados['nome'], 
        tipo=dados['tipo'], 
        saldo_atual=dados.get('saldo_atual', 0.0)
    )
    db.session.add(nova_conta)
    db.session.commit()
    return jsonify({"message": "Conta criada com sucesso!", "id": nova_conta.id}), 201

@api.route('/contas', methods=['GET'])
def listar_contas():
    contas = Conta.query.all()
    resultado = [
        {"id": c.id, "nome": c.nome, "tipo": c.tipo, "saldo": c.saldo_atual} 
        for c in contas
    ]
    return jsonify(resultado)

@api.route('/estatisticas/despesas', methods=['GET'])
def estatisticas_despesas():
    # Junta as transações e categorias, filtra só despesas e soma os valores
    resultado = db.session.query(
        Categoria.nome, 
        func.sum(Transacao.valor).label('total')
    ).join(Transacao).filter(Categoria.tipo == 'Despesa').group_by(Categoria.nome).all()
    
    labels = [linha.nome for linha in resultado]
    valores = [float(linha.total) for linha in resultado]
    
    return jsonify({"labels": labels, "valores": valores})

# Blueprint do Frontend
frontend = Blueprint('frontend', __name__)

# Rota principal (MANTEMOS APENAS ESTA VERSÃO COMPLETA)
@frontend.route('/')
def index():
    contas = Conta.query.all()
    categorias = Categoria.query.all()
    # Puxa as últimas 10 transações
    transacoes = Transacao.query.order_by(Transacao.data.desc()).limit(10).all()
    
    total_saldo = sum(c.saldo_atual for c in contas)
    
    return render_template('index.html', 
                           contas=contas, 
                           categorias=categorias, 
                           transacoes=transacoes, 
                           total_saldo=total_saldo)

@frontend.route('/frontend/contas', methods=['POST'])
def front_criar_conta():
    # Captura os dados enviados pelo formulário HTML
    nome = request.form.get('nome')
    tipo = request.form.get('tipo')
    saldo_atual = float(request.form.get('saldo_atual', 0.0))
    
    nova_conta = Conta(nome=nome, tipo=tipo, saldo_atual=saldo_atual)
    db.session.add(nova_conta)
    db.session.commit()
    
    return render_template('conta_item.html', conta=nova_conta)

@frontend.route('/frontend/transacoes', methods=['POST'])
def front_criar_transacao():
    conta_id = int(request.form.get('conta_id'))
    categoria_id = int(request.form.get('categoria_id'))
    valor = float(request.form.get('valor'))
    descricao = request.form.get('descricao')
    
    conta = Conta.query.get(conta_id)
    categoria = Categoria.query.get(categoria_id)
    
    # Atualiza o saldo da conta dinamicamente
    if categoria.tipo == 'Despesa':
        conta.saldo_atual -= valor
    else:
        conta.saldo_atual += valor
        
    nova_transacao = Transacao(
        conta_id=conta.id, 
        categoria_id=categoria.id, 
        valor=valor, 
        descricao=descricao
    )
    db.session.add(nova_transacao)
    db.session.commit()
    
    # O HX-Refresh instrui o navegador a atualizar os saldos na tela
    resposta = make_response()
    resposta.headers['HX-Refresh'] = 'true'
    return resposta