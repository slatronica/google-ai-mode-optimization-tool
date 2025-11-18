"""Report generation and export"""
import json
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates optimization reports and recommendations"""
    
    def generate_optimization_report(self, site_url: str, content: Dict, content_graph, 
                                   query_patterns: Dict, depth_analysis: Dict) -> Dict:
        """Generate comprehensive optimization report"""
        logger.info("Generating optimization report...")
        
        # Generate recommendations
        recommendations = self.generate_recommendations(query_patterns, depth_analysis)
        
        # Compile report
        report = {
            'site_url': site_url,
            'analysis_date': datetime.now().isoformat(),
            'summary': {
                'total_posts': len(content['posts']),
                'total_pages': len(content['pages']),
                'content_nodes': content_graph.number_of_nodes(),
                'internal_links': content_graph.number_of_edges(),
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
    
    def visualize_content_graph(self, content_graph, output_file: str = 'content_graph.html'):
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
        
        for node_id, data in content_graph.nodes(data=True):
            nt.add_node(
                node_id,
                label=data.get('title', data.get('name', str(node_id)))[:30],
                color=color_map.get(data.get('type', ''), '#gray'),
                title=data.get('url', ''),
                size=20 + content_graph.degree(node_id) * 2
            )
        
        # Add edges
        for source, target in content_graph.edges():
            nt.add_edge(source, target)
        
        # Generate HTML
        nt.save_graph(output_file)
        logger.info(f"Content graph visualization saved to {output_file}")

