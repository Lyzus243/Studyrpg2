import secrets

def generate_secret_key(length: int = 64) -> str:
    """Generate a secure random secret key."""
    return secrets.token_hex(length // 2)  # token_hex outputs 2 chars per byte

if __name__ == "__main__":
    key = generate_secret_key()
    print(f"Your new SECRET_KEY is:\n{key}")
