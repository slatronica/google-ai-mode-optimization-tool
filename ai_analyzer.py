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

IMPORTANT: Respond with ONLY valid JSON, no markdown code blocks, no explanations before or after.

Provide analysis in this exact JSON format:
{{
  "complex_queries": ["query 1", "query 2"],
  "decompositions": {{
    "query 1": ["sub-query 1", "sub-query 2"],
    "query 2": ["sub-query 3", "sub-query 4"]
  }},
  "coverage_analysis": {{
    "query 1": {{
      "sub-query 1": ["content title that answers this"],
      "sub-query 2": []
    }}
  }},
  "gaps": ["missing sub-query 1", "missing sub-query 2"],
  "opportunities": ["opportunity 1", "opportunity 2"]
}}"""

        try:
            response = self.claude.messages.create(
                model=self.claude_model,
                max_tokens=8000,  # Increased for comprehensive analysis
                messages=[{"role": "user", "content": prompt}]
            )
            
            # Parse Claude's response - handle both old and new response formats
            response_text = ""
            if hasattr(response, 'content') and len(response.content) > 0:
                # Handle text content blocks
                content_block = response.content[0]
                if hasattr(content_block, 'text'):
                    response_text = content_block.text
                elif isinstance(content_block, dict):
                    if 'text' in content_block:
                        response_text = content_block['text']
                    else:
                        logger.warning(f"Unexpected content block structure: {list(content_block.keys())}")
                        response_text = str(content_block)
                else:
                    # Fallback: try to get text from response directly
                    response_text = str(content_block)
                    logger.debug(f"Using string conversion of content block: {type(content_block)}")
            else:
                logger.warning(f"Unexpected response format from Claude API. Response type: {type(response)}")
                if hasattr(response, '__dict__'):
                    logger.debug(f"Response attributes: {list(response.__dict__.keys())}")
                return patterns
            
            logger.debug(f"Claude raw response (first 500 chars): {response_text[:500]}")
            
            analysis = self.parse_claude_response(response_text)
            logger.debug(f"Parsed analysis keys: {list(analysis.keys())}")
            
            # Merge analysis into patterns, handling different field name variations
            if 'complex_queries' in analysis and analysis['complex_queries']:
                patterns['complex_queries'] = analysis['complex_queries']
                logger.info(f"Found {len(patterns['complex_queries'])} complex queries")
            
            if 'decompositions' in analysis and analysis['decompositions']:
                patterns['decompositions'] = analysis['decompositions']
                logger.info(f"Found decompositions for {len(patterns['decompositions'])} queries")
            else:
                logger.warning("No decompositions found in Claude response")
            
            # Handle both 'coverage_analysis' and 'current_coverage' field names
            if 'coverage_analysis' in analysis and analysis['coverage_analysis']:
                patterns['coverage_analysis'] = analysis['coverage_analysis']
                logger.info(f"Found coverage analysis for {len(patterns['coverage_analysis'])} queries")
            elif 'current_coverage' in analysis and analysis['current_coverage']:
                patterns['coverage_analysis'] = analysis['current_coverage']
                logger.info(f"Found current_coverage (mapped to coverage_analysis)")
            else:
                logger.warning("No coverage_analysis found in Claude response")
            
            # Handle both 'opportunities' and 'recommendations' field names
            if 'opportunities' in analysis and analysis['opportunities']:
                patterns['opportunities'] = analysis['opportunities']
                logger.info(f"Found {len(patterns['opportunities'])} opportunities")
            elif 'recommendations' in analysis and analysis['recommendations']:
                patterns['opportunities'] = analysis['recommendations']
                logger.info(f"Found recommendations (mapped to opportunities)")
            else:
                logger.warning("No opportunities found in Claude response")
            
            if 'gaps' in analysis and analysis['gaps']:
                patterns['gaps'] = analysis['gaps']
                logger.info(f"Found {len(patterns['gaps'])} gaps")
            else:
                logger.warning("No gaps found in Claude response")
                patterns['gaps'] = []  # Ensure it's always a list
            
        except Exception as e:
            logger.error(f"Error analyzing with Claude: {e}", exc_info=True)
        
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
            # Remove markdown code blocks if present
            cleaned_text = response_text.strip()
            if cleaned_text.startswith('```'):
                # Remove markdown code block markers
                cleaned_text = re.sub(r'^```(?:json)?\s*', '', cleaned_text, flags=re.MULTILINE)
                cleaned_text = re.sub(r'\s*```\s*$', '', cleaned_text, flags=re.MULTILINE)
            
            # Try to extract JSON from response - look for the outermost JSON object
            json_match = re.search(r'\{[\s\S]*\}', cleaned_text)
            if json_match:
                json_str = json_match.group()
                parsed = json.loads(json_str)
                logger.info(f"Successfully parsed JSON with keys: {list(parsed.keys())}")
                return parsed
            else:
                logger.warning("No JSON object found in response, using fallback parsing")
                return self.fallback_parse(response_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error: {e}, attempting fallback parsing")
            logger.debug(f"Problematic JSON text: {response_text[:500]}")
            return self.fallback_parse(response_text)
        except Exception as e:
            logger.error(f"Unexpected error parsing response: {e}", exc_info=True)
            return self.fallback_parse(response_text)
    
    def fallback_parse(self, text: str) -> Dict:
        """Fallback parsing if JSON extraction fails"""
        logger.warning("Using fallback parsing - Claude response may not have been valid JSON")
        return {
            'complex_queries': re.findall(r'"([^"]+\?)"', text) or re.findall(r'([^"]+\?)', text),
            'decompositions': {},
            'coverage_analysis': {},
            'gaps': [],
            'opportunities': []
        }

