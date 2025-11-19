"""Content graph builder for WordPress sites"""
import networkx as nx
import re
import logging
from typing import Dict

from utils import clean_html

logger = logging.getLogger(__name__)


class GraphBuilder:
    """Builds and manages the content graph"""
    
    def __init__(self, site_url: str):
        self.site_url = site_url.rstrip('/')
        self.content_graph = nx.DiGraph()
    
    def build_content_graph(self, content: Dict) -> nx.DiGraph:
        """Build a graph representation of the site's content"""
        logger.info("Building content graph...")
        
        # Add posts as nodes
        for post in content.get('posts', []):
            try:
                # Handle both REST API format (dict with 'rendered') and sitemap format (string)
                title = post.get('title', {})
                if isinstance(title, dict):
                    title = title.get('rendered', '')
                
                post_content = post.get('content', {})
                if isinstance(post_content, dict):
                    post_content = post_content.get('rendered', '')
                
                excerpt = post.get('excerpt', {})
                if isinstance(excerpt, dict):
                    excerpt = excerpt.get('rendered', '')
                
                # Get post type (sitemap provides this, REST API doesn't)
                post_type = post.get('type', 'post')
                
                self.content_graph.add_node(
                    post['id'],
                    type=post_type,
                    title=title,
                    url=post.get('link', ''),
                    content=clean_html(post_content),
                    excerpt=clean_html(excerpt),
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
                # Handle both REST API format (dict with 'rendered') and sitemap format (string)
                title = page.get('title', {})
                if isinstance(title, dict):
                    title = title.get('rendered', '')
                
                page_content = page.get('content', {})
                if isinstance(page_content, dict):
                    page_content = page_content.get('rendered', '')
                
                # Get page type (sitemap provides this, REST API doesn't)
                page_type = page.get('type', 'page')
                
                self.content_graph.add_node(
                    f"page_{page['id']}",
                    type=page_type,
                    title=title,
                    url=page.get('link', ''),
                    content=clean_html(page_content),
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
                    # Handle both REST API format (dict with id, name, slug) and sitemap format (dict with url)
                    if isinstance(cat, dict):
                        if 'id' in cat:
                            # REST API format
                            self.content_graph.add_node(
                                f"cat_{cat['id']}",
                                type='category',
                                name=cat.get('name', ''),
                                slug=cat.get('slug', '')
                            )
                        elif 'url' in cat:
                            # Sitemap format - extract name from URL
                            url = cat['url']
                            name = url.split('/')[-1].replace('-', ' ').title()
                            slug = url.split('/')[-1]
                            cat_id = hash(url) % (10**9)
                            self.content_graph.add_node(
                                f"cat_{cat_id}",
                                type='category',
                                name=name,
                                slug=slug,
                                url=url
                            )
                except (KeyError, TypeError) as e:
                    logger.warning(f"Error adding category node: {e}, category data: {cat}")
        
        # Create tag nodes
        if content.get('tags'):
            for tag in content['tags']:
                try:
                    # Handle both REST API format (dict with id, name, slug) and sitemap format (dict with url)
                    if isinstance(tag, dict):
                        if 'id' in tag:
                            # REST API format
                            self.content_graph.add_node(
                                f"tag_{tag['id']}",
                                type='tag',
                                name=tag.get('name', ''),
                                slug=tag.get('slug', '')
                            )
                        elif 'url' in tag:
                            # Sitemap format - extract name from URL
                            url = tag['url']
                            name = url.split('/')[-1].replace('-', ' ').title()
                            slug = url.split('/')[-1]
                            tag_id = hash(url) % (10**9)
                            self.content_graph.add_node(
                                f"tag_{tag_id}",
                                type='tag',
                                name=name,
                                slug=slug,
                                url=url
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
                categories = data.get('categories', [])
                for cat_item in categories:
                    try:
                        # Handle both REST API format (list of IDs) and sitemap format (list of strings)
                        if isinstance(cat_item, (int, str)):
                            # REST API: numeric ID or sitemap: category name/string
                            if isinstance(cat_item, int):
                                cat_node_id = f"cat_{cat_item}"
                            else:
                                # Sitemap format: find category node by name
                                cat_node_id = None
                                for cat_node, cat_data in self.content_graph.nodes(data=True):
                                    if cat_data.get('type') == 'category' and cat_data.get('name', '').lower() == cat_item.lower():
                                        cat_node_id = cat_node
                                        break
                            
                            if cat_node_id and self.content_graph.has_node(cat_node_id):
                                self.content_graph.add_edge(node_id, cat_node_id, type='categorized_as')
                    except Exception as e:
                        logger.debug(f"Could not connect post {node_id} to category {cat_item}: {e}")
                
                # Connect to tags
                tags = data.get('tags', [])
                for tag_item in tags:
                    try:
                        # Handle both REST API format (list of IDs) and sitemap format (list of strings)
                        if isinstance(tag_item, (int, str)):
                            # REST API: numeric ID or sitemap: tag name/string
                            if isinstance(tag_item, int):
                                tag_node_id = f"tag_{tag_item}"
                            else:
                                # Sitemap format: find tag node by name
                                tag_node_id = None
                                for tag_node, tag_data in self.content_graph.nodes(data=True):
                                    if tag_data.get('type') == 'tag' and tag_data.get('name', '').lower() == tag_item.lower():
                                        tag_node_id = tag_node
                                        break
                            
                            if tag_node_id and self.content_graph.has_node(tag_node_id):
                                self.content_graph.add_edge(node_id, tag_node_id, type='tagged_as')
                    except Exception as e:
                        logger.debug(f"Could not connect post {node_id} to tag {tag_item}: {e}")
        except Exception as e:
            logger.error(f"Error building taxonomy edges: {e}", exc_info=True)
            raise

