import firebase_admin
from firebase_admin import credentials, firestore

def iniciar_firebase():
    caminho_credencial = '/etc/secrets/firebase_key.json'

    if not firebase_admin._apps:
        cred = credentials.Certificate(caminho_credencial)
        firebase_admin.initialize_app(cred)

    return firestore.client()
