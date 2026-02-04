import re
from urllib.parse import parse_qs, urldefrag, urljoin, urlparse
from bs4 import BeautifulSoup
from collections import defaultdict, Counter
from utils import normalize

DOKU_MEDIA_PARAMS = {"do", "tab_files", "tab_details", "image", "ns"}

STOPWORDS = [
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before",
    "being", "below", "between", "both", "but", "by", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's",
    "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how",
    "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is",
    "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most",
    "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should",
    "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their",
    "theirs", "them", "themselves", "then", "there", "there's", "these", "they",
    "they'd", "they'll", "they're", "they've", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd",
    "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
    "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
]


MAX_SIZE = 1_000_000

SUBDOMAIN_PAGE_COUNT = defaultdict(set)
WORD_FREQUENCIES = Counter()
TOTAL_UNIQUE_PAGES = set()
LONGEST_PAGE = {"url": None, "word_count": 0}


def scraper(url, resp):
    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]

    for link in valid_links:
        parsed = urlparse(link)
        host = parsed.hostname.lower() if parsed.hostname else ""
        if host.endswith(".uci.edu"):
            SUBDOMAIN_PAGE_COUNT[host].add(link)

    return valid_links


def tokenize(text: str) -> list[str]:
    text = text.lower()
    return re.findall(r"\b[a-zA-Z]{2,}\b", text)


def extract_next_links(url, resp):
    links = []
    if resp is None or resp.status != 200 or resp.raw_response is None:
        return links

    c_type = (resp.raw_response.headers.get("Content-Type") or "").lower()
    if "text/html" not in c_type:
        return links

    # Parse the content of the response
    html = resp.raw_response.content
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator=" ")
    words = [w for w in tokenize(text) if w not in STOPWORDS]
    word_count = len(words)

    if word_count < 100:
        return links
    elif word_count < 300 and content_length > MAX_SIZE:
        return links

    TOTAL_UNIQUE_PAGES.add(resp.raw_response.url)
    WORD_FREQUENCIES.update(words)
    if word_count > LONGEST_PAGE["word_count"]:
        LONGEST_PAGE["url"] = url
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
            or re.search(r"/\d{4}/\d{2}/\d{2}", parsed.path)
            or re.search(r"date=\d{4}-\d{2}-\d{2}", parsed.query)
        ):
            return False

        if host == "gitlab.ics.uci.edu":
            return False

        if not (
            any(host.endswith(domain) for domain in allowed_domains)
        ):
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
    }

    if any(k in DOKU_MEDIA_PARAMS for k in q.keys()):
        return False
    if len(q) > 5:
        return False
    if parsed.path.count("/") > 10:
        return False

    for key in q:
        if key in invalid_query_parameters:
            return False

    return True


def generate_report(filename="report.txt"):
    # getting all values to ensure consistency
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
