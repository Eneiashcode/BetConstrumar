import firebase_admin
from firebase_admin import credentials, firestore

def iniciar_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate('seu_arquivo_chave_firebase.json')
        firebase_admin.initialize_app(cred)
    return firestore.client()
