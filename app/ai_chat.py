import os
from datetime import datetime
from sqlalchemy import func
from google import genai
from google.genai import types
from .models import db, Conta, Categoria, Transacao, ContaAPagar

def montar_contexto_financeiro() -> str:
    """Gera um resumo compacto e atualizado do banco SQLite para o System Prompt."""
    contas = Conta.query.all()
    contas_fixas = ContaAPagar.query.order_by(ContaAPagar.dia_vencimento.asc()).all()
    ultimas_transacoes = Transacao.query.order_by(Transacao.data.desc()).limit(50).all()
    
    # Soma por categoria
    resumo_categorias = db.session.query(
        Categoria.nome, Categoria.tipo, func.sum(Transacao.valor).label('total')
    ).join(Transacao).group_by(Categoria.id).all()

    linhas_contas = "\n".join([f"- {c.nome} ({c.tipo}): R$ {c.saldo_atual:.2f}" for c in contas])
    linhas_fixas = "\n".join([
        f"- Dia {cf.dia_vencimento}: {cf.descricao} | R$ {cf.valor:.2f} ({cf.tipo} {f'{cf.parcela_atual}/{cf.total_parcelas}' if cf.tipo == 'Parcelada' else ''})"
        for cf in contas_fixas
    ])
    linhas_cat = "\n".join([f"- {r.nome} ({r.tipo}): R$ {r.total:.2f}" for r in resumo_categorias])
    linhas_tx = "\n".join([
        f"- [{t.data.strftime('%d/%m/%Y')}] {t.descricao}: R$ {t.valor:.2f} ({t.categoria.tipo} - {t.categoria.nome} via {t.conta.nome})"
        for t in ultimas_transacoes
    ])

    return f"""
    DATA ATUAL: {datetime.now().strftime('%d/%m/%Y')}
    
    SALDOS EM CONTAS:
    {linhas_contas or 'Nenhuma conta cadastrada.'}
    
    COMPROMISSOS FIXOS E PARCELADOS (A PAGAR):
    {linhas_fixas or 'Nenhuma conta fixa cadastrada.'}
    
    ACUMULADO POR CATEGORIA:
    {linhas_cat or 'Sem dados por categoria.'}
    
    ÚLTIMAS 50 TRANSAÇÕES:
    {linhas_tx or 'Sem transações recentes.'}
    """

def responder_chat_financeiro(mensagem_usuario: str, historico: list) -> str:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    contexto_db = montar_contexto_financeiro()
    
    instrucao_sistema = f"""
    Você é o consultor financeiro pessoal do Eduardo dentro do app 'Finanças pae'.
    Responda de forma direta, amigável, analítica e prática em português.
    Use formatação Markdown limpa (negrito para valores, listas curtas).
    Sempre baseie suas respostas, cálculos e previsões EXCLUSIVAMENTE nos dados reais abaixo:
    
    {contexto_db}
    """
    
    # Converte o histórico simples da sessão para o formato do Gemini
    contents = []
    for msg in historico:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["text"])]
            )
        )
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=mensagem_usuario)]))

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=instrucao_sistema,
            temperature=0.3,
        )
    )
    return response.text