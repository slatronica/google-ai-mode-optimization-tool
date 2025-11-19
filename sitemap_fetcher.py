"""Sitemap-based content fetcher"""
import requests
import time
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class SitemapFetcher:
    """Handles fetching content from WordPress site via sitemap.xml"""
    
    def __init__(self, site_url: str, sitemap_url: str = None):
        self.site_url = site_url.rstrip('/')
        if sitemap_url:
            # If sitemap_url is relative, make it absolute
            if sitemap_url.startswith('http://') or sitemap_url.startswith('https://'):
                self.sitemap_url = sitemap_url
            else:
                # Relative path - join with site URL
                self.sitemap_url = urljoin(self.site_url + '/', sitemap_url.lstrip('/'))
        else:
            self.sitemap_url = f"{self.site_url}/sitemap.xml"
        
        # Set up session with proper headers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def fetch_all_content(self) -> Dict:
        """Fetch all content from WordPress site via sitemap"""
        logger.info(f"Fetching content from sitemap: {self.sitemap_url}")
        
        # Get all URLs from sitemap(s)
        urls = self.get_all_urls_from_sitemap(self.sitemap_url)
        logger.info(f"Found {len(urls)} URLs in sitemap(s)")
        
        # Categorize URLs and fetch content
        posts = []
        pages = []
        categories = []
        tags = []
        media = []
        
        for url in urls:
            url_lower = url.lower()
            # Skip sitemap URLs themselves
            if 'sitemap' in url_lower and url_lower.endswith('.xml'):
                continue
                
            # Categorize based on URL patterns
            if '/category/' in url_lower or '/categories/' in url_lower:
                categories.append({'url': url})
            elif '/tag/' in url_lower or '/tags/' in url_lower:
                tags.append({'url': url})
            elif '/wp-content/uploads/' in url_lower or any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.mp4', '.mp3']):
                media.append({'url': url})
            elif any(pattern in url_lower for pattern in ['/page/', '/about', '/contact', '/privacy', '/terms', '/services', '/products']):
                # Likely a page
                page_data = self.fetch_page_content(url)
                if page_data:
                    pages.append(page_data)
            else:
                # Likely a post (blog post, article, etc.)
                post_data = self.fetch_page_content(url)
                if post_data:
                    posts.append(post_data)
            
            time.sleep(0.3)  # Rate limiting
        
        logger.info(f"Fetched {len(posts)} posts and {len(pages)} pages")
        
        return {
            'posts': posts,
            'pages': pages,
            'categories': categories,
            'tags': tags,
            'media': media
        }
    
    def get_all_urls_from_sitemap(self, sitemap_url: str) -> Set[str]:
        """Recursively get all URLs from sitemap, handling nested sitemaps"""
        urls = set()
        visited_sitemaps = set()
        
        def parse_sitemap(url: str):
            """Parse a sitemap and extract URLs or nested sitemap references"""
            if url in visited_sitemaps:
                return
            visited_sitemaps.add(url)
            
            try:
                logger.info(f"Fetching sitemap: {url}")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get('Content-Type', '').lower()
                logger.debug(f"Response Content-Type: {content_type}")
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response size: {len(response.content)} bytes")
                
                # Check if response is empty
                if len(response.content) == 0:
                    logger.error(f"Received empty response from {url}")
                    return
                
                # Try to decode the content first
                try:
                    # Try UTF-8 first (requests should handle encoding automatically)
                    xml_content = response.text
                except (UnicodeDecodeError, AttributeError):
                    # Fallback: decode manually
                    try:
                        xml_content = response.content.decode('utf-8')
                    except UnicodeDecodeError:
                        # Try with error handling
                        xml_content = response.content.decode('utf-8', errors='ignore')
                        logger.warning(f"Had to decode XML with error handling for {url}")
                
                # Remove BOM if present
                if xml_content.startswith('\ufeff'):
                    xml_content = xml_content[1:]
                    logger.debug("Removed BOM from XML")
                
                # Check if response is actually XML (not HTML)
                xml_content_stripped = xml_content.strip()
                if xml_content_stripped.startswith('<!DOCTYPE') or xml_content_stripped.startswith('<html'):
                    logger.error(f"Received HTML instead of XML from {url}")
                    logger.error(f"This might be a 404 page, redirect, or the sitemap URL is incorrect.")
                    logger.error(f"Response preview: {xml_content[:500]}")
                    logger.error(f"Please verify the sitemap URL is correct: {url}")
                    return
                
                # Check if it looks like XML
                if not xml_content_stripped.startswith('<?xml') and not xml_content_stripped.startswith('<'):
                    logger.error(f"Response doesn't appear to be XML from {url}")
                    logger.error(f"Response preview: {xml_content[:500]}")
                    return
                
                # Parse XML
                try:
                    root = ET.fromstring(xml_content)
                except ET.ParseError as parse_err:
                    # Try to get more context about the error
                    logger.error(f"XML parsing failed for {url}: {parse_err}")
                    logger.error(f"Content type: {content_type}")
                    logger.error(f"First 500 chars of response: {xml_content[:500]}")
                    # Try to find the problematic line
                    lines = xml_content.split('\n')
                    if len(lines) > 0:
                        logger.error(f"First line: {lines[0][:200]}")
                    raise
                
                # Check if this is a sitemap index (contains nested sitemaps)
                if root.tag.endswith('sitemapindex'):
                    # This is a sitemap index - get nested sitemap URLs
                    namespace = self._get_namespace(root)
                    sitemap_elements = root.findall(f'.//{namespace}sitemap/{namespace}loc')
                    
                    for sitemap_elem in sitemap_elements:
                        nested_sitemap_url = sitemap_elem.text
                        if nested_sitemap_url:
                            # Resolve relative URLs
                            if not nested_sitemap_url.startswith('http'):
                                nested_sitemap_url = urljoin(url, nested_sitemap_url)
                            logger.info(f"Found nested sitemap: {nested_sitemap_url}")
                            parse_sitemap(nested_sitemap_url)
                            time.sleep(0.5)  # Rate limiting between sitemaps
                
                else:
                    # This is a regular sitemap - extract URLs
                    namespace = self._get_namespace(root)
                    url_elements = root.findall(f'.//{namespace}url/{namespace}loc')
                    
                    for url_elem in url_elements:
                        if url_elem.text:
                            urls.add(url_elem.text)
                    
                    logger.info(f"Extracted {len(url_elements)} URLs from sitemap")
                    
            except ET.ParseError as e:
                logger.error(f"Error parsing XML from {url}: {e}")
                logger.error(f"Response content type: {response.headers.get('Content-Type', 'unknown')}")
                logger.error(f"Response status code: {response.status_code}")
                # Try to show what we actually received
                try:
                    preview = response.text[:500] if hasattr(response, 'text') else str(response.content[:500])
                    logger.error(f"Response preview: {preview}")
                except:
                    logger.error(f"Response bytes preview: {response.content[:500]}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching sitemap {url}: {e}")
            except UnicodeDecodeError as e:
                logger.error(f"Error decoding response from {url}: {e}")
                logger.error(f"Trying alternative encoding methods...")
                # Try with different encodings
                try:
                    xml_content = response.content.decode('latin-1')
                    root = ET.fromstring(xml_content)
                    # If successful, continue processing
                    logger.info("Successfully decoded with latin-1 encoding")
                except Exception as e2:
                    logger.error(f"Failed to decode with alternative encoding: {e2}")
            except Exception as e:
                logger.error(f"Unexpected error processing sitemap {url}: {e}", exc_info=True)
        
        # Start parsing from the main sitemap
        parse_sitemap(sitemap_url)
        
        return urls
    
    def _get_namespace(self, root: ET.Element) -> str:
        """Extract namespace from XML root element"""
        # Get namespace from root tag
        namespace_match = re.match(r'\{([^}]+)\}', root.tag)
        if namespace_match:
            return f"{{{namespace_match.group(1)}}}"
        return ''
    
    def fetch_page_content(self, url: str) -> Dict:
        """Fetch and parse content from a single page URL"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = ''
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
            elif soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            
            # Extract main content
            content = ''
            # Try common WordPress content selectors
            content_selectors = [
                'article',
                '.entry-content',
                '.post-content',
                '.content',
                'main',
                '#content',
                '.main-content'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    content = content_elem.get_text(separator='\n', strip=True)
                    break
            
            # If no content found, try to get body text
            if not content:
                body = soup.find('body')
                if body:
                    # Remove script and style tags
                    for script in body(["script", "style", "nav", "header", "footer"]):
                        script.decompose()
                    content = body.get_text(separator='\n', strip=True)
            
            # Extract excerpt/meta description
            excerpt = ''
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                excerpt = meta_desc.get('content')
            
            # Try to determine if it's a post or page
            # Check for common WordPress post indicators
            is_post = any([
                soup.find('article', class_=re.compile(r'post|blog')),
                soup.find(class_=re.compile(r'single-post|post-type-post')),
                '/blog/' in url.lower() or '/news/' in url.lower()
            ])
            
            # Extract date if available
            date = ''
            time_tag = soup.find('time')
            if time_tag and time_tag.get('datetime'):
                date = time_tag.get('datetime')
            else:
                # Try meta tags
                meta_date = soup.find('meta', attrs={'property': 'article:published_time'})
                if meta_date:
                    date = meta_date.get('content', '')
            
            # Extract categories and tags if available
            categories = []
            tags = []
            
            # Look for category links
            category_links = soup.find_all('a', href=re.compile(r'/category/|/categories/'))
            for link in category_links[:10]:  # Limit to first 10
                cat_name = link.get_text(strip=True)
                if cat_name:
                    categories.append(cat_name)
            
            # Look for tag links
            tag_links = soup.find_all('a', href=re.compile(r'/tag/|/tags/'))
            for link in tag_links[:10]:  # Limit to first 10
                tag_name = link.get_text(strip=True)
                if tag_name:
                    tags.append(tag_name)
            
            return {
                'id': hash(url) % (10**9),  # Generate a numeric ID from URL hash
                'title': {'rendered': title},
                'link': url,
                'content': {'rendered': content},
                'excerpt': {'rendered': excerpt},
                'date': date,
                'categories': categories,
                'tags': tags,
                'type': 'post' if is_post else 'page'
            }
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing {url}: {e}")
            return None

