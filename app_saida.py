# app_saida.py
from flask import Flask, request, redirect, url_for, render_template_string
import sqlite3
from datetime import datetime
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
        resumo = conn.execute('''
            SELECT item, SUM(quantidade) FROM retiradas GROUP BY item
        ''').fetchall()

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

        with sqlite3.connect(DB) as conn:
            conn.execute(
                'INSERT INTO retiradas (item, quantidade, usuario, destino, data_hora) VALUES (?, ?, ?, ?, ?)',
                (ITENS_VALIDOS[item], quantidade, usuario, destino, data_hora)
            )
            conn.commit()

        return redirect(url_for('sucesso'))

    return render_template_string(
        TEMPLATE_REGISTRO,
        item_nome=ITENS_VALIDOS[item],
        destinos=DESTINOS
    )

@app.route('/sucesso')
def sucesso():
    return render_template_string(TEMPLATE_SUCESSO)

@app.route('/historico')
def historico():
    with sqlite3.connect(DB) as conn:
        dados = conn.execute(
            'SELECT id, item, quantidade, usuario, destino, data_hora FROM retiradas ORDER BY id DESC'
        ).fetchall()
    return render_template_string(TEMPLATE_HISTORICO, dados=dados)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    with sqlite3.connect(DB) as conn:
        if request.method == 'POST':
            usuario = request.form.get('usuario')
            quantidade = int(request.form.get('quantidade'))
            item = request.form.get('item')
            destino = request.form.get('destino')

            conn.execute('''
                UPDATE retiradas
                SET item=?, quantidade=?, usuario=?, destino=?
                WHERE id=?
            ''', (item, quantidade, usuario, destino, id))
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
body {
  margin:0;
  font-family: Arial,sans-serif;
  background:
    linear-gradient(rgba(255,255,255,0.85), rgba(255,255,255,0.85)),
    url('/static/notos_logo.png') no-repeat center center fixed;
  background-size: cover;
}
.container {
  background: rgba(88,0,88,0.85);
  color:white;
  width:90%;
  max-width:500px;
  margin:50px auto;
  padding:30px;
  border-radius:20px;
  text-align:center;
}
input, button { width:100%; padding:12px; margin-top:10px; border-radius:8px; border:none;}
button { background:#fff; color:#580058; font-weight:bold; }
.resumo { margin-top:30px; text-align:center; color:#580058; }
.resumo table { border-collapse: collapse; margin: 0 auto; background:white; color:black; }
.resumo th, .resumo td { border:1px solid #580058; padding:10px; text-align:center; }
.itens { text-align:center; margin-bottom:20px; }
.itens ul { list-style:none; padding:0; font-weight:bold; }
.itens li { margin:5px 0; }
.resumo a { display:inline-block; margin-top:15px; color:white; font-weight:bold; text-decoration:none; }
.resumo a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="container">
<h2>Controle de Saída</h2>

<div class="itens">
<strong>Identificação dos Materiais:</strong>
<ul>
{% for codigo, nome in itens_validos.items() %}
<li>{{ codigo }} → {{ nome }}</li>
{% endfor %}
</ul>
</div>

<form method="post">
  <input name="codigo" autofocus placeholder="Bipe o código" required>
  <button>Confirmar</button>
</form>

<div class="resumo">
<h3>Resumo do que já saiu:</h3>
<table>
<tr><th>Item</th><th>Total Saído</th></tr>
{% for r in resumo %}
<tr>
  <td>{{ r[0] }}</td>
  <td>{{ r[1] }}</td>
</tr>
{% endfor %}
</table>
<a href="/historico">Ver histórico completo</a>
</div>
</div>
</body>
</html>
'''

TEMPLATE_REGISTRO = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Registrar Retirada</title></head>
<body>
<h2>Item: {{ item_nome }}</h2>
<form method="post">
<input name="usuario" placeholder="Nome de quem retirou" required><br><br>
<input name="quantidade" type="number" min="0" value="0" required><br><br>
<select name="destino" required>
{% for d in destinos %}
<option value="{{ d }}">{{ d }}</option>
{% endfor %}
</select><br><br>
<button>Registrar saída</button>
</form>
</body>
</html>
'''

TEMPLATE_SUCESSO = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Sucesso</title></head>
<body>
<h2>Retirada registrada com sucesso ✅</h2>
<a href="/">Nova retirada</a> | <a href="/historico">Ver histórico</a>
</body>
</html>
'''

TEMPLATE_HISTORICO = '''
<!doctype html>
<html>
<head><meta charset="utf-8">
<title>Histórico</title>
<style>
table { border-collapse: collapse; width: 100%; }
th, td { border:1px solid black; padding:5px; text-align:center; }
form { display:inline; }
button { padding:4px 8px; }
</style>
</head>
<body>
<h2>Histórico de Retiradas</h2>
<table>
<tr><th>Item</th><th>Qtd</th><th>Usuário</th><th>Destino</th><th>Data</th><th>Ações</th></tr>
{% for d in dados %}
<tr>
<td>{{ d[1] }}</td>
<td>{{ d[2] }}</td>
<td>{{ d[3] }}</td>
<td>{{ d[4] }}</td>
<td>{{ d[5] }}</td>
<td>
<a href="/editar/{{ d[0] }}">Editar</a>
<form method="post" action="/deletar/{{ d[0] }}" style="display:inline;">
<button type="submit">Excluir</button>
</form>
</td>
</tr>
{% endfor %}
</table>
<br>
<a href="/">Voltar</a>
</body>
</html>
'''

TEMPLATE_EDITAR = '''
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Editar Retirada</title></head>
<body>
<h2>Editar Retirada</h2>
<form method="post">
<label>Item:</label>
<select name="item" required>
{% for i in itens %}
<option value="{{ i }}" {% if i==registro[0] %}selected{% endif %}>{{ i }}</option>
{% endfor %}
</select><br><br>

<label>Quantidade:</label>
<input name="quantidade" type="number" min="0" value="{{ registro[1] }}" required><br><br>

<label>Usuário:</label>
<input name="usuario" value="{{ registro[2] }}" required><br><br>

<label>Destino:</label>
<select name="destino" required>
{% for d in destinos %}
<option value="{{ d }}" {% if d==registro[3] %}selected{% endif %}>{{ d }}</option>
{% endfor %}
</select><br><br>

<button>Salvar alterações</button>
</form>
<br>
<a href="/historico">Cancelar</a>
</body>
</html>
'''

TEMPLATE_ERRO = '''
<!doctype html>
<html><body>
<h2>Código inválido ❌</h2>
<a href="/">Voltar</a>
</body></html>
'''

# ------------------ START ------------------
if __name__ == '__main__':
    if not os.path.exists(DB):
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
