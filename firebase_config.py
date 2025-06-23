import os
import firebase_admin
from firebase_admin import credentials, firestore

def iniciar_firebase():
    # Verifica se está rodando no Render
    if os.environ.get('RENDER'):
        caminho_credencial = '/etc/secrets/firebase_key.json'  # Caminho usado no Render
    else:
        caminho_credencial = 'seu_arquivo_chave_firebase.json'  # Caminho usado localmente

    if not firebase_admin._apps:
        cred = credentials.Certificate(caminho_credencial)
        firebase_admin.initialize_app(cred)

    return firestore.client()
