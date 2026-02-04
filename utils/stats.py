import re
import shelve
from collections import defaultdict, Counter
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Common English stop words
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and',
    'any', 'are', "aren't", 'as', 'at', 'be', 'because', 'been', 'before', 'being',
    'below', 'between', 'both', 'but', 'by', "can't", 'cannot', 'could', "couldn't",
    'did', "didn't", 'do', 'does', "doesn't", 'doing', "don't", 'down', 'during',
    'each', 'few', 'for', 'from', 'further', 'had', "hadn't", 'has', "hasn't",
    'have', "haven't", 'having', 'he', "he'd", "he'll", "he's", 'her', 'here',
    "here's", 'hers', 'herself', 'him', 'himself', 'his', 'how', "how's", 'i',
    "i'd", "i'll", "i'm", "i've", 'if', 'in', 'into', 'is', "isn't", 'it', "it's",
    'its', 'itself', "let's", 'me', 'more', 'most', "mustn't", 'my', 'myself',
    'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought',
    'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', "shan't", 'she',
    "she'd", "she'll", "she's", 'should', "shouldn't", 'so', 'some', 'such', 'than',
    'that', "that's", 'the', 'their', 'theirs', 'them', 'themselves', 'then',
    'there', "there's", 'these', 'they', "they'd", "they'll", "they're", "they've",
    'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was',
    "wasn't", 'we', "we'd", "we'll", "we're", "we've", 'were', "weren't", 'what',
    "what's", 'when', "when's", 'where', "where's", 'which', 'while', 'who',
    "who's", 'whom', 'why', "why's", 'with', "won't", 'would', "wouldn't", 'you',
    "you'd", "you'll", "you're", "you've", 'your', 'yours', 'yourself', 'yourselves'
}

class CrawlerStats:
    def __init__(self, stats_file='crawler_stats.shelve'):
        self.stats_file = stats_file
        self.unique_pages = set()  # URLs (without fragments)
        self.page_word_counts = {}  # URL -> word count
        self.all_words = Counter()  # Word -> frequency
        self.subdomain_counts = defaultdict(set)  # subdomain -> set of URLs
        
    def add_page(self, url, content):
        """
        Add a page to statistics.
        url: The normalized URL (fragments already removed)
        content: The raw HTML content
        """
        # Track unique pages (URLs are already normalized, fragments removed)
        self.unique_pages.add(url)
        
        # Extract subdomain
        parsed = urlparse(url)
        if parsed.netloc:
            self.subdomain_counts[parsed.netloc].add(url)
        
        # Extract text and count words
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            # Get all text, excluding script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            
            # Extract words (alphanumeric sequences)
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            
            # Filter out stop words and count
            filtered_words = [w for w in words if w not in STOP_WORDS and len(w) > 1]
            
            # Update word counts
            word_count = len(filtered_words)
            self.page_word_counts[url] = word_count
            
            # Update global word frequency
            self.all_words.update(filtered_words)
    
    def get_longest_page(self):
        """Return the URL and word count of the longest page."""
        if not self.page_word_counts:
            return None, 0
        url = max(self.page_word_counts, key=self.page_word_counts.get)
        return url, self.page_word_counts[url]
    
    def get_top_words(self, n=50):
        """Return the top N most common words."""
        return self.all_words.most_common(n)
    
    def get_subdomain_stats(self):
        """Return subdomain statistics as a list of (subdomain, count) tuples, sorted alphabetically."""
        stats = [(subdomain, len(urls)) for subdomain, urls in self.subdomain_counts.items()]
        return sorted(stats)
    
    def save(self):
        """Save statistics to disk."""
        with shelve.open(self.stats_file) as db:
            db['unique_pages'] = self.unique_pages
            db['page_word_counts'] = self.page_word_counts
            db['all_words'] = dict(self.all_words)
            db['subdomain_counts'] = {k: list(v) for k, v in self.subdomain_counts.items()}
    
    def load(self):
        """Load statistics from disk."""
        try:
            with shelve.open(self.stats_file) as db:
                self.unique_pages = db.get('unique_pages', set())
                self.page_word_counts = db.get('page_word_counts', {})
                self.all_words = Counter(db.get('all_words', {}))
                subdomain_data = db.get('subdomain_counts', {})
                # Keep as defaultdict to auto-create sets for new subdomains
                self.subdomain_counts = defaultdict(set, {k: set(v) for k, v in subdomain_data.items()})
        except:
            pass  # File doesn't exist yet
    
    def generate_report(self):
        """Generate a report with all required statistics."""
        report = []
        report.append("=" * 60)
        report.append("CRAWLER STATISTICS REPORT")
        report.append("=" * 60)
        report.append("")
        
        # 1. Unique pages
        report.append(f"1. Number of unique pages: {len(self.unique_pages)}")
        report.append("")
        
        # 2. Longest page
        longest_url, longest_count = self.get_longest_page()
        report.append(f"2. Longest page (word count): {longest_count} words")
        report.append(f"   URL: {longest_url}")
        report.append("")
        
        # 3. Top 50 words
        report.append("3. Top 50 most common words (excluding stop words):")
        top_words = self.get_top_words(50)
        for i, (word, count) in enumerate(top_words, 1):
            report.append(f"   {i:2d}. {word:20s} - {count:6d} occurrences")
        report.append("")
        
        # 4. Subdomain statistics
        report.append("4. Subdomain statistics:")
        subdomain_stats = self.get_subdomain_stats()
        for subdomain, count in subdomain_stats:
            report.append(f"   {subdomain}, {count}")
        report.append("")
        
        return "\n".join(report)

