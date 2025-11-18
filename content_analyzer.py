"""Content depth and semantic analysis"""
import logging
from typing import List, Dict
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Analyzes content depth and semantic relationships"""
    
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
    
    def analyze_content_depth(self, content_graph) -> Dict:
        """Analyze content depth and multi-hop potential"""
        logger.info("Analyzing content depth and multi-hop potential...")
        
        depth_analysis = {
            'content_scores': {},
            'hub_potential': [],
            'orphan_content': [],
            'semantic_clusters': []
        }
        
        # Calculate content depth scores
        for node_id, data in content_graph.nodes(data=True):
            if data.get('type') in ['post', 'page']:
                score = self.calculate_content_depth(data)
                depth_analysis['content_scores'][node_id] = {
                    'title': data.get('title', ''),
                    'url': data.get('url', ''),
                    'depth_score': score,
                    'word_count': len(data.get('content', '').split()),
                    'internal_links': content_graph.out_degree(node_id),
                    'backlinks': content_graph.in_degree(node_id)
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
        depth_analysis['semantic_clusters'] = self.identify_semantic_clusters(content_graph)
        
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
    
    def identify_semantic_clusters(self, content_graph) -> List[Dict]:
        """Identify semantic content clusters using TF-IDF"""
        logger.info("Identifying semantic clusters...")
        
        # Prepare content for vectorization
        content_texts = []
        node_ids = []
        
        for node_id, data in content_graph.nodes(data=True):
            if data.get('type') in ['post', 'page'] and data.get('content'):
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

