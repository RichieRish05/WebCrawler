import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from utils import normalize

def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content

    # First, we check if the response is valid
    if resp.status != 200 or resp.error:
        return []
    # Check if we have a valid raw_response
    if not resp.raw_response or not resp.raw_response.content:
        return []

    # Parse the content of the response
    soup = BeautifulSoup(resp.raw_response.content, 'html.parser')
    # Find all the links in the content
    links = soup.find_all('a')
 
    base_url = resp.url
    # Extract hrefs and convert relative URLs to absolute URLs
    extracted_links = []
    for link in links:
        href = link.get('href')
        if href:
            # Skip non-http links
            if href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                continue
            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(base_url, href)
            # Normalize fragments
            if '#' in absolute_url:
                absolute_url = absolute_url.split('#')[0]
            # Remove trailing slashes
            normalized_url = normalize(absolute_url)
            extracted_links.append(normalized_url)
            
    # Return the list of extracted links
    return extracted_links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            return False
        
        # Filter out URLs that are not within the allowed UCI domains
        allowed_domains = ("ics.uci.edu", "cs.uci.edu", "informatics.uci.edu", "stat.uci.edu")
        if parsed.netloc and not any(parsed.netloc.endswith(domain) for domain in allowed_domains):
            return False
    
        # Block fragments
        if parsed.fragment:
            return False
        
        # Filter out URLs with file extensions that don't point to webpages
        return not re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower())

    except TypeError:
        print ("TypeError for ", parsed)
        raise
