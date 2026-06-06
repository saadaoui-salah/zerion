# password_hasher.py
import hashlib

def hash_password(password):
    # Using SHA-256 for hashing
    return hashlib.sha256(password.encode()).hexdigest()