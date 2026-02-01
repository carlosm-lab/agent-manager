"""
Google Antigravity Manager - Utilidades de Encriptación
Proporciona encriptación Fernet para datos sensibles.
"""

import os
import base64
import hashlib
from cryptography.fernet import Fernet


def get_encryption_key():
    """
    Generar clave de encriptación desde SECRET_KEY.
    Usa hash SHA-256 para asegurar una clave de 32 bytes.
    """
    secret = os.environ.get('SECRET_KEY', 'dev-secret-key')
    key_hash = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_hash)


def get_fernet():
    """Obtener instancia de Fernet para encriptar/desencriptar."""
    return Fernet(get_encryption_key())


def encrypt_data(plaintext):
    """
    Encriptar un string.
    
    Args:
        plaintext: String a encriptar
        
    Returns:
        String encriptado (codificado en base64)
    """
    if not plaintext:
        return plaintext
    
    fernet = get_fernet()
    encrypted = fernet.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt_data(ciphertext):
    """
    Desencriptar un string.
    
    Args:
        ciphertext: String encriptado (codificado en base64)
        
    Returns:
        String desencriptado en texto plano
    """
    if not ciphertext:
        return ciphertext
    
    try:
        fernet = get_fernet()
        decrypted = fernet.decrypt(ciphertext.encode())
        return decrypted.decode()
    except Exception:
        # Si falla la desencriptación, retornar original (puede estar sin encriptar)
        return ciphertext


def hash_pin(pin):
    """
    Hashear un PIN para almacenamiento seguro.
    
    Args:
        pin: PIN en texto plano
        
    Returns:
        Hash SHA-256 del PIN
    """
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_pin(pin, hashed_pin):
    """
    Verificar un PIN contra su hash usando comparación timing-safe.
    
    Args:
        pin: PIN en texto plano a verificar
        hashed_pin: Hash almacenado para comparar
        
    Returns:
        Booleano indicando si el PIN coincide
        
    Seguridad:
        Usa hmac.compare_digest para prevenir ataques de temporización.
    """
    import hmac
    pin_hash = hash_pin(pin)
    return hmac.compare_digest(pin_hash, hashed_pin)
