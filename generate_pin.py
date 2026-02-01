"""
Google Antigravity Manager - Generador de PIN
Genera un hash SHA-256 para el PIN de acceso.
Ejecutar: python generate_pin.py
"""

import hashlib


def generate_pin_hash(pin):
    """
    Generar hash SHA-256 de un PIN.
    
    Args:
        pin: PIN en texto plano
        
    Returns:
        Hash SHA-256 del PIN en formato hexadecimal
    """
    return hashlib.sha256(pin.encode()).hexdigest()


def main():
    """Función principal del generador de PIN."""
    print("\nGenerador de PIN - Antigravity Manager\n")
    
    pin = input("Ingresa tu PIN de acceso: ")
    
    if not pin:
        print("Error: El PIN no puede estar vacío")
        return
    
    pin_hash = generate_pin_hash(pin)
    
    print("\nHash generado:")
    print("Copia esta línea a tu archivo .env o configúrala en Vercel")
    print(f"ACCESS_PIN_HASH={pin_hash}")


if __name__ == '__main__':
    main()
