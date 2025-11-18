"""Claude AI analysis for query pattern identification"""
import json
import re
import anthropic
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Handles Claude AI analysis for query optimization"""
    
    def __init__(self, claude_api_key: str, claude_model: str = "claude-sonnet-4-5"):
        self.claude = anthropic.Anthropic(api_key=claude_api_key)
        self.claude_model = claude_model
    
    def analyze_query_patterns(self, site_url: str, content_graph) -> Dict:
        """Analyze content for complex query patterns using Claude"""
        logger.info("Analyzing query patterns with Claude API...")
        
        patterns = {
            'complex_queries': [],
            'decompositions': {},
            'coverage_analysis': {},
            'opportunities': []
        }
        
        # Sample content for analysis
        sample_content = self.get_content_sample(content_graph)
        
        # Analyze with Claude
        prompt = f"""Analyze this WordPress site content for Google AI Mode query optimization opportunities.

Site URL: {site_url}

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
    
    def get_content_sample(self, content_graph) -> List[Dict]:
        """Get a representative sample of content"""
        sample = []
        
        for node_id, data in list(content_graph.nodes(data=True))[:20]:
            if data.get('type') in ['post', 'page']:
                sample.append({
                    'title': data.get('title', ''),
                    'type': data.get('type', ''),
                    'excerpt': data.get('excerpt', '')[:200],
                    'url': data.get('url', '')
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

