import os
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from celery import Celery

app = Flask(__name__)

# --- Configuração para o Render ---
# Lê as URLs a partir das variáveis de ambiente injetadas pelo Render
DATABASE_URL = os.environ.get('DATABASE_URL')
REDIS_URL = os.environ.get('REDIS_URL')

# Altera a string de conexão do PostgreSQL para ser compatível com SQLAlchemy
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['CELERY_BROKER_URL'] = f"{REDIS_URL}/0"
app.config['CELERY_RESULT_BACKEND'] = f"{REDIS_URL}/0"

db = SQLAlchemy(app)
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)


# --- Modelo do Banco de Dados ---
class Mensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    texto = db.Column(db.Text, nullable=False)


# --- Rotas da API e da Página ---
@app.route('/')
def index():
    try:
        mensagens = Mensagem.query.order_by(Mensagem.id.desc()).all()
    except Exception:
        # Se a tabela ainda não existir, retorna uma lista vazia
        mensagens = []
    return render_template('index.html', mensagens=mensagens)


@app.route('/salvar-mensagem', methods=['POST'])
def salvar_mensagem():
    dados = request.json
    if not dados.get('titulo') or not dados.get('texto'):
        return jsonify({'status': 'erro', 'mensagem': 'Título e texto são obrigatórios.'}), 400
    
    nova_mensagem = Mensagem(titulo=dados['titulo'], texto=dados['texto'])
    db.session.add(nova_mensagem)
    db.session.commit()
    return jsonify({'status': 'sucesso', 'mensagem': 'Mensagem salva!'})


@app.route('/enviar-campanha', methods=['POST'])
def enviar_campanha():
    dados = request.json
    
    # Validação dos dados de entrada
    if not all(k in dados for k in ['numeros', 'id_mensagem', 'intervalo']):
        return jsonify({'status': 'erro', 'mensagem': 'Dados incompletos.'}), 400

    numeros = [n.strip() for n in dados['numeros'].split()]
    id_mensagem = dados['id_mensagem']
    intervalo = int(dados['intervalo'])

    if intervalo < 5:
        return jsonify({'status': 'erro', 'mensagem': 'O intervalo deve ser de no mínimo 5 segundos.'}), 400

    mensagem_obj = Mensagem.query.get(id_mensagem)
    if not mensagem_obj:
        return jsonify({'status': 'erro', 'mensagem': 'Mensagem não encontrada.'}), 404

    # Importa o worker e envia a tarefa para a fila do Celery
    from worker import enviar_para_lista
    enviar_para_lista.delay(numeros, mensagem_obj.texto, intervalo)
    
    return jsonify({'status': 'sucesso', 'mensagem': 'Campanha iniciada! O envio está ocorrendo em segundo plano.'})

# Comando para criar as tabelas no banco de dados (será executado pelo Render)
@app.cli.command("create-db")
def create_db():
    db.create_all()
    print("Banco de dados e tabelas criados.")