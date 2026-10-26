import base64, hashlib, hmac, os, secrets, time
import jwt

SECRET = os.getenv("HP_SECRET", "")
if not SECRET:
    SECRET = "dev-only-secret-change-me"
    print("WARNING: HP_SECRET is not set. Using an insecure development secret.")


def hash_pw(pw, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200_000).hex()


def check_pw(pw, salt, h):
    return hmac.compare_digest(hash_pw(pw, salt)[1], h)


def make_token(uid, days=14):
    return jwt.encode({"sub": str(uid), "exp": int(time.time()) + days * 86400}, SECRET, algorithm="HS256")


def read_token(t):
    try:
        return int(jwt.decode(t, SECRET, algorithms=["HS256"])["sub"])
    except Exception:
        return None


def sig(batch, serial):
    """Short signature printed on the pack. Only the holder of HP_SECRET can create a valid one."""
    d = hmac.new(SECRET.encode(), f"{batch}|{serial}".encode(), hashlib.sha256).digest()
    return base64.b32encode(d).decode()[:8]


def sig_ok(batch, serial, s):
    return hmac.compare_digest(sig(batch, serial), s.upper())


def sign_payload(text):
    return hmac.new(SECRET.encode(), text.encode(), hashlib.sha256).hexdigest()
