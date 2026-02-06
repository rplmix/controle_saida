# app_saida.py
from flask import Flask, request, redirect, url_for, render_template_string, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import io
import os

app = Flask(__name__)
DB = 'saida_materiais.db'

# ------------------ CONFIGURAÇÕES ------------------
ITENS_VALIDOS = {
    '1': 'Palete',
    '2': 'Stretch Filme',
    '3': 'Cantoneira'
}

DESTINOS = ['CWB', 'ITJ', 'POA', 'VIX', 'USO INTERNO']

# ------------------ BANCO ------------------
def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Tabela de saídas
        c.execute('''
            CREATE TABLE IF NOT EXISTS retiradas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
                usuario TEXT NOT NULL,
                destino TEXT NOT NULL,
                data_hora TEXT NOT NULL
            )
        ''')
        # Tabela de estoque para o balanço
        c.execute('''
            CREATE TABLE IF NOT EXISTS estoque (
                item TEXT PRIMARY KEY,
                quantidade_inicial INTEGER NOT NULL DEFAULT 0
            )
        ''')
        for nome in ITENS_VALIDOS.values():
            c.execute('INSERT OR IGNORE INTO estoque (item, quantidade_inicial) VALUES (?, ?)', (nome, 0))
        conn.commit()

# ------------------ ROTAS ------------------
@app.route('/', methods=['GET', 'POST'])
def leitura():
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        if codigo in ITENS_VALIDOS:
            return redirect(url_for('registrar', item=codigo))
        return render_template_string(TEMPLATE_ERRO)

    with sqlite3.connect(DB) as conn:
        resumo_saidas = conn.execute('SELECT item, SUM(quantidade) FROM retiradas GROUP BY item').fetchall()
        saidas_dict = {item: qtd for item, qtd in resumo_saidas}
        estoque_inicial = conn.execute('SELECT item, quantidade_inicial FROM estoque').fetchall()

    resumo_list = []
    for item_nome, inicial in estoque_inicial:
        saido = saidas_dict.get(item_nome, 0)
        saldo = inicial - saido
        resumo_list.append((item_nome, saido, saldo, inicial))

    return render_template_string(TEMPLATE_LEITURA, resumo=resumo_list, itens_validos=ITENS_VALIDOS)

@app.route('/balanco', methods=['GET', 'POST'])
def balanco():
    with sqlite3.connect(DB) as conn:
        if request.method == 'POST':
            for item_nome in ITENS_VALIDOS.values():
                valor = request.form.get(item_nome, 0)
                conn.execute('UPDATE estoque SET quantidade_inicial = ? WHERE item = ?', (int(valor), item_nome))
            conn.commit()
            return redirect(url_for('leitura'))
        estoque = conn.execute('SELECT item, quantidade_inicial FROM estoque').fetchall()
    return render_template_string(TEMPLATE_BALANCO, estoque=estoque)

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
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        with sqlite3.connect(DB) as conn:
            conn.execute('INSERT INTO retiradas (item, quantidade, usuario, destino, data_hora) VALUES (?, ?, ?, ?, ?)',
                (ITENS_VALIDOS[item], int(quantidade), usuario, destino, data_hora))
            conn.commit()
        return redirect(url_for('sucesso'))
    return render_template_string(TEMPLATE_REGISTRO, item_nome=ITENS_VALIDOS[item], destinos=DESTINOS)

@app.route('/sucesso')
def sucesso():
    return render_template_string(TEMPLATE_SUCESSO)

@app.route('/historico')
def historico():
    with sqlite3.connect(DB) as conn:
        dados = conn.execute('SELECT id, item, quantidade, usuario, destino, data_hora FROM retiradas ORDER BY id DESC').fetchall()
    return render_template_string(TEMPLATE_HISTORICO, dados=dados)

@app.route('/exportar')
def exportar():
    with sqlite3.connect(DB) as conn:
        df = pd.read_sql_query("SELECT item, quantidade, usuario, destino, data_hora FROM retiradas", conn)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Saídas')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"historico_{datetime.now().strftime('%Y%m%d')}.xlsx")

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    with sqlite3.connect(DB) as conn:
        if request.method == 'POST':
            usuario = request.form.get('usuario')
            quantidade = int(request.form.get('quantidade'))
            item = request.form.get('item')
            destino = request.form.get('destino')
            conn.execute('UPDATE retiradas SET item=?, quantidade=?, usuario=?, destino=? WHERE id=?', (item, quantidade, usuario, destino, id))
            conn.commit()
            return redirect(url_for('historico'))
        registro = conn.execute('SELECT item, quantidade, usuario, destino FROM retiradas WHERE id=?', (id,)).fetchone()
    return render_template_string(TEMPLATE_EDITAR, registro=registro, id=id, itens=ITENS_VALIDOS.values(), destinos=DESTINOS)

@app.route('/deletar/<int:id>', methods=['POST'])
def deletar(id):
    with sqlite3.connect(DB) as conn:
        conn.execute('DELETE FROM retiradas WHERE id=?', (id,))
        conn.commit()
    return redirect(url_for('historico'))

# ------------------ TEMPLATES ------------------
TEMPLATE_LEITURA = '''
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Controle de Saída</title>
<style>
body { margin:0; font-family: Arial,sans-serif; background: linear-gradient(rgba(255,255,255,0.85), rgba(255,255,255,0.85)), url('/static/notos_logo.png') no-repeat center center fixed; background-size: cover; }
.container { background: rgba(88,0,88,0.85); color:white; width:90%; max-width:500px; margin:50px auto; padding:30px; border-radius:20px; text-align:center; }
input, button { width:100%; padding:12px; margin-top:10px; border-radius:8px; border:none;}
button { background:#fff; color:#580058; font-weight:bold; cursor:pointer; }
.resumo { margin-top:30px; text-align:center; color:#580058; }
.resumo table { border-collapse: collapse; margin: 0 auto; background:white; color:black; width:100%; }
.resumo th, .resumo td { border:1px solid #580058; padding:10px; text-align:center; }
.itens { text-align:center; margin-bottom:20px; }
.itens ul { list-style:none; padding:0; font-weight:bold; }
.resumo a { display:inline-block; margin-top:15px; color:white; font-weight:bold; text-decoration:none; }
.btn-balanco { background:#ffcc00; color:#580058; padding:5px 10px; border-radius:5px; text-decoration:none; font-size:12px; font-weight:bold; display:block; margin: 10px auto; width: fit-content;}
</style>
</head>
<body>
<div class="container">
<h2>Controle de Saída</h2>
<div class="itens"><strong>Identificação dos Materiais:</strong><ul>{% for codigo, nome in itens_validos.items() %}<li>{{ codigo }} → {{ nome }}</li>{% endfor %}</ul></div>
<form method="post"><input name="codigo" autofocus placeholder="Bipe o código" required><button>Confirmar</button></form>
<div class="resumo">
<h3>Resumo de Estoque:</h3>
<table>
<tr><th>Item</th><th>Saído</th><th>Saldo</th></tr>
{% for nome, saido, saldo, inicial in resumo %}
<tr><td>{{ nome }}</td><td>{{ saido }}</td><td><b>{{ saldo }}</b></td></tr>
{% endfor %}
</table>
<a href="/balanco" class="btn-balanco">ATUALIZAR BALANÇO (ESTOQUE)</a>
<a href="/historico">Ver histórico completo</a>
</div></div>
</body></html>
'''

TEMPLATE_BALANCO = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Balanço</title>
<style>
body { font-family: Arial; text-align:center; padding-top:50px; background:#f4f4f4; }
.box { background:white; padding:20px; display:inline-block; border-radius:15px; box-shadow:0 0 10px rgba(0,0,0,0.1); }
input { padding:8px; margin:5px; border-radius:5px; border:1px solid #ccc; width:100px; }
button { background:#580058; color:white; padding:10px 20px; border:none; border-radius:5px; cursor:pointer; }
</style>
</head>
<body>
<div class="box">
    <h2>Ajustar Estoque Inicial</h2>
    <form method="post">
        {% for item, qtd in estoque %}
        <label>{{ item }}: </label><input type="number" name="{{ item }}" value="{{ qtd }}"><br>
        {% endfor %}
        <br><button type="submit">Salvar Balanço</button>
    </form>
    <br><a href="/">Voltar</a>
</div>
</body></html>
'''

TEMPLATE_REGISTRO = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Registrar Retirada</title>
<style>
body { margin:0; font-family: Arial,sans-serif; background: linear-gradient(rgba(255,255,255,0.85), rgba(255,255,255,0.85)); }
.container { background: rgba(88,0,88,0.85); color:white; width:90%; max-width:500px; margin:50px auto; padding:30px; border-radius:20px; text-align:center; }
input, select, button { width:100%; padding:12px; margin-top:10px; border-radius:8px; border:none; box-sizing: border-box;}
label { display: block; margin-top: 15px; text-align: left; font-weight: bold; }
button { background:#fff; color:#580058; font-weight:bold; cursor:pointer; margin-top: 25px;}
.voltar { display: block; margin-top: 20px; color: white; text-decoration: none; font-size: 0.9em;}
</style>
</head>
<body>
<div class="container">
    <h2>Registrar Saída</h2>
    <h3 style="background: white; color: #580058; padding: 10px; border-radius: 8px;">{{ item_nome }}</h3>
    <form method="post">
        <label>Quem está retirando?</label><input name="usuario" placeholder="Nome do usuário" required autofocus>
        <label>Quantidade:</label><input name="quantidade" type="number" min="1" value="1" required>
        <label>Destino:</label>
        <select name="destino" required>
            <option value="" disabled selected>Selecione o destino</option>
            {% for d in destinos %}<option value="{{ d }}">{{ d }}</option>{% endfor %}
        </select>
        <button type="submit">CONFIRMAR RETIRADA</button>
    </form>
    <a href="/" class="voltar">← Voltar</a>
</div>
</body></html>
'''

TEMPLATE_HISTORICO = '''
<!doctype html>
<html>
<head><meta charset="utf-8">
<title>Histórico</title>
<style>
body { font-family: Arial, sans-serif; padding: 20px; }
table { border-collapse: collapse; width: 100%; margin-top: 20px; }
th, td { border:1px solid #ccc; padding:10px; text-align:center; }
th { background-color: #580058; color: white; }
tr:nth-child(even) { background-color: #f2f2f2; }
.btn-excel { background-color: #1d6f42; color: white; padding: 10px 15px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block; margin-bottom: 20px; }
.btn-voltar { color: #580058; text-decoration: none; font-weight: bold; }
a { color: blue; text-decoration: none; font-size: 14px; }
.del-btn { color: red; border: none; background: none; cursor: pointer; font-size: 14px; padding: 0; }
</style>
</head>
<body>
<h2>Histórico de Retiradas</h2>
<a href="/exportar" class="btn-excel">📊 Exportar para Excel</a>
<br>
<table>
<tr><th>Item</th><th>Qtd</th><th>Usuário</th><th>Destino</th><th>Data</th><th>Ações</th></tr>
{% for d in dados %}
<tr>
<td>{{ d[1] }}</td><td>{{ d[2] }}</td><td>{{ d[3] }}</td><td>{{ d[4] }}</td><td>{{ d[5] }}</td>
<td>
    <a href="/editar/{{ d[0] }}">Editar</a> | 
    <form method="post" action="/deletar/{{ d[0] }}" style="display:inline;" onsubmit="return confirm('Tem certeza?');">
        <button type="submit" class="del-btn">Excluir</button>
    </form>
</td>
</tr>
{% endfor %}
</table>
<br><a href="/" class="btn-voltar">← Voltar</a>
</body></html>
'''

TEMPLATE_EDITAR = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Editar</title></head>
<body>
<h2>Editar Retirada</h2>
<form method="post">
<label>Item:</label>
<select name="item">
{% for i in itens %}<option value="{{ i }}" {% if i==registro[0] %}selected{% endif %}>{{ i }}</option>{% endfor %}
</select><br><br>
<label>Quantidade:</label><input name="quantidade" type="number" value="{{ registro[1] }}"><br><br>
<label>Usuário:</label><input name="usuario" value="{{ registro[2] }}"><br><br>
<label>Destino:</label>
<select name="destino">
{% for d in destinos %}<option value="{{ d }}" {% if d==registro[3] %}selected{% endif %}>{{ d }}</option>{% endfor %}
</select><br><br>
<button>Salvar</button>
</form>
<a href="/historico">Cancelar</a>
</body></html>
'''

TEMPLATE_SUCESSO = '''<!doctype html><html><body style="text-align:center; padding-top:50px; font-family:Arial;"><h2>Registrado! ✅</h2><a href="/">Nova retirada</a> | <a href="/historico">Histórico</a></body></html>'''
TEMPLATE_ERRO = '''<!doctype html><html><body style="text-align:center; padding-top:50px;"><h2>Código Inválido ❌</h2><a href="/">Voltar</a></body></html>'''

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
