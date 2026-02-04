from flask import Flask, request, redirect, url_for, render_template_string
import psycopg2
from datetime import datetime
import os

app = Flask(__name__)

# --- CONFIGURAÇÃO DO BANCO POSTGRESQL (RENDER) ---
# O Render fornece a URL automaticamente pela variável DATABASE_URL
DB_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    # Conecta ao PostgreSQL usando a URL do Render
    conn = psycopg2.connect(DB_URL)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS retiradas (
            id SERIAL PRIMARY KEY,
            item TEXT NOT NULL,
            quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
            usuario TEXT NOT NULL,
            destino TEXT NOT NULL,
            data_hora TEXT NOT NULL
        )
    ''')
    conn.commit()
    c.close()
    conn.close()

# Inicializa o banco (Postgres) ao carregar o app
try:
    init_db()
except Exception as e:
    print(f"Erro ao inicializar banco: {e}")

# ------------------ CONFIGURAÇÕES ------------------
ITENS_VALIDOS = {'1': 'Palete', '2': 'Stretch Filme', '3': 'Cantoneira'}
DESTINOS = ['CWB', 'ITJ', 'POA', 'VIX', 'USO INTERNO']

# ------------------ ROTAS ------------------
@app.route('/', methods=['GET', 'POST'])
def leitura():
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        if codigo in ITENS_VALIDOS:
            return redirect(url_for('registrar', item=codigo))
        return render_template_string(TEMPLATE_ERRO)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT item, SUM(quantidade) FROM retiradas GROUP BY item')
    resumo = c.fetchall()
    c.close()
    conn.close()

    resumo_dict = {item: 0 for item in ITENS_VALIDOS.values()}
    for item, qtd in resumo:
        resumo_dict[item] = qtd
    resumo_list = [(item, resumo_dict[item]) for item in ITENS_VALIDOS.values()]

    return render_template_string(TEMPLATE_LEITURA, resumo=resumo_list, itens_validos=ITENS_VALIDOS)

@app.route('/registrar/<item>', methods=['GET', 'POST'])
def registrar(item):
    if item not in ITENS_VALIDOS:
        return redirect(url_for('leitura'))

    if request.method == 'POST':
        usuario = request.form.get('usuario')
        quantidade = request.form.get('quantidade')
        destino = request.form.get('destino')

        if not usuario or quantidade is None or destino not in DESTINOS:
            return redirect(url_for('registrar', item=item))

        quantidade = int(quantidade)
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            'INSERT INTO retiradas (item, quantidade, usuario, destino, data_hora) VALUES (%s, %s, %s, %s, %s)',
            (ITENS_VALIDOS[item], quantidade, usuario, destino, data_hora)
        )
        conn.commit()
        c.close()
        conn.close()
        return redirect(url_for('sucesso'))

    return render_template_string(TEMPLATE_REGISTRO, item_nome=ITENS_VALIDOS[item], destinos=DESTINOS)

@app.route('/sucesso')
def sucesso():
    return render_template_string(TEMPLATE_SUCESSO)

@app.route('/historico')
def historico():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('SELECT id, item, quantidade, usuario, destino, data_hora FROM retiradas ORDER BY id DESC')
    dados = c.fetchall()
    c.close()
    conn.close()
    return render_template_string(TEMPLATE_HISTORICO, dados=dados)

@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM retiradas WHERE id = %s', (id,))
    conn.commit()
    c.close()
    conn.close()
    return redirect(url_for('historico'))

# --- OS TEMPLATES PERMANECEM OS MESMOS DA VERSÃO ROXA ANTERIOR ---
TEMPLATE_LEITURA = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Controle de Saída</title>
<style>
body { margin:0; font-family: Arial,sans-serif; background-color: #f4f4f4; }
.container { background: rgba(88,0,88,0.9); color:white; width:90%; max-width:500px; margin:50px auto; padding:30px; border-radius:20px; text-align:center; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
input, button { width:100%; padding:12px; margin-top:10px; border-radius:8px; border:none;}
button { background:#fff; color:#580058; font-weight:bold; cursor:pointer;}
.resumo { margin-top:30px; text-align:center; color:#580058; }
.resumo table { border-collapse: collapse; margin: 0 auto; background:white; color:black; width:100%;}
.resumo th, .resumo td { border:1px solid #580058; padding:10px; text-align:center; }
.itens { text-align:center; margin-bottom:20px; }
.itens ul { list-style:none; padding:0; font-weight:bold; }
.resumo a { display:inline-block; margin-top:15px; color:white; font-weight:bold; text-decoration:none; background:#580058; padding: 10px; border-radius: 8px;}
</style>
</head>
<body>
<div class="container">
<h2>Controle de Saída (Postgres)</h2>
<div class="itens">
<strong>Materiais:</strong>
<ul>{% for codigo, nome in itens_validos.items() %}<li>{{ codigo }} → {{ nome }}</li>{% endfor %}</ul>
</div>
<form method="post"><input name="codigo" autofocus placeholder="Bipe o código" required><button>Confirmar</button></form>
<div class="resumo"><h3 style="color:white;">Resumo Total:</h3>
<table><tr><th>Item</th><th>Total</th></tr>
{% for r in resumo %}<tr><td>{{ r[0] }}</td><td>{{ r[1] }}</td></tr>{% endfor %}
</table><a href="/historico">Ver histórico</a></div></div>
</body></html>
'''

TEMPLATE_REGISTRO = '''
<!doctype html>
<html><head><meta charset="utf-8"><title>Registrar</title></head>
<body><h2>Item: {{ item_nome }}</h2>
<form method="post">
<input name="usuario" placeholder="Nome" required><br><br>
<input name="quantidade" type="number" min="0" required><br><br>
<select name="destino" required>{% for d in destinos %}<option value="{{ d }}">{{ d }}</option>{% endfor %}</select><br><br>
<button>Registrar saída</button></form>
<a href="/">Voltar</a></body></html>
'''

TEMPLATE_SUCESSO = '''
<!doctype html>
<html><body style="text-align:center; font-family:sans-serif; padding-top:50px;">
<h2>✅ Salvo no Banco Permanente!</h2>
<a href="/">Voltar</a> | <a href="/historico">Histórico</a>
</body></html>
'''

TEMPLATE_HISTORICO = '''
<!doctype html>
<html><head><meta charset="utf-8"><style>table { border-collapse: collapse; width: 100%; } th, td { border:1px solid black; padding:8px; text-align:center; }</style></head>
<body><h2>Histórico Permanente</h2>
<table><tr><th>Item</th><th>Qtd</th><th>Usuário</th><th>Destino</th><th>Data</th><th>Ações</th></tr>
{% for d in dados %}<tr><td>{{ d[1] }}</td><td>{{ d[2] }}</td><td>{{ d[3] }}</td><td>{{ d[4] }}</td><td>{{ d[5] }}</td>
<td><form method="post" action="/deletar/{{ d[0] }}"><button type="submit">Excluir</button></form></td></tr>{% endfor %}
</table><br><a href="/">Voltar</a></body></html>
'''

TEMPLATE_ERRO = '<html><body><h2>❌ Inválido</h2><a href="/">Voltar</a></body></html>'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
