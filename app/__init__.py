import os
from flask import Flask
from .models import db, Categoria

def create_app():
    app = Flask(__name__)

    app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'chave_padrao_insegura_dev')
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'financas.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()

        if not Categoria.query.first():
            db.session.add_all([
                Categoria(nome='Alimentação', tipo='Despesa'),
                Categoria(nome='Despesas da Muffin', tipo='Despesa'),
                Categoria(nome='Despesas da Casa', tipo='Despesa'),
                Categoria(nome='Financiamento', tipo='Despesa'),
                Categoria(nome='Manutenção Peugeot 207', tipo='Despesa'),
                Categoria(nome='Rendimentos', tipo='Receita'),
                Categoria(nome='Salário', tipo='Receita'),
                Categoria(nome='Vendas', tipo='Receita'),
                
            ])
            db.session.commit()
        
    from .routes import api, frontend
    app.register_blueprint(api, url_prefix='/api')
    app.register_blueprint(frontend)
        
    return app