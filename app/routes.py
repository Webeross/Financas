from flask import Blueprint, request, jsonify, render_template, make_response, redirect, url_for
from sqlalchemy import func
from datetime import datetime
from .models import db, Conta, Categoria, Transacao, ContaAPagar

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
    resultado = db.session.query(
        Categoria.nome, 
        func.sum(Transacao.valor).label('total')
    ).join(Transacao).filter(Categoria.tipo == 'Despesa').group_by(Categoria.nome).all()
    
    labels = [linha.nome for linha in resultado]
    valores = [float(linha.total) for linha in resultado]
    
    return jsonify({"labels": labels, "valores": valores})


# Blueprint do Frontend
frontend = Blueprint('frontend', __name__)

@frontend.route('/')
def index():
    contas = Conta.query.all()
    categorias = Categoria.query.all()
    transacoes = Transacao.query.order_by(Transacao.data.desc()).limit(15).all()
    contas_a_pagar = ContaAPagar.query.order_by(ContaAPagar.dia_vencimento.asc()).all()
    
    total_saldo = sum(c.saldo_atual for c in contas)
    
    # Cálculos do mês atual para dar visibilidade imediata no Hero Card
    hoje = datetime.utcnow()
    transacoes_mes = Transacao.query.filter(
        func.extract('month', Transacao.data) == hoje.month,
        func.extract('year', Transacao.data) == hoje.year
    ).all()
    
    receitas_mes = sum(t.valor for t in transacoes_mes if t.categoria.tipo == 'Receita')
    despesas_mes = sum(t.valor for t in transacoes_mes if t.categoria.tipo == 'Despesa')
    total_fixas_pendentes = sum(cp.valor for cp in contas_a_pagar)
    saldo_previsto = total_saldo - total_fixas_pendentes
    
    return render_template('index.html', 
                           contas=contas, 
                           categorias=categorias, 
                           transacoes=transacoes,
                           contas_a_pagar=contas_a_pagar,
                           total_saldo=total_saldo,
                           receitas_mes=receitas_mes,
                           despesas_mes=despesas_mes,
                           total_fixas_pendentes=total_fixas_pendentes,
                           saldo_previsto=saldo_previsto)

@frontend.route('/frontend/contas', methods=['POST'])
def front_criar_conta():
    nome = request.form.get('nome')
    tipo = request.form.get('tipo')
    saldo_atual = float(request.form.get('saldo_atual', 0.0))
    
    nova_conta = Conta(nome=nome, tipo=tipo, saldo_atual=saldo_atual)
    db.session.add(nova_conta)
    db.session.commit()
    
    resposta = make_response()
    resposta.headers['HX-Refresh'] = 'true'
    return resposta

@frontend.route('/frontend/categorias', methods=['POST'])
def front_criar_categoria():
    nome = request.form.get('nome')
    tipo = request.form.get('tipo') # 'Despesa' ou 'Receita'
    if nome and tipo:
        nova_cat = Categoria(nome=nome, tipo=tipo)
        db.session.add(nova_cat)
        db.session.commit()
    
    resposta = make_response()
    resposta.headers['HX-Refresh'] = 'true'
    return resposta

@frontend.route('/frontend/transacoes', methods=['POST'])
def front_criar_transacao():
    conta_id = int(request.form.get('conta_id'))
    categoria_id = int(request.form.get('categoria_id'))
    valor = float(request.form.get('valor'))
    descricao = request.form.get('descricao')
    
    conta = Conta.query.get_or_404(conta_id)
    categoria = Categoria.query.get_or_404(categoria_id)
    
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
    
    resposta = make_response()
    resposta.headers['HX-Refresh'] = 'true'
    return resposta

@frontend.route('/frontend/transacoes/<int:transacao_id>', methods=['DELETE'])
def front_excluir_transacao(transacao_id):
    transacao = Transacao.query.get_or_404(transacao_id)
    conta = transacao.conta
    
    # Estorna o valor na conta correspondente antes de apagar
    if transacao.categoria.tipo == 'Despesa':
        conta.saldo_atual += transacao.valor
    else:
        conta.saldo_atual -= transacao.valor
        
    db.session.delete(transacao)
    db.session.commit()
    
    resposta = make_response()
    resposta.headers['HX-Refresh'] = 'true'
    return resposta

@frontend.route('/frontend/filtro/<int:categoria_id>')
def filtrar_por_categoria(categoria_id):
    categoria = Categoria.query.get_or_404(categoria_id)
    transacoes = Transacao.query.filter_by(categoria_id=categoria_id).order_by(Transacao.data.desc()).all()
    total = sum(t.valor for t in transacoes)
    
    return render_template('filtro_resultados.html', transacoes=transacoes, categoria=categoria, total=total)

@frontend.route('/frontend/contas-a-pagar', methods=['POST'])
def front_criar_conta_a_pagar():
    descricao = request.form.get('descricao')
    valor = float(request.form.get('valor'))
    dia_vencimento = int(request.form.get('dia_vencimento'))
    tipo = request.form.get('tipo')
    categoria_id = int(request.form.get('categoria_id'))
    
    nova_conta = ContaAPagar(
        descricao=descricao,
        valor=valor,
        dia_vencimento=dia_vencimento,
        tipo=tipo,
        categoria_id=categoria_id
    )
    
    if tipo == 'Parcelada':
        nova_conta.parcela_atual = int(request.form.get('parcela_atual', 1))
        nova_conta.total_parcelas = int(request.form.get('total_parcelas', 1))
        
    db.session.add(nova_conta)
    db.session.commit()
    
    return redirect(url_for('frontend.contas_fixas'))

@frontend.route('/frontend/contas-a-pagar/<int:id>/pagar', methods=['POST'])
def pagar_conta_fixa(id):
    conta_pagar = ContaAPagar.query.get_or_404(id)
    conta_bancaria_id = int(request.form.get('conta_id'))
    conta_bancaria = Conta.query.get_or_404(conta_bancaria_id)
    
    # 1. Desconta o saldo da conta escolhida
    conta_bancaria.saldo_atual -= conta_pagar.valor
    
    # 2. Registra no extrato como uma transação real
    desc_extrato = conta_pagar.descricao
    if conta_pagar.tipo == 'Parcelada':
        desc_extrato += f" ({conta_pagar.parcela_atual}/{conta_pagar.total_parcelas})"
        
    nova_transacao = Transacao(
        conta_id=conta_bancaria.id,
        categoria_id=conta_pagar.categoria_id,
        valor=conta_pagar.valor,
        descricao=desc_extrato
    )
    db.session.add(nova_transacao)
    
    # 3. Se for parcelada, avança a parcela ou remove se chegou na última
    if conta_pagar.tipo == 'Parcelada':
        if conta_pagar.parcela_atual >= conta_pagar.total_parcelas:
            db.session.delete(conta_pagar)
        else:
            conta_pagar.parcela_atual += 1
            
    db.session.commit()
    return redirect(url_for('frontend.contas_fixas'))

@frontend.route('/frontend/contas-a-pagar/<int:id>/excluir', methods=['POST'])
def excluir_conta_fixa(id):
    conta_pagar = ContaAPagar.query.get_or_404(id)
    db.session.delete(conta_pagar)
    db.session.commit()
    return redirect(url_for('frontend.contas_fixas'))

@frontend.route('/contas-fixas')
def contas_fixas():
    contas_a_pagar = ContaAPagar.query.order_by(ContaAPagar.dia_vencimento.asc()).all()
    categorias = Categoria.query.filter_by(tipo='Despesa').all()
    contas = Conta.query.all()
    total_fixas = sum(cp.valor for cp in contas_a_pagar)
    return render_template('contas_fixas.html', 
                           contas_a_pagar=contas_a_pagar, 
                           categorias=categorias, 
                           contas=contas,
                           total_fixas=total_fixas)