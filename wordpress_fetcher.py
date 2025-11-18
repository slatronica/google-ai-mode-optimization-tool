"""WordPress REST API content fetcher"""
import requests
import time
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class WordPressFetcher:
    """Handles fetching content from WordPress REST API"""
    
    def __init__(self, site_url: str):
        self.site_url = site_url.rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        
        # Set up session with proper headers to avoid Cloudflare/bot blocking
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def test_api_connection(self) -> bool:
        """Test if WordPress REST API is accessible"""
        try:
            test_url = f"{self.api_base}/posts"
            logger.info(f"Testing API connection to {test_url}")
            response = self.session.get(test_url, params={'per_page': 1}, timeout=10)
            logger.info(f"API test response status: {response.status_code}")
            
            if response.status_code == 200:
                logger.info("✓ WordPress REST API is accessible")
                return True
            elif response.status_code == 403:
                logger.error(f"✗ REST API access forbidden (403). This is often caused by:")
                logger.error(f"  1. Cloudflare bot protection blocking requests")
                logger.error(f"  2. WordPress security plugins (e.g., Wordfence, iThemes Security)")
                logger.error(f"  3. Server-level restrictions")
                logger.error(f"")
                logger.error(f"Solutions:")
                logger.error(f"  - Whitelist your server IP in Cloudflare/security plugins")
                logger.error(f"  - Disable REST API restrictions in security plugins")
                logger.error(f"  - Check if {test_url} works in a browser")
                logger.error(f"  - Consider using authentication if required")
                if 'cloudflare' in response.text.lower() or '__CF$cv$params' in response.text:
                    logger.error(f"  - Cloudflare challenge detected - may need to solve challenge or whitelist IP")
                logger.error(f"Response preview: {response.text[:300]}")
                return False
            elif response.status_code == 404:
                logger.error(f"✗ REST API endpoint not found. Please verify:")
                logger.error(f"  1. WordPress REST API is enabled")
                logger.error(f"  2. The URL {test_url} is correct")
                logger.error(f"  3. Try accessing it in a browser: {test_url}")
                logger.error(f"Response: {response.text[:500]}")
                return False
            elif response.status_code == 401:
                logger.error("✗ REST API requires authentication")
                logger.error(f"Response: {response.text[:500]}")
                return False
            else:
                logger.warning(f"API returned status {response.status_code}")
                logger.warning(f"Response: {response.text[:500]}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"✗ Failed to connect to REST API: {e}")
            logger.error(f"Please verify the site URL is correct and accessible")
            return False
    
    def fetch_all_content(self) -> Dict:
        """Fetch all content from WordPress site"""
        logger.info(f"Fetching content from {self.site_url}")
        
        # Test API connection first
        if not self.test_api_connection():
            logger.warning("API connection test failed, but continuing anyway...")
        
        content = {
            'posts': self.fetch_posts(),
            'pages': self.fetch_pages(),
            'categories': self.fetch_categories(),
            'tags': self.fetch_tags(),
            'media': self.fetch_media_info()
        }
        
        logger.info(f"Fetched {len(content['posts'])} posts and {len(content['pages'])} pages")
        return content
    
    def fetch_posts(self, per_page=100) -> List[Dict]:
        """Fetch all posts from WordPress"""
        posts = []
        page = 1
        
        logger.info(f"Fetching posts from {self.api_base}/posts")
        
        while True:
            try:
                url = f"{self.api_base}/posts"
                params = {'per_page': per_page, 'page': page, '_embed': True}
                logger.debug(f"Requesting: {url} with params: {params}")
                
                response = self.session.get(url, params=params, timeout=30)
                
                logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    batch = response.json()
                    logger.info(f"Page {page}: Received {len(batch)} posts")
                    if not batch:
                        logger.info("No more posts to fetch")
                        break
                    posts.extend(batch)
                    page += 1
                    time.sleep(0.5)  # Rate limiting
                elif response.status_code == 400:
                    # WordPress returns 400 when page number exceeds available pages
                    response_data = response.json()
                    if 'rest_post_invalid_page_number' in response_data.get('code', ''):
                        logger.info("Reached end of posts (all pages fetched)")
                    else:
                        logger.warning(f"Bad request (400) when fetching posts: {response_data}")
                    break
                elif response.status_code == 403:
                    logger.error(f"Access forbidden (403) when fetching posts. Check security settings.")
                    if page == 1:  # Only show detailed error on first page
                        logger.error(f"This usually means Cloudflare or security plugins are blocking access.")
                    break
                elif response.status_code == 404:
                    logger.warning(f"Posts endpoint not found (404). Check if REST API is enabled at {url}")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                elif response.status_code == 401:
                    logger.warning(f"Unauthorized (401). REST API may require authentication.")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                else:
                    logger.warning(f"Unexpected status code {response.status_code} when fetching posts")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error fetching posts: {e}")
                break
            except Exception as e:
                logger.error(f"Error fetching posts: {e}", exc_info=True)
                break
                
        logger.info(f"Total posts fetched: {len(posts)}")
        return posts
    
    def fetch_pages(self, per_page=100) -> List[Dict]:
        """Fetch all pages from WordPress"""
        pages = []
        page = 1
        
        logger.info(f"Fetching pages from {self.api_base}/pages")
        
        while True:
            try:
                url = f"{self.api_base}/pages"
                params = {'per_page': per_page, 'page': page, '_embed': True}
                logger.debug(f"Requesting: {url} with params: {params}")
                
                response = self.session.get(url, params=params, timeout=30)
                
                logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    batch = response.json()
                    logger.info(f"Page {page}: Received {len(batch)} pages")
                    if not batch:
                        logger.info("No more pages to fetch")
                        break
                    pages.extend(batch)
                    page += 1
                    time.sleep(0.5)
                elif response.status_code == 400:
                    # WordPress returns 400 when page number exceeds available pages
                    response_data = response.json()
                    if 'rest_post_invalid_page_number' in response_data.get('code', ''):
                        logger.info("Reached end of pages (all pages fetched)")
                    else:
                        logger.warning(f"Bad request (400) when fetching pages: {response_data}")
                    break
                elif response.status_code == 403:
                    logger.error(f"Access forbidden (403) when fetching pages. Check security settings.")
                    if page == 1:  # Only show detailed error on first page
                        logger.error(f"This usually means Cloudflare or security plugins are blocking access.")
                    break
                elif response.status_code == 404:
                    logger.warning(f"Pages endpoint not found (404). Check if REST API is enabled at {url}")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                elif response.status_code == 401:
                    logger.warning(f"Unauthorized (401). REST API may require authentication.")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                else:
                    logger.warning(f"Unexpected status code {response.status_code} when fetching pages")
                    logger.warning(f"Response: {response.text[:200]}")
                    break
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error fetching pages: {e}")
                break
            except Exception as e:
                logger.error(f"Error fetching pages: {e}", exc_info=True)
                break
                
        logger.info(f"Total pages fetched: {len(pages)}")
        return pages
    
    def fetch_categories(self) -> List[Dict]:
        """Fetch all categories"""
        try:
            response = self.session.get(f"{self.api_base}/categories", params={'per_page': 100}, timeout=30)
            return response.json() if response.status_code == 200 else []
        except:
            return []
    
    def fetch_tags(self) -> List[Dict]:
        """Fetch all tags"""
        try:
            response = self.session.get(f"{self.api_base}/tags", params={'per_page': 100}, timeout=30)
            return response.json() if response.status_code == 200 else []
        except:
            return []
    
    def fetch_media_info(self) -> List[Dict]:
        """Fetch media information"""
        try:
            response = self.session.get(f"{self.api_base}/media", params={'per_page': 50}, timeout=30)
            return response.json() if response.status_code == 200 else []
        except:
            return []

