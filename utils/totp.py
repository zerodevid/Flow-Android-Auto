#!/usr/bin/env python3
"""
TOTP (Time-based One-Time Password) Generator
Generates TOTP codes from secret keys
"""

import hmac
import hashlib
import struct
import time
import base64
import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class TOTPConfig:
    """TOTP configuration"""
    secret: str
    digits: int = 6
    period: int = 30
    algorithm: str = "sha1"
    issuer: Optional[str] = None
    account: Optional[str] = None


def normalize_secret(secret: str) -> bytes:
    """
    Normalize and decode a TOTP secret key
    Handles various formats: base32, with/without spaces, uppercase/lowercase
    """
    # Remove spaces, dashes, and convert to uppercase
    secret = re.sub(r'[\s\-]', '', secret.upper())
    
    # Add padding if needed (base32 requires padding to multiple of 8)
    padding = 8 - (len(secret) % 8)
    if padding != 8:
        secret += '=' * padding
    
    try:
        return base64.b32decode(secret)
    except Exception as e:
        raise ValueError(f"Invalid TOTP secret: {e}")


def generate_totp(secret: str, digits: int = 6, period: int = 30, 
                  timestamp: Optional[float] = None) -> str:
    """
    Generate a TOTP code
    
    Args:
        secret: Base32 encoded secret key
        digits: Number of digits in the code (default 6)
        period: Time period in seconds (default 30)
        timestamp: Optional timestamp (uses current time if not provided)
    
    Returns:
        TOTP code as string
    """
    if timestamp is None:
        timestamp = time.time()
    
    # Decode secret
    key = normalize_secret(secret)
    
    # Calculate time counter
    counter = int(timestamp // period)
    
    # Pack counter as big-endian 64-bit integer
    counter_bytes = struct.pack('>Q', counter)
    
    # Generate HMAC-SHA1
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    
    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    truncated = struct.unpack('>I', hmac_hash[offset:offset + 4])[0]
    truncated &= 0x7FFFFFFF
    
    # Get the final code
    code = truncated % (10 ** digits)
    
    return str(code).zfill(digits)


def get_totp_with_remaining(secret: str, digits: int = 6, period: int = 30) -> Tuple[str, int]:
    """
    Generate TOTP code and return remaining validity time
    
    Returns:
        Tuple of (code, seconds_remaining)
    """
    now = time.time()
    code = generate_totp(secret, digits, period, now)
    remaining = period - int(now % period)
    return code, remaining


def wait_for_fresh_totp(secret: str, min_remaining: int = 5, 
                        digits: int = 6, period: int = 30) -> str:
    """
    Wait for a fresh TOTP code with at least min_remaining seconds of validity
    
    Args:
        secret: TOTP secret key
        min_remaining: Minimum seconds of validity required
        digits: Number of digits
        period: Time period
    
    Returns:
        Fresh TOTP code
    """
    while True:
        code, remaining = get_totp_with_remaining(secret, digits, period)
        if remaining >= min_remaining:
            return code
        # Wait for next period
        time.sleep(remaining + 1)


def parse_totp_uri(uri: str) -> TOTPConfig:
    """
    Parse a TOTP URI (otpauth://totp/...)
    
    Args:
        uri: TOTP URI string
    
    Returns:
        TOTPConfig object
    """
    import urllib.parse
    
    if not uri.startswith("otpauth://totp/"):
        raise ValueError("Invalid TOTP URI")
    
    # Parse the URI
    parsed = urllib.parse.urlparse(uri)
    params = urllib.parse.parse_qs(parsed.query)
    
    # Extract label (account name)
    label = urllib.parse.unquote(parsed.path.lstrip('/'))
    
    # Extract parameters
    secret = params.get('secret', [None])[0]
    if not secret:
        raise ValueError("Missing secret in TOTP URI")
    
    return TOTPConfig(
        secret=secret,
        digits=int(params.get('digits', [6])[0]),
        period=int(params.get('period', [30])[0]),
        algorithm=params.get('algorithm', ['sha1'])[0].lower(),
        issuer=params.get('issuer', [None])[0],
        account=label
    )


class TOTPManager:
    """
    Manages multiple TOTP secrets and generates codes
    """
    
    def __init__(self):
        self._secrets: dict[str, TOTPConfig] = {}
    
    def add(self, name: str, secret: str, digits: int = 6, period: int = 30):
        """Add a TOTP secret"""
        self._secrets[name] = TOTPConfig(secret=secret, digits=digits, period=period)
    
    def add_uri(self, name: str, uri: str):
        """Add from TOTP URI"""
        self._secrets[name] = parse_totp_uri(uri)
    
    def get(self, name: str) -> Optional[str]:
        """Get TOTP code for a saved secret"""
        if name not in self._secrets:
            return None
        config = self._secrets[name]
        return generate_totp(config.secret, config.digits, config.period)
    
    def get_with_remaining(self, name: str) -> Optional[Tuple[str, int]]:
        """Get TOTP code and remaining time"""
        if name not in self._secrets:
            return None
        config = self._secrets[name]
        return get_totp_with_remaining(config.secret, config.digits, config.period)
    
    def get_fresh(self, name: str, min_remaining: int = 5) -> Optional[str]:
        """Get fresh TOTP code with minimum remaining validity"""
        if name not in self._secrets:
            return None
        config = self._secrets[name]
        return wait_for_fresh_totp(config.secret, min_remaining, config.digits, config.period)
    
    def remove(self, name: str):
        """Remove a secret"""
        self._secrets.pop(name, None)
    
    def list(self) -> list[str]:
        """List all saved secret names"""
        return list(self._secrets.keys())
    
    def save(self, filepath: str):
        """Save secrets to JSON file"""
        import json
        data = {name: {"secret": cfg.secret, "digits": cfg.digits, "period": cfg.period}
                for name, cfg in self._secrets.items()}
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: str):
        """Load secrets from JSON file"""
        import json
        with open(filepath) as f:
            data = json.load(f)
        for name, cfg in data.items():
            self._secrets[name] = TOTPConfig(**cfg)


# Global manager instance
totp_manager = TOTPManager()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
TOTP Generator

Usage:
    python totp.py <secret>           Generate code from secret
    python totp.py -w <secret>        Wait for fresh code (5+ seconds remaining)
    python totp.py -u <otpauth_uri>   Generate from URI
    
Example:
    python totp.py JBSWY3DPEHPK3PXP
    python totp.py -w JBSWY3DPEHPK3PXP
""")
        sys.exit(1)
    
    if sys.argv[1] == "-w" and len(sys.argv) > 2:
        secret = sys.argv[2]
        print("Waiting for fresh code...")
        code = wait_for_fresh_totp(secret)
        print(f"TOTP: {code}")
    elif sys.argv[1] == "-u" and len(sys.argv) > 2:
        uri = sys.argv[2]
        config = parse_totp_uri(uri)
        code = generate_totp(config.secret, config.digits, config.period)
        remaining = config.period - int(time.time() % config.period)
        print(f"TOTP: {code} (valid for {remaining}s)")
    else:
        secret = sys.argv[1]
        code, remaining = get_totp_with_remaining(secret)
        print(f"TOTP: {code} (valid for {remaining}s)")
