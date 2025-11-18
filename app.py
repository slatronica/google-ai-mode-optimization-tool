import requests
import json
import networkx as nx
from urllib.parse import urlparse, urljoin
import time
from datetime import datetime
import anthropic
from typing import List, Dict, Set, Tuple
import re
from collections import defaultdict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WordPressQueryFanOutAnalyzer:
    """Analyze WordPress sites for Google AI Mode query fan-out optimization"""
    
    def __init__(self, site_url: str, claude_api_key: str, claude_model: str = "claude-sonnet-4-5"):
        self.site_url = site_url.rstrip('/')
        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        logger.info(f"Initialized analyzer for {self.site_url}")
        logger.info(f"REST API base URL: {self.api_base}")
        self.claude = anthropic.Anthropic(api_key=claude_api_key)
        self.claude_model = claude_model
        self.content_graph = nx.DiGraph()
        self.query_patterns = defaultdict(list)
        self.content_cache = {}
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        
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
    
    def build_content_graph(self, content: Dict) -> nx.DiGraph:
        """Build a graph representation of the site's content"""
        logger.info("Building content graph...")
        
        # Add posts as nodes
        for post in content.get('posts', []):
            try:
                self.content_graph.add_node(
                    post['id'],
                    type='post',
                    title=post.get('title', {}).get('rendered', ''),
                    url=post.get('link', ''),
                    content=self.clean_html(post.get('content', {}).get('rendered', '')),
                    excerpt=self.clean_html(post.get('excerpt', {}).get('rendered', '')),
                    categories=post.get('categories', []),
                    tags=post.get('tags', []),
                    date=post.get('date', '')
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"Error adding post node: {e}, post ID: {post.get('id', 'unknown')}")
                continue
            
        # Add pages as nodes
        for page in content.get('pages', []):
            try:
                self.content_graph.add_node(
                    f"page_{page['id']}",
                    type='page',
                    title=page.get('title', {}).get('rendered', ''),
                    url=page.get('link', ''),
                    content=self.clean_html(page.get('content', {}).get('rendered', '')),
                    parent=page.get('parent', 0),
                    date=page.get('date', '')
                )
            except (KeyError, TypeError) as e:
                logger.warning(f"Error adding page node: {e}, page ID: {page.get('id', 'unknown')}")
                continue
        
        # Build edges based on internal links
        self.build_internal_link_edges()
        
        # Build edges based on category/tag relationships
        self.build_taxonomy_edges(content)
        
        logger.info(f"Content graph built with {self.content_graph.number_of_nodes()} nodes and {self.content_graph.number_of_edges()} edges")
        return self.content_graph
    
    def clean_html(self, html: str) -> str:
        """Remove HTML tags and clean text"""
        text = re.sub('<.*?>', '', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def build_internal_link_edges(self):
        """Extract and build edges from internal links"""
        # Convert to list first to avoid "dictionary changed size during iteration" error
        nodes_list = list(self.content_graph.nodes(data=True))
        for node_id, data in nodes_list:
            if 'content' in data:
                # Extract internal links
                links = re.findall(rf'{self.site_url}/[^"\'>\s]+', data['content'])
                
                # Convert target nodes to list as well
                target_nodes_list = list(self.content_graph.nodes(data=True))
                for link in links:
                    # Find the target node
                    for target_id, target_data in target_nodes_list:
                        if target_data.get('url') == link:
                            self.content_graph.add_edge(node_id, target_id, type='internal_link')
                            break
    
    def build_taxonomy_edges(self, content: Dict):
        """Build edges based on categories and tags"""
        # Create category nodes
        if content.get('categories'):
            for cat in content['categories']:
                try:
                    self.content_graph.add_node(
                        f"cat_{cat['id']}",
                        type='category',
                        name=cat.get('name', ''),
                        slug=cat.get('slug', '')
                    )
                except (KeyError, TypeError) as e:
                    logger.warning(f"Error adding category node: {e}, category data: {cat}")
        
        # Create tag nodes
        if content.get('tags'):
            for tag in content['tags']:
                try:
                    self.content_graph.add_node(
                        f"tag_{tag['id']}",
                        type='tag',
                        name=tag.get('name', ''),
                        slug=tag.get('slug', '')
                    )
                except (KeyError, TypeError) as e:
                    logger.warning(f"Error adding tag node: {e}, tag data: {tag}")
        
        # Connect posts to categories and tags
        # Convert to list first to avoid "dictionary changed size during iteration" error
        try:
            nodes_list = list(self.content_graph.nodes(data=True))
            for node_id, data in nodes_list:
                # Skip if node doesn't have type or if it's not a post
                if not data or data.get('type') != 'post':
                    continue
                
                # Connect to categories
                for cat_id in data.get('categories', []):
                    try:
                        cat_node_id = f"cat_{cat_id}"
                        # Only add edge if category node exists
                        if self.content_graph.has_node(cat_node_id):
                            self.content_graph.add_edge(node_id, cat_node_id, type='categorized_as')
                    except Exception as e:
                        logger.debug(f"Could not connect post {node_id} to category {cat_id}: {e}")
                
                # Connect to tags
                for tag_id in data.get('tags', []):
                    try:
                        tag_node_id = f"tag_{tag_id}"
                        # Only add edge if tag node exists
                        if self.content_graph.has_node(tag_node_id):
                            self.content_graph.add_edge(node_id, tag_node_id, type='tagged_as')
                    except Exception as e:
                        logger.debug(f"Could not connect post {node_id} to tag {tag_id}: {e}")
        except Exception as e:
            logger.error(f"Error building taxonomy edges: {e}", exc_info=True)
            raise
    
    def analyze_query_patterns(self) -> Dict:
        """Analyze content for complex query patterns using Claude"""
        logger.info("Analyzing query patterns with Claude API...")
        
        patterns = {
            'complex_queries': [],
            'decompositions': {},
            'coverage_analysis': {},
            'opportunities': []
        }
        
        # Sample content for analysis
        sample_content = self.get_content_sample()
        
        # Analyze with Claude
        prompt = f"""Analyze this WordPress site content for Google AI Mode query optimization opportunities.

Site URL: {self.site_url}

Content Sample:
{json.dumps(sample_content, indent=2)[:3000]}

Identify:
1. Complex queries users might ask that would trigger Google's query fan-out
2. How Google would decompose these queries into sub-queries
3. Which content currently answers which sub-queries
4. Gaps where sub-queries aren't answered
5. Multi-source optimization opportunities

Focus on queries that would require multiple hops of reasoning to answer fully.

Provide analysis in JSON format with:
- complex_queries: List of potential complex user queries
- decompositions: How each query would be broken down
- current_coverage: Which content addresses which sub-queries
- gaps: Missing sub-query content
- recommendations: Specific content to create"""

        try:
            response = self.claude.messages.create(
                model=self.claude_model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Claude's response - handle both old and new response formats
            response_text = ""
            if hasattr(response, 'content') and len(response.content) > 0:
                # Handle text content blocks
                if hasattr(response.content[0], 'text'):
                    response_text = response.content[0].text
                elif isinstance(response.content[0], dict) and 'text' in response.content[0]:
                    response_text = response.content[0]['text']
                else:
                    # Fallback: try to get text from response directly
                    response_text = str(response.content[0])
            else:
                logger.warning("Unexpected response format from Claude API")
                return patterns
            
            analysis = self.parse_claude_response(response_text)
            patterns.update(analysis)
            
        except Exception as e:
            logger.error(f"Error analyzing with Claude: {e}")
        
        return patterns
    
    def get_content_sample(self) -> List[Dict]:
        """Get a representative sample of content"""
        sample = []
        
        for node_id, data in list(self.content_graph.nodes(data=True))[:20]:
            if data['type'] in ['post', 'page']:
                sample.append({
                    'title': data['title'],
                    'type': data['type'],
                    'excerpt': data.get('excerpt', '')[:200],
                    'url': data['url']
                })
        
        return sample
    
    def parse_claude_response(self, response_text: str) -> Dict:
        """Parse Claude's response into structured data"""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                return json.loads(json_match.group())
            else:
                # Fallback parsing
                return self.fallback_parse(response_text)
        except:
            return self.fallback_parse(response_text)
    
    def fallback_parse(self, text: str) -> Dict:
        """Fallback parsing if JSON extraction fails"""
        return {
            'complex_queries': re.findall(r'"([^"]+\?)"', text),
            'recommendations': [text],
            'gaps': []
        }
    
    def analyze_content_depth(self) -> Dict:
        """Analyze content depth and multi-hop potential"""
        logger.info("Analyzing content depth and multi-hop potential...")
        
        depth_analysis = {
            'content_scores': {},
            'hub_potential': [],
            'orphan_content': [],
            'semantic_clusters': []
        }
        
        # Calculate content depth scores
        for node_id, data in self.content_graph.nodes(data=True):
            if data['type'] in ['post', 'page']:
                score = self.calculate_content_depth(data)
                depth_analysis['content_scores'][node_id] = {
                    'title': data['title'],
                    'url': data['url'],
                    'depth_score': score,
                    'word_count': len(data.get('content', '').split()),
                    'internal_links': self.content_graph.out_degree(node_id),
                    'backlinks': self.content_graph.in_degree(node_id)
                }
        
        # Identify hub potential
        for node_id, score_data in depth_analysis['content_scores'].items():
            if score_data['internal_links'] > 5 and score_data['depth_score'] > 0.7:
                depth_analysis['hub_potential'].append(score_data)
        
        # Find orphan content
        for node_id, score_data in depth_analysis['content_scores'].items():
            if score_data['backlinks'] == 0 and score_data['internal_links'] < 2:
                depth_analysis['orphan_content'].append(score_data)
        
        # Identify semantic clusters
        depth_analysis['semantic_clusters'] = self.identify_semantic_clusters()
        
        return depth_analysis
    
    def calculate_content_depth(self, node_data: Dict) -> float:
        """Calculate a depth score for content"""
        score = 0.0
        
        # Word count factor
        word_count = len(node_data.get('content', '').split())
        if word_count > 2000:
            score += 0.3
        elif word_count > 1000:
            score += 0.2
        elif word_count > 500:
            score += 0.1
        
        # Heading structure (simplified)
        content = node_data.get('content', '')
        h2_count = content.count('<h2') + content.count('## ')
        h3_count = content.count('<h3') + content.count('### ')
        
        if h2_count > 3:
            score += 0.2
        if h3_count > 5:
            score += 0.1
        
        # Media presence
        if '<img' in content or '[gallery' in content:
            score += 0.1
        
        # Lists and structured data
        if '<ul' in content or '<ol' in content or '- ' in content:
            score += 0.1
        
        # Schema markup indicators
        if 'itemtype' in content or '@type' in content:
            score += 0.2
        
        return min(score, 1.0)
    
    def identify_semantic_clusters(self) -> List[Dict]:
        """Identify semantic content clusters using TF-IDF"""
        logger.info("Identifying semantic clusters...")
        
        # Prepare content for vectorization
        content_texts = []
        node_ids = []
        
        for node_id, data in self.content_graph.nodes(data=True):
            if data['type'] in ['post', 'page'] and data.get('content'):
                content_texts.append(data['content'])
                node_ids.append(node_id)
        
        if not content_texts:
            return []
        
        # Vectorize content
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(content_texts)
            
            # Calculate similarity matrix
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # Identify clusters (simplified clustering)
            clusters = []
            visited = set()
            
            for i in range(len(node_ids)):
                if node_ids[i] in visited:
                    continue
                    
                cluster = {
                    'center': node_ids[i],
                    'members': [],
                    'theme': self.extract_cluster_theme(i, tfidf_matrix)
                }
                
                for j in range(len(node_ids)):
                    if similarity_matrix[i][j] > 0.3:  # Similarity threshold
                        cluster['members'].append({
                            'id': node_ids[j],
                            'similarity': float(similarity_matrix[i][j])
                        })
                        visited.add(node_ids[j])
                
                if len(cluster['members']) > 1:
                    clusters.append(cluster)
            
            return clusters
            
        except Exception as e:
            logger.error(f"Error in semantic clustering: {e}")
            return []
    
    def extract_cluster_theme(self, doc_index: int, tfidf_matrix) -> List[str]:
        """Extract theme keywords for a cluster"""
        feature_names = self.tfidf_vectorizer.get_feature_names_out()
        doc_tfidf = tfidf_matrix[doc_index].toarray()[0]
        
        # Get top 5 terms
        top_indices = doc_tfidf.argsort()[-5:][::-1]
        return [feature_names[i] for i in top_indices if doc_tfidf[i] > 0]
    
    def generate_optimization_report(self) -> Dict:
        """Generate comprehensive optimization report"""
        logger.info("Generating optimization report...")
        
        # Fetch and analyze content
        content = self.fetch_all_content()
        self.build_content_graph(content)
        
        # Run analyses
        query_patterns = self.analyze_query_patterns()
        depth_analysis = self.analyze_content_depth()
        
        # Generate recommendations
        recommendations = self.generate_recommendations(query_patterns, depth_analysis)
        
        # Compile report
        report = {
            'site_url': self.site_url,
            'analysis_date': datetime.now().isoformat(),
            'summary': {
                'total_posts': len(content['posts']),
                'total_pages': len(content['pages']),
                'content_nodes': self.content_graph.number_of_nodes(),
                'internal_links': self.content_graph.number_of_edges(),
                'orphan_content': len(depth_analysis['orphan_content']),
                'hub_pages': len(depth_analysis['hub_potential']),
                'semantic_clusters': len(depth_analysis['semantic_clusters'])
            },
            'query_optimization': query_patterns,
            'content_depth': depth_analysis,
            'recommendations': recommendations,
            'action_plan': self.create_action_plan(recommendations)
        }
        
        return report
    
    def generate_recommendations(self, query_patterns: Dict, depth_analysis: Dict) -> List[Dict]:
        """Generate specific optimization recommendations"""
        recommendations = []
        
        # Query coverage recommendations
        if 'gaps' in query_patterns:
            for gap in query_patterns.get('gaps', []):
                recommendations.append({
                    'type': 'content_gap',
                    'priority': 'high',
                    'action': 'Create new content',
                    'details': f"Create content to answer sub-query: {gap}",
                    'impact': 'Enables multi-hop reasoning path'
                })
        
        # Orphan content recommendations
        for orphan in depth_analysis['orphan_content'][:5]:  # Top 5
            recommendations.append({
                'type': 'orphan_content',
                'priority': 'medium',
                'action': 'Add internal links',
                'details': f"Connect orphan content: {orphan['title']}",
                'url': orphan['url'],
                'impact': 'Improves content graph connectivity'
            })
        
        # Hub optimization
        for hub in depth_analysis['hub_potential'][:3]:  # Top 3
            recommendations.append({
                'type': 'hub_optimization',
                'priority': 'high',
                'action': 'Enhance hub page',
                'details': f"Optimize hub potential: {hub['title']}",
                'url': hub['url'],
                'impact': 'Strengthens multi-source selection'
            })
        
        # Semantic cluster recommendations
        for cluster in depth_analysis['semantic_clusters'][:3]:  # Top 3
            recommendations.append({
                'type': 'semantic_bridge',
                'priority': 'medium',
                'action': 'Create semantic bridges',
                'details': f"Link related content in cluster: {', '.join(cluster['theme'])}",
                'impact': 'Enables query fan-out paths'
            })
        
        return recommendations
    
    def create_action_plan(self, recommendations: List[Dict]) -> Dict:
        """Create prioritized action plan"""
        action_plan = {
            'immediate': [],
            'short_term': [],
            'long_term': []
        }
        
        for rec in recommendations:
            if rec['priority'] == 'high':
                action_plan['immediate'].append({
                    'action': rec['action'],
                    'details': rec['details'],
                    'expected_impact': rec['impact']
                })
            elif rec['priority'] == 'medium':
                action_plan['short_term'].append({
                    'action': rec['action'],
                    'details': rec['details'],
                    'expected_impact': rec['impact']
                })
            else:
                action_plan['long_term'].append({
                    'action': rec['action'],
                    'details': rec['details'],
                    'expected_impact': rec['impact']
                })
        
        return action_plan
    
    def export_report(self, report: Dict, filename: str = 'seo_analysis_report.json'):
        """Export report to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report exported to {filename}")
    
    def visualize_content_graph(self, output_file: str = 'content_graph.html'):
        """Create an interactive visualization of the content graph"""
        import pyvis.network as net
        
        # Create pyvis network
        nt = net.Network(height='750px', width='100%', bgcolor='#222222', font_color='white')
        
        # Add nodes with different colors by type
        color_map = {
            'post': '#1f77b4',
            'page': '#ff7f0e',
            'category': '#2ca02c',
            'tag': '#d62728'
        }
        
        for node_id, data in self.content_graph.nodes(data=True):
            nt.add_node(
                node_id,
                label=data.get('title', data.get('name', str(node_id)))[:30],
                color=color_map.get(data['type'], '#gray'),
                title=data.get('url', ''),
                size=20 + self.content_graph.degree(node_id) * 2
            )
        
        # Add edges
        for source, target in self.content_graph.edges():
            nt.add_edge(source, target)
        
        # Generate HTML
        nt.save_graph(output_file)
        logger.info(f"Content graph visualization saved to {output_file}")

def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='WordPress Query Fan-Out SEO Analyzer')
    parser.add_argument('site_url', help='WordPress site URL')
    parser.add_argument('claude_api_key', help='Claude API key')
    parser.add_argument('--output', default='seo_report.json', help='Output file name')
    parser.add_argument('--visualize', action='store_true', help='Generate graph visualization')
    parser.add_argument('--model', default='claude-sonnet-4-5', 
                       help='Claude model to use (default: claude-sonnet-4-5). Other options: claude-3-opus-20240229, claude-3-haiku-20240307, claude-3-5-haiku-20241022')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    # Initialize analyzer
    analyzer = WordPressQueryFanOutAnalyzer(args.site_url, args.claude_api_key, args.model)
    
    # Generate report
    report = analyzer.generate_optimization_report()
    
    # Export report
    analyzer.export_report(report, args.output)
    
    # Generate visualization if requested
    if args.visualize:
        analyzer.visualize_content_graph()
    
    # Print summary
    print("\n" + "="*50)
    print("SEO ANALYSIS COMPLETE")
    print("="*50)
    print(f"Site: {report['site_url']}")
    print(f"Total Content Nodes: {report['summary']['content_nodes']}")
    print(f"Orphan Content: {report['summary']['orphan_content']}")
    print(f"Potential Hub Pages: {report['summary']['hub_pages']}")
    print(f"Semantic Clusters: {report['summary']['semantic_clusters']}")
    print(f"\nTop Recommendations: {len(report['recommendations'])}")
    print(f"Report saved to: {args.output}")
    
    if report['recommendations']:
        print("\nTop 3 Immediate Actions:")
        for i, rec in enumerate(report['recommendations'][:3], 1):
            print(f"{i}. {rec['action']}: {rec['details']}")

if __name__ == "__main__":
    main()
