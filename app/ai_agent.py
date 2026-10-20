import os
from datetime import datetime
from sqlalchemy import func
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from .models import db, Conta, Categoria, Transacao, ContaAPagar

# Modelo atualizado exigido pela API para novas chaves
MODELO_GEMINI = "gemini-3.8-flash"

# ==========================================
# 1. AGENTE EXTRATOR DE PDF (Pydantic Schema)
# ==========================================
class TransacaoExtraida(BaseModel):
    data: str = Field(description="Data da transação no formato YYYY-MM-DD")
    descricao: str = Field(description="Nome limpo e legível do estabelecimento ou pessoa")
    valor: float = Field(description="Valor absoluto (sempre positivo) da transação")
    tipo: str = Field(description="'Despesa' para saídas/débitos ou 'Receita' para entradas/créditos")
    categoria_id: int = Field(description="ID da categoria mais adequada conforme a lista fornecida")

class ExtratoProcessado(BaseModel):
    transacoes: list[TransacaoExtraida]


def analisar_extrato_pdf(pdf_bytes: bytes, categorias_db: list) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("A variável GEMINI_API_KEY não está configurada no ambiente.")

    client = genai.Client(api_key=api_key)
    
    if categorias_db:
        mapa_categorias = "\n".join(
            [f"- ID {c.id}: {c.nome} (Tipo: {c.tipo})" for c in categorias_db]
        )
    else:
        mapa_categorias = "- ID 1: Geral (Tipo: Despesa)"
    
    prompt = f"""
    Você é um assistente contábil analisando um extrato bancário ou fatura em PDF.
    Extraia todas as movimentações financeiras reais (débitos, pagamentos, pix enviados/recebidos, compras).
    
    REGRAS IMPORTANTES:
    1. Ignore linhas de 'Saldo Anterior', 'Saldo do Dia', 'Total da Fatura' ou rendimentos automáticos de centavos.
    2. Limpe a descrição (ex: 'COMPRA ELO RESTAURANTE X' vira 'Restaurante X').
    3. O campo 'valor' deve ser sempre um número positivo (float).
    4. Classifique cada transação usando OBRIGATORIAMENTE um dos IDs de categoria abaixo (respeitando se é Despesa ou Receita):
    
    CATEGORIAS DISPONÍVEIS NO SISTEMA:
    {mapa_categorias}
    """

    response = client.models.generate_content(
        model=MODELO_GEMINI,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type='application/pdf'),
            prompt
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ExtratoProcessado,
            temperature=0.1
        ),
    )
    
    return ExtratoProcessado.model_validate_json(response.text).model_dump()


# ==========================================
# 2. AGENTE CONSULTOR FINANCEIRO (Chat)
# ==========================================
def montar_contexto_financeiro() -> str:
    contas = Conta.query.all()
    contas_fixas = ContaAPagar.query.order_by(ContaAPagar.dia_vencimento.asc()).all()
    ultimas_transacoes = Transacao.query.order_by(Transacao.data.desc()).limit(50).all()
    
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
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "⚠️ A chave GEMINI_API_KEY não foi encontrada. Verifique o seu arquivo .env e reinicie o container."

    client = genai.Client(api_key=api_key)
    contexto_db = montar_contexto_financeiro()
    
    instrucao_sistema = f"""
    Você é o consultor financeiro pessoal do Eduardo dentro do app 'Finanças pae'.
    Responda de forma direta, amigável, analítica e prática em português.
    Evite tabelas complexas; prefira listas curtas e valores importantes destacados.
    Sempre baseie suas respostas, cálculos e previsões EXCLUSIVAMENTE nos dados reais abaixo:
    
    {contexto_db}
    """
    
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
        model=MODELO_GEMINI,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=instrucao_sistema,
            temperature=0.3,
        )
    )
    return response.text