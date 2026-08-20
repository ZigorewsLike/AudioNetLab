def fixed_hash(text: str) -> int:
    """Stable string hash, unlike the built-in hash it does not change between runs.

    Used to pick a placeholder cover for a track id.

    :param text: Source string.
    :returns: int - Hash value.
    """
    hash_text = 0
    for ch in text:
        hash_text = (hash_text * 754645 ^ ord(ch) * 32454645) & 0xFAFAFA3434
    return hash_text


def median(a, x, b):
    """Clamp a value into the range [a, b].

    :param a: Lower bound.
    :param x: Value to clamp.
    :param b: Upper bound.
    :returns: The value limited by the bounds.
    """
    return min(max(x, a), b)