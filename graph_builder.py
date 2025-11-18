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
                self.content_graph.add_node(
                    post['id'],
                    type='post',
                    title=post.get('title', {}).get('rendered', ''),
                    url=post.get('link', ''),
                    content=clean_html(post.get('content', {}).get('rendered', '')),
                    excerpt=clean_html(post.get('excerpt', {}).get('rendered', '')),
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
                    content=clean_html(page.get('content', {}).get('rendered', '')),
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

