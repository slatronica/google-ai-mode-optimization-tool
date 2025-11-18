"""WordPress Query Fan-Out SEO Analyzer - Main entry point"""
import logging
from wordpress_fetcher import WordPressFetcher
from graph_builder import GraphBuilder
from ai_analyzer import AIAnalyzer
from content_analyzer import ContentAnalyzer
from report_generator import ReportGenerator

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WordPressQueryFanOutAnalyzer:
    """Analyze WordPress sites for Google AI Mode query fan-out optimization"""
    
    def __init__(self, site_url: str, claude_api_key: str, claude_model: str = "claude-sonnet-4-5"):
        self.site_url = site_url.rstrip('/')
        logger.info(f"Initialized analyzer for {self.site_url}")
        
        # Initialize components
        self.fetcher = WordPressFetcher(self.site_url)
        self.graph_builder = GraphBuilder(self.site_url)
        self.ai_analyzer = AIAnalyzer(claude_api_key, claude_model)
        self.content_analyzer = ContentAnalyzer()
        self.report_generator = ReportGenerator()
        
        # Store graph reference
        self.content_graph = self.graph_builder.content_graph
    
    def generate_optimization_report(self) -> dict:
        """Generate comprehensive optimization report"""
        logger.info("Generating optimization report...")
        
        # Fetch and analyze content
        content = self.fetcher.fetch_all_content()
        self.graph_builder.build_content_graph(content)
        self.content_graph = self.graph_builder.content_graph
        
        # Run analyses
        query_patterns = self.ai_analyzer.analyze_query_patterns(self.site_url, self.content_graph)
        depth_analysis = self.content_analyzer.analyze_content_depth(self.content_graph)
        
        # Generate report
        report = self.report_generator.generate_optimization_report(
            self.site_url, content, self.content_graph, query_patterns, depth_analysis
        )
        
        return report
    
    def export_report(self, report: dict, filename: str = 'seo_analysis_report.json'):
        """Export report to JSON file"""
        self.report_generator.export_report(report, filename)
    
    def visualize_content_graph(self, output_file: str = 'content_graph.html'):
        """Create an interactive visualization of the content graph"""
        self.report_generator.visualize_content_graph(self.content_graph, output_file)


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
