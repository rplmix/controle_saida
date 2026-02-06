import os
import sqlite3
import io
from datetime import datetime
import pandas as pd
from flask import Flask, request, redirect, url_for, render_template_string, send_file

app = Flask(__name__)

# CONFIGURAÇÃO DE CAMINHO PARA O RENDER
# Isso garante que o banco seja criado na pasta correta do servidor
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, 'saida_materiais.db')

# ------------------ CONFIGURAÇÕES ------------------
ITENS_VALIDOS = {'1': 'Palete', '2': 'Stretch Filme', '3': 'Cantoneira'}
DESTINOS = ['CWB', 'ITJ', 'POA', 'VIX', 'USO INTERNO']

# ------------------ BANCO DE DADOS (AUTO-CRIAÇÃO) ------------------
def init_db():
    with sqlite3.connect(DB) as conn:
        c = conn.cursor()
        # Cria tabela de retiradas
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
        # Cria tabela de estoque
        c.execute('''
            CREATE TABLE IF NOT EXISTS estoque (
                item TEXT PRIMARY KEY,
                quantidade_inicial INTEGER NOT NULL DEFAULT 0
            )
        ''')
        for nome in ITENS_VALIDOS.values():
            c.execute('INSERT OR IGNORE INTO estoque (item, quantidade_inicial) VALUES (?, ?)', (nome, 0))
        conn.commit()

# FORÇA A CRIAÇÃO DO BANCO ANTES DE QUALQUER ACESSO
init_db()

# ------------------ ROTAS ------------------
@app.route('/', methods=['GET', 'POST'])
def leitura():
    try:
        if request.method == 'POST':
            codigo = request.form.get('codigo')
            if codigo in ITENS_VALIDOS:
                return redirect(url_for('registrar', item=codigo))
            return render_template_string(TEMPLATE_ERRO)

        with sqlite3.connect(DB) as conn:
            resumo_saidas = conn.execute('SELECT item, SUM(quantidade) FROM retiradas GROUP BY item').fetchall()
            saidas_dict = {item: (qtd if qtd else 0) for item, qtd in resumo_saidas}
            estoque_inicial = conn.execute('SELECT item, quantidade_inicial FROM estoque').fetchall()

        resumo_list = []
        for item_nome, inicial in estoque_inicial:
            saido = saidas_dict.get(item_nome, 0)
            saldo = inicial - saido
            resumo_list.append((item_nome, saido, saldo, inicial))

        return render_template_string(TEMPLATE_LEITURA, resumo=resumo_list, itens_validos=ITENS_VALIDOS)
    except Exception as e:
        return f"Erro no banco de dados: {e}. Tente Reiniciar o servidor."

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

# ------------------ TEMPLATES (Omitidos para brevidade, mantenha os seus) ------------------
# [Mantenha aqui os blocos TEMPLATE_LEITURA, TEMPLATE_BALANCO, etc., que você já tem]

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
