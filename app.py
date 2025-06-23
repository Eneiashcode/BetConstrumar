from flask import Flask, render_template, request, redirect, session, url_for
from firebase_config import iniciar_firebase
from utils.moedas import MOEDAS_POR_JOGADOR, calcular_valor_pix
import re

app = Flask(__name__)
app.secret_key = 'chave_secreta_simples'

# Conexão Firebase
db = iniciar_firebase()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome = request.form['nome'].strip()
        email = request.form['email'].strip()

        # Validação simples de nome
        if len(nome.split()) < 2:
            return "Por favor, informe Nome e Sobrenome."

        # Validação simples de email
        email_regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(email_regex, email):
            return "E-mail inválido. Por favor, insira um e-mail válido."

        user_id = nome.lower().replace(' ', '_')

        try:
            usuario_ref = db.collection('usuarios').document(user_id)
            usuario_doc = usuario_ref.get()

            if usuario_doc.exists:
                print(f"Login: Usuário {user_id} já existe no Firestore. Fazendo login...")
            else:
                print(f"Login: Usuário {user_id} não existe. Criando novo cadastro...")
                usuario_ref.set({
                    'nome': nome,
                    'email': email,
                    'moedas': 100,
                    'historico': [],
                    'total_apostas': 0,
                    'acertos': 0
                })
                print(f"Cadastro do usuário {user_id} criado com sucesso no Firestore.")

            # Salvar sessão
            session['usuario_id'] = user_id
            session['nome'] = nome
            session['email'] = email

            return redirect('/perfil')

        except Exception as e:
            print(f"Erro ao tentar fazer login ou criar usuário: {e}")
            return "Erro ao acessar o banco de dados. Verifique o Firebase e o console."

    return render_template('login.html')

@app.route('/perfil')
def perfil():
    user_id = session.get('usuario_id')
    if not user_id:
        return redirect('/login')

    try:
        usuario_ref = db.collection('usuarios').document(user_id)
        usuario_doc = usuario_ref.get()

        if usuario_doc.exists:
            usuario = usuario_doc.to_dict()
            moedas_faltantes = max(0, MOEDAS_POR_JOGADOR - usuario['moedas'])
            valor_estimado_pix = calcular_valor_pix(moedas_faltantes)

            return render_template('perfil.html',
                                   nome=usuario['nome'],
                                   email=usuario['email'],
                                   moedas=usuario['moedas'],
                                   valor_pix=valor_estimado_pix)
        else:
            return "Usuário não encontrado."

    except Exception as e:
        print(f"Erro no perfil: {e}")
        return "Erro ao carregar o perfil."

@app.route('/incluir_jogo', methods=['GET', 'POST'])
def incluir_jogo():
    if request.method == 'POST':
        jogadorA = request.form['jogadorA'].strip()
        jogadorB = request.form['jogadorB'].strip()

        if not jogadorA or not jogadorB:
            return "Preencha os dois nomes."

        db.collection('jogos').add({
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
        jogo = doc.to_dict()
        jogo['id'] = doc.id
        jogos.append(jogo)

    return render_template('jogos.html', jogos=jogos)

@app.route('/apostar', methods=['GET', 'POST'])
def apostar():
    user_id = session.get('usuario_id')

    if not user_id:
        return redirect('/login')

    if request.method == 'POST':
        jogo_id = request.form.get('jogo_id')
        palpite = request.form.get('palpite')
        quantidade_moedas = int(request.form.get('quantidade_moedas', 1))

        # Verifica se o jogo existe no Firebase
        jogo_doc = db.collection('jogos').document(jogo_id).get()
        if not jogo_doc.exists:
            return "Jogo inválido."

        # Carrega os dados do usuário do Firebase
        usuario_ref = db.collection('usuarios').document(user_id)
        usuario_doc = usuario_ref.get()

        if not usuario_doc.exists:
            return "Usuário não encontrado."

        usuario_data = usuario_doc.to_dict()

        # Verifica saldo
        saldo_atual = usuario_data.get('moedas', 0)
        if saldo_atual < quantidade_moedas:
            return f"Saldo insuficiente. Seu saldo atual: {saldo_atual} moedas."

        # Debita moedas
        novo_saldo = saldo_atual - quantidade_moedas
        usuario_ref.update({
            'moedas': novo_saldo,
            'total_apostas': usuario_data.get('total_apostas', 0) + 1
        })

        # Salva a aposta no Firestore
        db.collection('apostas').add({
            'usuario_id': user_id,
            'jogo_id': jogo_id,
            'palpite': palpite,
            'quantidade_moedas': quantidade_moedas
        })

        print(f"✅ Aposta registrada: {quantidade_moedas} moedas em {palpite} para o jogo {jogo_id}")

        return redirect('/perfil')

    # Se for GET, carrega jogos disponíveis
    jogos_disponiveis = []
    jogos_ref = db.collection('jogos').where('vencedor', '==', None).stream()
    for doc in jogos_ref:
        dados = doc.to_dict()
        jogos_disponiveis.append({
            'id': doc.id,
            'jogadorA': dados.get('jogadorA'),
            'jogadorB': dados.get('jogadorB')
        })

    # Carrega também os dados do usuário para mostrar o saldo
    usuario_doc = db.collection('usuarios').document(user_id).get()
    usuario_data = usuario_doc.to_dict()

    return render_template('apostar.html', jogos=jogos_disponiveis, usuario=usuario_data)

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
            try:
                # Atualizar resultado do jogo
                db.collection('jogos').document(jogo_id).update({
                    'vencedor': vencedor
                })
                print(f"✅ Resultado do jogo {jogo_id} salvo como: {vencedor}")

                # Agora vamos buscar todas as apostas feitas para esse jogo
                apostas_ref = db.collection('apostas').where('jogo_id', '==', jogo_id).stream()

                for aposta_doc in apostas_ref:
                    aposta = aposta_doc.to_dict()
                    apostador_id = aposta.get('usuario_id')
                    palpite = aposta.get('palpite')

                    print(f"🎯 Validando aposta do jogador: {apostador_id} | Palpite: {palpite} | Vencedor real: {vencedor}")

                    # Se o palpite bateu com o vencedor
                    if palpite == vencedor:
                        usuario_ref = db.collection('usuarios').document(apostador_id)
                        usuario_doc = usuario_ref.get()

                        if usuario_doc.exists:
                            usuario_data = usuario_doc.to_dict()
                            novos_acertos = usuario_data.get('acertos', 0) + 1

                            usuario_ref.update({
                                'acertos': novos_acertos
                            })
                            print(f"✅ {apostador_id} ganhou 1 acerto! Total agora: {novos_acertos}")

            except Exception as e:
                print(f"❌ Erro ao processar resultado: {e}")

        return redirect('/meus_jogos')

    # Exibir lista de jogos do usuário
    meus_jogos = []
    try:
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
    except Exception as e:
        print(f"❌ Erro ao carregar jogos: {e}")

    return render_template('meus_jogos.html', jogos=meus_jogos, nome=nome_usuario)

@app.route('/ranking')
def ranking():
    try:
        usuarios_ref = db.collection('usuarios').stream()
        ranking_lista = []

        for doc in usuarios_ref:
            usuario = doc.to_dict()
            ranking_lista.append({
                'nome': usuario.get('nome'),
                'acertos': usuario.get('acertos', 0),
                'moedas': usuario.get('moedas', 0)
            })

        # Ordena por acertos (maior para menor)
        ranking_ordenado = sorted(ranking_lista, key=lambda x: x['acertos'], reverse=True)

        return render_template('ranking.html', ranking=ranking_ordenado)

    except Exception as e:
        print(f"❌ Erro ao carregar ranking: {e}")
        return "Erro ao carregar o ranking."

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)
