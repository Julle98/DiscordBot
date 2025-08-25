from cryptography.fernet import Fernet
import base64
import hashlib

def generoi_avain(salasana: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(salasana.encode()).digest())

def salaa(sisalto: str, salasana: str) -> str:
    f = Fernet(generoi_avain(salasana))
    return f.encrypt(sisalto.encode()).decode()

def pura(salattu: str, salasana: str) -> str:
    f = Fernet(generoi_avain(salasana))
    return f.decrypt(salattu.encode()).decode()