"""Local tests for scraper functions - no server needed."""

from scraper import (
    djb2_hash,
    compute_simhash,
    hamming_distance,
    is_near_duplicate,
    is_valid,
    tokenize,
    SIMHASHES
)


def test_djb2_hash():
    print("=== Testing djb2_hash ===")

    # Same text should produce same hash
    h1 = djb2_hash("hello world")
    h2 = djb2_hash("hello world")
    print(f"Same text produces same hash: {h1 == h2}")  # True

    # Different text should produce different hash
    h3 = djb2_hash("hello worlds")
    print(f"Different text produces different hash: {h1 != h3}")  # True

    # Hash is 64-bit
    print(f"Hash is 64-bit: {h1 < 2**64}")  # True
    print()


def test_simhash():
    print("=== Testing simhash ===")

    # Similar documents should have small Hamming distance
    doc1 = ["computer", "science", "research", "data", "algorithm", "programming"]
    doc2 = ["computer", "science", "research", "data", "algorithm", "coding"]  # 1 word different
    doc3 = ["biology", "chemistry", "physics", "math", "experiment", "laboratory"]  # Completely different

    hash1 = compute_simhash(doc1)
    hash2 = compute_simhash(doc2)
    hash3 = compute_simhash(doc3)

    dist_similar = hamming_distance(hash1, hash2)
    dist_different = hamming_distance(hash1, hash3)

    print(f"Similar docs Hamming distance: {dist_similar} (should be small, <=10)")
    print(f"Different docs Hamming distance: {dist_different} (should be large, >10)")
    print(f"Similar < Different: {dist_similar < dist_different}")
    print()


def test_near_duplicate():
    print("=== Testing near-duplicate detection ===")

    # Clear any existing simhashes
    SIMHASHES.clear()

    # Add first document
    doc1 = ["web", "crawler", "python", "scraper", "html", "parsing"] * 10
    hash1 = compute_simhash(doc1)
    SIMHASHES.append(hash1)

    # Very similar document should be detected as near-duplicate
    doc2 = ["web", "crawler", "python", "scraper", "html", "parser"] * 10  # 1 word different
    hash2 = compute_simhash(doc2)
    print(f"Similar doc is near-duplicate: {is_near_duplicate(hash2)}")
    print(f"  Hamming distance: {hamming_distance(hash1, hash2)}")

    # Different document should NOT be detected as near-duplicate
    doc3 = ["machine", "learning", "neural", "network", "training", "model"] * 10
    hash3 = compute_simhash(doc3)
    print(f"Different doc is near-duplicate: {is_near_duplicate(hash3)}")
    print(f"  Hamming distance: {hamming_distance(hash1, hash3)}")
    print()


def test_is_valid():
    print("=== Testing is_valid URL filter ===")

    # Should PASS
    valid_urls = [
        "https://www.ics.uci.edu/",
        "https://www.cs.uci.edu/page",
        "https://www.informatics.uci.edu/research",
        "https://www.stat.uci.edu/faculty",
    ]

    # Should FAIL
    invalid_urls = [
        ("https://gitlab.ics.uci.edu/repo", "GitLab blocked"),
        ("https://www.ics.uci.edu/2024/01/15", "Date trap"),
        ("https://www.ics.uci.edu/events/2024-01-15", "Date trap hyphen"),
        ("https://www.ics.uci.edu/file.pdf", "PDF extension"),
        ("https://www.ics.uci.edu/file.zip", "ZIP extension"),
        ("https://www.google.com/", "Not UCI domain"),
        ("https://www.ics.uci.edu/timeline/event", "Timeline trap"),
    ]

    print("Valid URLs (should all be True):")
    for url in valid_urls:
        result = is_valid(url)
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {url}")

    print("\nInvalid URLs (should all be False):")
    for url, reason in invalid_urls:
        result = is_valid(url)
        status = "PASS" if not result else "FAIL"
        print(f"  [{status}] {url} ({reason})")
    print()


def test_tokenize():
    print("=== Testing tokenize ===")

    text = "Hello, World! This is a TEST with numbers123 and symbols@#$."
    tokens = tokenize(text)
    print(f"Input: {text}")
    print(f"Tokens: {tokens}")
    print(f"All lowercase: {all(t.islower() for t in tokens)}")
    print(f"All alpha: {all(t.isalpha() for t in tokens)}")
    print(f"All >= 2 chars: {all(len(t) >= 2 for t in tokens)}")
    print()


if __name__ == "__main__":
    test_djb2_hash()
    test_simhash()
    test_near_duplicate()
    test_is_valid()
    test_tokenize()

    print("=== All tests complete ===")
