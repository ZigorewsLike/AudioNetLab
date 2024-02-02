def fixed_hash(text: str) -> int:
    hash_text = 0
    for ch in text:
        hash_text = (hash_text * 754645 ^ ord(ch) * 32454645) & 0xFAFAFA3434
    return hash_text

def median(a, x, b):
    return min(max(x, a), b)