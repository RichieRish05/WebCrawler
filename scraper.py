import re
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse
from bs4 import BeautifulSoup
from collections import defaultdict, Counter
from utils import normalize

DOKU_MEDIA_PARAMS = {"do", "tab_files", "tab_details", "image", "ns"}

STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "aren't",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can't",
    "cannot",
    "could",
    "couldn't",
    "did",
    "didn't",
    "do",
    "does",
    "doesn't",
    "doing",
    "don't",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadn't",
    "has",
    "hasn't",
    "have",
    "haven't",
    "having",
    "he",
    "he'd",
    "he'll",
    "he's",
    "her",
    "here",
    "here's",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "how's",
    "i",
    "i'd",
    "i'll",
    "i'm",
    "i've",
    "if",
    "in",
    "into",
    "is",
    "isn't",
    "it",
    "it's",
    "its",
    "itself",
    "let's",
    "me",
    "more",
    "most",
    "mustn't",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "shan't",
    "she",
    "she'd",
    "she'll",
    "she's",
    "should",
    "shouldn't",
    "so",
    "some",
    "such",
    "than",
    "that",
    "that's",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "there's",
    "these",
    "they",
    "they'd",
    "they'll",
    "they're",
    "they've",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasn't",
    "we",
    "we'd",
    "we'll",
    "we're",
    "we've",
    "were",
    "weren't",
    "what",
    "what's",
    "when",
    "when's",
    "where",
    "where's",
    "which",
    "while",
    "who",
    "who's",
    "whom",
    "why",
    "why's",
    "with",
    "won't",
    "would",
    "wouldn't",
    "you",
    "you'd",
    "you'll",
    "you're",
    "you've",
    "your",
    "yours",
    "yourself",
    "yourselves",
}


MAX_SIZE = 1_000_000

SUBDOMAIN_PAGE_COUNT = defaultdict(set)
WORD_FREQUENCIES = Counter()
TOTAL_UNIQUE_PAGES = set()
LONGEST_PAGE = {"url": None, "word_count": 0}
CONTENT_HASHES: set[int] = set()  # For exact duplicate detection
NEAR_DUPLICATE_FINGERPRINTS: set[frozenset] = set()  # For near-duplicate detection


def djb2_hash(text: str) -> int:
    """DJB2 hash function for string hashing.

    Used for trigram hashing in near-duplicate detection. The algorithm
    multiplies by 33 (via bit shift) and adds each character's ASCII value.
    Time complexity: O(n). Returns 64-bit hash to minimize collisions.

    Source: https://mojoauth.com/hashing/bernsteins-hash-djb2-in-python
    """
    hash_value = 5381
    for char in text:
        hash_value = ((hash_value << 5) + hash_value) + ord(char)
    return hash_value & 0xFFFFFFFFFFFFFFFF


def djb2_hash_bytes(data: bytes) -> int:
    """DJB2 hash for raw HTML content bytes.

    Used for exact duplicate detection BEFORE parsing HTML. Hashing raw bytes
    is faster than parsing first, and catches identical pages early.
    """
    hash_value = 5381
    for byte in data:
        hash_value = ((hash_value << 5) + hash_value) + byte
    return hash_value & 0xFFFFFFFFFFFFFFFF


def is_near_duplicate(tokens: list[str], threshold: float = 0.95) -> bool:
    """Detect near-duplicate content using trigram Jaccard similarity.

    Why Jaccard over SimHash:
    - SimHash computes a single hash where similar documents have similar hashes
    - Problem: UCI sites share templates/headers/footers, causing SimHash to
      flag distinct pages as duplicates due to high template similarity
    - Jaccard compares actual content overlap (intersection/union of trigrams)
    - This measures TRUE content similarity, not just structural similarity
    - Result: Jaccard correctly identifies duplicates while avoiding false
      positives from shared site templates

    Algorithm:
    1. Create trigrams (3-word sequences) from the token list
    2. Hash each trigram using DJB2
    3. Sample ~25% of hashes (those divisible by 4) as a fingerprint (MinHash-like)
    4. Compare fingerprint against all seen fingerprints using Jaccard similarity
    5. If similarity >= 0.95, it's a near-duplicate

    The 0.95 threshold is conservative - only flags pages that are 95%+ similar
    in actual word content, avoiding false positives from template similarity.
    """
    if len(tokens) < 10:
        return False

    # Create trigrams and hash them
    trigrams = [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
    trigram_hashes = {djb2_hash(t) for t in trigrams}

    # MinHash-like sampling: only keep hashes divisible by 4
    fingerprint = frozenset(h for h in trigram_hashes if h % 4 == 0)

    if not fingerprint:
        return False

    # Compare against seen fingerprints
    for seen in NEAR_DUPLICATE_FINGERPRINTS:
        intersection = len(fingerprint & seen)
        union = len(fingerprint | seen)
        if union > 0 and intersection / union >= threshold:
            return True

    NEAR_DUPLICATE_FINGERPRINTS.add(fingerprint)
    return False


def scraper(url, resp):
    """Main entry point called by the crawler for each URL.

    Extracts links from the page, filters them through is_valid(),
    and tracks subdomain statistics for the report.
    Returns list of valid URLs to add to the frontier.
    """
    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]

    for link in valid_links:
        parsed = urlparse(link)
        host = parsed.hostname.lower() if parsed.hostname else ""
        if host.endswith(".uci.edu"):
            SUBDOMAIN_PAGE_COUNT[host].add(link)

    return valid_links


def tokenize(text: str) -> list[str]:
    """Extract words from text for word frequency analysis.

    Returns lowercase words with 2+ alphabetic characters.
    Filters out numbers, punctuation, and single-letter words.
    """
    text = text.lower()
    return re.findall(r"\b[a-zA-Z]{2,}\b", text)


def extract_next_links(url, resp):
    """Process a page response and extract all links.

    This function handles:
    1. Response validation (status 200, HTML content)
    2. Exact duplicate detection (via content hash)
    3. Content extraction and word counting
    4. Low-value page filtering (< 50 words, large files with little text)
    5. Near-duplicate detection (via trigram Jaccard similarity)
    6. Statistics tracking (unique pages, word frequencies, longest page)
    7. Link extraction and normalization

    Returns empty list if page should be skipped, otherwise returns
    list of absolute URLs found on the page.
    """
    links = []
    if resp is None or resp.status != 200 or resp.raw_response is None:
        return links

    c_type = (resp.raw_response.headers.get("Content-Type") or "").lower()
    if "text/html" not in c_type:
        return links

    html = resp.raw_response.content

    # Exact duplicate detection using raw content hash (before parsing)
    content_hash = djb2_hash_bytes(html)
    if content_hash in CONTENT_HASHES:
        return links  # Skip exact duplicate
    CONTENT_HASHES.add(content_hash)

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")
    words = [w for w in tokenize(text) if w not in STOPWORDS]
    word_count = len(words)

    if word_count < 50:
        return links

    # Skip large files with low information value
    if word_count < 100 and len(html) > MAX_SIZE:
        return links

    # Near-duplicate detection using trigram Jaccard
    if is_near_duplicate(words):
        return links

    TOTAL_UNIQUE_PAGES.add(resp.raw_response.url)
    WORD_FREQUENCIES.update(words)
    if word_count > LONGEST_PAGE["word_count"]:
        LONGEST_PAGE["url"] = resp.raw_response.url
        LONGEST_PAGE["word_count"] = word_count

    for a_tag in soup.find_all("a", href=True):
        raw = a_tag["href"].strip()
        if raw.startswith(("mailto:", "javascript:", "tel:")):
            continue
        try:
            absolute_url = urljoin(resp.raw_response.url or url, raw)
        except ValueError:
            continue
        clean_url, _ = urldefrag(absolute_url)
        clean_url = normalize(clean_url)
        links.append(clean_url)

    return list(set(links))


def is_valid(url):
    """Determine if a URL should be crawled.

    Validates URLs against multiple criteria:
    - Must be http/https scheme
    - Must be in allowed domains (ics, cs, informatics, stat .uci.edu)
    - Must not be a known trap pattern (calendars, dates, login pages, etc.)
    - Must not be a binary/media file extension
    - Must not have problematic query parameters

    Trap patterns blocked:
    - Date-based URLs (calendars, events, timelines)
    - Authentication pages (login, register, auth)
    - DokuWiki media pages, eppstein/pix (image galleries)
    - GitLab (infinite repository traversal)
    - Dataset pages (large files, low text value)
    """
    allowed_domains = (
        ".ics.uci.edu",
        ".cs.uci.edu",
        ".informatics.uci.edu",
        ".stat.uci.edu",
    )

    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return False

        host = (parsed.hostname or "").lower()
        if parsed.fragment:
            return False
        if (
            "timeline" in parsed.path.lower()
            or "ml/datasets" in parsed.path.lower()
            or "/events/" in parsed.path.lower()
            or "tribe" in parsed.path.lower()
            or "tribe" in parsed.query.lower()
            or "wp-login" in parsed.path.lower()
            or "/auth/" in parsed.path.lower()
            or "/login" in parsed.path.lower()
            or "/register" in parsed.path.lower()
            or "ical" in parsed.path.lower()
            or "ical" in parsed.query.lower()
            or "eppstein/pix" in parsed.path.lower()
            or "doku.php" in parsed.path.lower()
            or "dataset" in parsed.path.lower()
            or "sld" in parsed.path.lower()
            or re.search(r"/\d{4}/\d{2}/\d{2}", parsed.path)
            or re.search(r"/day/\d{4}-\d{2}-\d{2}", parsed.path)
            or re.search(r"/\d{4}-\d{2}$", parsed.path)
            or re.search(r"date=\d{4}-\d{2}-\d{2}", parsed.query)
        ):
            return False

        if host == "gitlab.ics.uci.edu":
            return False

        if not (any(host.endswith(domain) for domain in allowed_domains)):
            return False

        if not valid_query(parsed):
            return False

        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|war|java|bam|svg|ppsx|pps"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$",
            parsed.path.lower(),
        )
    except TypeError:
        print("TypeError for ", parsed)
        return False


def valid_query(parsed):
    """Check if URL query parameters are acceptable.

    Blocks URLs with query parameters that indicate:
    - DokuWiki actions (do, media, tab_files, etc.)
    - Calendar exports (ical, outlook-ical)
    - Revision/version parameters (rev, action, version)
    - Apache directory sorting (C, O params create infinite variations)
    - Social sharing links (share=facebook/twitter)
    - Wiki format variants (format=txt duplicates)
    - WordPress comment replies (replytocom)

    Also rejects URLs with > 100 query parameters (likely spam/trap).
    """
    q = parse_qs(parsed.query or "")
    invalid_query_parameters = {
        "do",
        "media",
        "ical",
        "idx",
        "sid",
        "rev",
        "rev2",
        "action",
        "version",
        "tab_files",
        "tab_details",
        "a",
        "h",
        "hb",
        "sf",
        "outlook-ical",
        "C",  # Apache directory listing sort column
        "O",  # Apache directory listing sort order
        "share",  # Social sharing links (facebook, twitter)
        "format",  # Trac wiki text format duplicates
        "replytocom",  # WordPress comment reply links
    }

    if any(k in DOKU_MEDIA_PARAMS for k in q.keys()):
        return False
    if len(q) > 100:
        return False

    for key in q:
        if key in invalid_query_parameters:
            return False

    return True


def generate_report(filename="report.txt"):
    """Generate the final crawl report with all required statistics.

    Report includes:
    1. Total unique pages crawled
    2. URL of longest page (by word count) and its word count
    3. Top 50 most common words (excluding stopwords)
    4. All subdomains found with their page counts
    """
    longest_url = LONGEST_PAGE["url"]
    longest_wc = LONGEST_PAGE["word_count"]
    total_unique = len(TOTAL_UNIQUE_PAGES)
    all_subdomains = sorted(SUBDOMAIN_PAGE_COUNT.keys())

    with open(filename, "w") as file:
        file.write(f"Unique pages: {total_unique}\n")
        file.write(f"Longest word count url: {longest_url}\n")
        file.write(f"Longest word count: {longest_wc}\n")

        for word, count in WORD_FREQUENCIES.most_common(50):
            file.write(f"{word}: {count}\n")

        file.write(f"Total subdomains: {len(all_subdomains)}\n")
        for subdomain in all_subdomains:
            file.write(f"{subdomain}: {len(SUBDOMAIN_PAGE_COUNT[subdomain])}\n")
