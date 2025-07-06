from flask import Flask, render_template, request, redirect, session, url_for
from firebase_config import iniciar_firebase
from utils.moedas import MOEDAS_POR_JOGADOR, calcular_valor_pix
import re
from google.cloud import firestore
from flask import send_from_directory


app = Flask(__name__)
app.secret_key = 'chave_secreta_simples'

db = iniciar_firebase()

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json', mimetype='application/json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory('static', 'service-worker.js', mimetype='application/javascript')


@app.route('/boas_vindas')
def boas_vindas():
    bola_davez = obter_bola_da_vez()
    print("[DEBUG] Bola da Vez:", bola_davez)  # Adicione isso temporariamente
    return render_template("boas_vindas.html", bola_davez=bola_davez)


@app.route('/home')
def home_redirect():
    return redirect(url_for('boas_vindas'))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        email = request.form['email'].strip()

        if len(nome.split()) < 2:
            return "Por favor, informe Nome e Sobrenome."

        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_regex, email):
            return "E-mail inválido. Por favor, insira um e-mail válido."

        user_id = nome.lower().replace(' ', '_')
        usuario_ref = db.collection('usuarios').document(user_id)
        usuario_doc = usuario_ref.get()

        if not usuario_doc.exists:
            usuario_ref.set({
                'nome': nome,
                'email': email,
                'moedas': MOEDAS_POR_JOGADOR,
                'historico': [],
                'total_apostas': 0,
                'acertos': 0
            })

        # Salvar sessão
        session['usuario_id'] = user_id
        session['nome'] = nome
        session['email'] = email

        # ✅ Agora o fluxo vai para a página de boas-vindas:
        return redirect('/boas_vindas')

    return render_template('login.html')

@app.route('/perfil')
def perfil():
    user_id = session.get('usuario_id')
    nome = session.get('nome')
    email = session.get('email')

    if not user_id:
        return redirect('/login')

    usuario_doc = db.collection('usuarios').document(user_id).get()
    if not usuario_doc.exists:
        return redirect('/login')

    usuario = usuario_doc.to_dict()
    moedas_faltantes = max(0, MOEDAS_POR_JOGADOR - usuario['moedas'])
    valor_estimado_pix = calcular_valor_pix(moedas_faltantes)

    return render_template('perfil.html', nome=nome, email=email,
                           moedas=usuario['moedas'], valor_pix=valor_estimado_pix)

@app.route('/incluir_jogo', methods=['GET', 'POST'])
def incluir_jogo():
    user_id = session.get('usuario_id')
    nome_usuario = session.get('nome')

    if not user_id:
        return redirect('/login')

    if request.method == 'POST':
        jogadorA = nome_usuario
        jogadorB = request.form['jogadorB'].strip()

        if not jogadorB:
            return "Informe o nome do Jogador B."

        jogos_ref = db.collection('jogos')
        novo_jogo = jogos_ref.document()
        novo_jogo.set({
            'jogadorA': jogadorA,
            'jogadorB': jogadorB,
            'vencedor': None
        })

        return redirect('/jogos')

    return render_template('incluir_jogo.html')

@app.route('/jogos')
def listar_jogos():
    jogos_ref = db.collection('jogos').stream()
    jogos = []

    for doc in jogos_ref:
        dados = doc.to_dict()
        jogos.append({
            'id': doc.id,
            'jogadorA': dados.get('jogadorA'),
            'jogadorB': dados.get('jogadorB'),
            'vencedor': dados.get('vencedor')
        })

    return render_template('jogos.html', jogos=jogos)

@app.route('/apostar', methods=['GET', 'POST'])
def apostar():
    user_id = session.get('usuario_id')
    nome_usuario = session.get('nome')

    if not user_id:
        return redirect('/login')

    usuario_ref = db.collection('usuarios').document(user_id)
    usuario_doc = usuario_ref.get()

    if not usuario_doc.exists:
        return redirect('/login')

    usuario = usuario_doc.to_dict()

    # Buscar todos os jogos ainda sem vencedor
    jogos_ref = db.collection('jogos').where('vencedor', '==', None).stream()
    jogos = []
    for doc in jogos_ref:
        jogo = doc.to_dict()
        jogos.append({
            'id': doc.id,
            'jogadorA': jogo.get('jogadorA'),
            'jogadorB': jogo.get('jogadorB')
        })

    if request.method == 'POST':
        jogo_id = request.form['jogo_id']
        palpite = request.form['palpite']
        quantidade_moedas = int(request.form['quantidade_moedas'])

        if usuario['moedas'] < quantidade_moedas:
            return "Saldo insuficiente."

        # Atualiza saldo e total de apostas do usuário
        usuario_ref.update({
            'moedas': usuario['moedas'] - quantidade_moedas,
            'total_apostas': usuario.get('total_apostas', 0) + 1
        })

        # Atualiza histórico (agora com firestore.ArrayUnion para acumular)
        nova_aposta = {
            'jogo_id': jogo_id,
            'palpite': palpite,
            'quantidade_moedas': quantidade_moedas
        }

        usuario_ref.update({
            'historico': firestore.ArrayUnion([nova_aposta])
        })

        # Registra aposta na coleção "apostas"
        db.collection('apostas').add({
            'usuario_id': user_id,
            'jogo_id': jogo_id,
            'palpite': palpite,
            'quantidade_moedas': quantidade_moedas
        })

        return redirect('/perfil')

    return render_template('apostar.html', jogos=jogos, usuario=usuario)

@app.route('/meus_jogos', methods=['GET', 'POST'])
def meus_jogos():
    user_id = session.get('usuario_id')
    nome_usuario = session.get('nome')

    if not user_id or not nome_usuario:
        return redirect('/login')

    if request.method == 'POST':
        jogo_id = request.form.get('jogo_id')
        vencedor = request.form.get('vencedor')

        if jogo_id and vencedor:
            db.collection('jogos').document(jogo_id).update({
                'vencedor': vencedor
            })

            apostas_ref = db.collection('apostas').where('jogo_id', '==', jogo_id).stream()

            for aposta_doc in apostas_ref:
                aposta = aposta_doc.to_dict()
                apostador_id = aposta.get('usuario_id')
                palpite = aposta.get('palpite')

                if palpite == vencedor:
                    usuario_ref = db.collection('usuarios').document(apostador_id)
                    usuario_doc = usuario_ref.get()
                    if usuario_doc.exists:
                        usuario_data = usuario_doc.to_dict()
                        novos_acertos = usuario_data.get('acertos', 0) + 1
                        usuario_ref.update({'acertos': novos_acertos})

        return redirect('/meus_jogos')

    meus_jogos = []
    jogos_ref = db.collection('jogos').stream()

    for doc in jogos_ref:
        jogo = doc.to_dict()
        if nome_usuario in (jogo.get('jogadorA'), jogo.get('jogadorB')):
            meus_jogos.append({
                'id': doc.id,
                'jogadorA': jogo.get('jogadorA'),
                'jogadorB': jogo.get('jogadorB'),
                'vencedor': jogo.get('vencedor')
            })

    return render_template('meus_jogos.html', jogos=meus_jogos, nome=nome_usuario)

@app.route('/ranking')
def ranking():
    usuarios_ref = db.collection('usuarios').stream()
    ranking_lista = []

    for doc in usuarios_ref:
        usuario = doc.to_dict()
        ranking_lista.append({
            'nome': usuario.get('nome'),
            'acertos': usuario.get('acertos', 0),
            'moedas': usuario.get('moedas', 0)
        })

    ranking_ordenado = sorted(ranking_lista, key=lambda x: x['acertos'], reverse=True)

    return render_template('ranking.html', ranking=ranking_ordenado)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

def obter_bola_da_vez():
    jogos_mais_apostados = {}
    jogo_detalhes_cache = {}

    # Buscar todos os usuários
    usuarios_ref = db.collection('usuarios').stream()

    for usuario in usuarios_ref:
        dados = usuario.to_dict()
        historico = dados.get('historico', [])

        # Percorrer cada aposta feita por esse usuário
        for aposta in historico:
            jogo_id = aposta.get('jogo_id')
            if not jogo_id:
                continue

            # Contabiliza apostas por jogo
            jogos_mais_apostados[jogo_id] = jogos_mais_apostados.get(jogo_id, 0) + 1

    if not jogos_mais_apostados:
        return None  # Nenhuma aposta registrada

    # Encontrar o jogo mais apostado
    jogo_mais_apostado_id = max(jogos_mais_apostados, key=jogos_mais_apostados.get)
    total_apostas = jogos_mais_apostados[jogo_mais_apostado_id]

    # Buscar os detalhes do jogo mais apostado
    jogo_doc = db.collection('jogos').document(jogo_mais_apostado_id).get()

    if jogo_doc.exists:
        jogo = jogo_doc.to_dict()
        return {
            'id': jogo_mais_apostado_id,
            'jogadorA': jogo.get('jogadorA', 'Jogador A'),
            'jogadorB': jogo.get('jogadorB', 'Jogador B'),
            'total_apostas': total_apostas
        }

    return None


@app.route('/resetar_sistema', methods=['GET', 'POST'])
def resetar_sistema():
    user_id = session.get('usuario_id')
    if not user_id:
        return redirect('/login')

    usuario_doc = db.collection('usuarios').document(user_id).get()
    if not usuario_doc.exists:
        return redirect('/login')

    dados = usuario_doc.to_dict()
    email = dados.get('email', '')

    if email != 'edias.dias@terra.com.br':
        return "Acesso não autorizado.", 403

    # Zerar dados dos usuários
    usuarios_ref = db.collection('usuarios').stream()
    for doc in usuarios_ref:
        doc_ref = db.collection('usuarios').document(doc.id)
        doc_ref.update({
            'acertos': 0,
            'total_apostas': 0,
            'moedas': 100,
            'historico': []
        })

    # Limpar apostas
    apostas_ref = db.collection('apostas').stream()
    for aposta in apostas_ref:
        db.collection('apostas').document(aposta.id).delete()

    # Limpar jogos
    jogos_ref = db.collection('jogos').stream()
    for jogo in jogos_ref:
        db.collection('jogos').document(jogo.id).delete()

    print("[INFO] Sistema resetado com sucesso.")
    return redirect('/perfil')

if __name__ == '__main__':
    app.run(debug=True)
