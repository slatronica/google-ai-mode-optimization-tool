# WordPress Query Fan-Out SEO Analyzer

A comprehensive tool that analyzes WordPress sites for Google AI Mode optimization using query decomposition and multi-hop reasoning strategies.

## Features

- **WordPress Content Crawling**: Fetches all posts, pages, categories, and tags via WordPress REST API or sitemap.xml
- **Sitemap Support**: Can crawl via sitemap.xml when REST API is blocked or unavailable (handles nested sitemaps)
- **Content Graph Construction**: Builds a knowledge graph of your site's content and internal links
- **Query Pattern Analysis**: Uses Claude AI to identify complex queries and decomposition opportunities
- **Semantic Clustering**: Groups related content using TF-IDF vectorization
- **Multi-Source Optimization**: Identifies content that can serve multiple Google source types
- **Actionable Recommendations**: Provides specific steps to optimize for query fan-out
- **Visual Graph Export**: Creates interactive visualization of your content network
- **Timestamped Reports**: All reports are saved in `reports/` directory with timestamps to prevent overwriting

## Installation

```bash
# Clone or download app.py
# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage (REST API Mode)

```bash
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY
```

### Sitemap Mode

When the WordPress REST API is blocked or unavailable, use sitemap mode:

```bash
# Use default sitemap.xml
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --sitemap

# Specify custom sitemap URL
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --sitemap https://yoursite.com/custom-sitemap.xml

# Or use relative path
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --sitemap sitemap-index.xml
```

### All Options

```bash
# Custom output file name (will be timestamped automatically)
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --output my_report.json

# Generate visualization
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --visualize

# Use different Claude model
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --model claude-3-opus-20240229

# Enable debug logging
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --debug

# Combine options
python app.py https://yourwordpresssite.com YOUR_CLAUDE_API_KEY --sitemap --output site_analysis.json --visualize --debug
```

### Command Line Arguments

- `site_url` (required): WordPress site URL to analyze
- `claude_api_key` (required): Your Claude API key
- `--output`: Output file name (default: `seo_report.json`)
  - Files are automatically saved in `reports/` directory with timestamps
  - Example: `reports/seo_report_20241118_143022.json`
- `--sitemap`: Use sitemap crawling instead of REST API
  - Optional: specify sitemap URL (default: `sitemap.xml`)
  - Handles nested sitemaps automatically
- `--visualize`: Generate interactive HTML graph visualization
  - Saved in `reports/` directory with timestamp
- `--model`: Claude model to use (default: `claude-sonnet-4-5`)
  - Options: `claude-3-opus-20240229`, `claude-3-haiku-20240307`, `claude-3-5-haiku-20241022`
- `--debug`: Enable verbose debug logging

## Getting Your Claude API Key

1. Sign up at https://console.anthropic.com
2. Go to API Keys section
3. Create a new API key
4. Copy and use in the command

## What the Analyzer Does

### 1. Content Fetching
- **REST API Mode**: Retrieves all published posts and pages via WordPress REST API
- **Sitemap Mode**: Crawls sitemap.xml to discover all URLs, then fetches and parses HTML content
  - Automatically handles nested sitemaps (sitemap index files)
  - Extracts title, content, categories, and tags from HTML
- Fetches categories, tags, and media information
- Respects rate limits to avoid overloading your server

### 2. Graph Construction
- Creates nodes for each piece of content
- Maps internal links as edges
- Identifies content relationships through categories/tags

### 3. Query Analysis with Claude
- Sends content samples to Claude API
- Identifies potential complex user queries
- Predicts how Google would decompose these queries
- Finds gaps in sub-query coverage

### 4. Content Depth Analysis
- Scores each piece of content for depth and comprehensiveness
- Identifies potential hub pages
- Finds orphaned content with no internal links
- Discovers semantic content clusters

### 5. Recommendation Generation
- Content gaps for unanswered sub-queries
- Internal linking opportunities
- Hub page optimization suggestions
- Semantic bridge creation recommendations

## Output Report Structure

```json
{
  "site_url": "https://example.com",
  "analysis_date": "2024-01-15T10:30:00",
  "summary": {
    "total_posts": 156,
    "total_pages": 23,
    "content_nodes": 205,
    "internal_links": 432,
    "orphan_content": 12,
    "hub_pages": 5,
    "semantic_clusters": 8
  },
  "query_optimization": {
    "complex_queries": [
      "How do I set up WooCommerce with custom shipping zones for international orders?"
    ],
    "decompositions": {
      "query_1": [
        "What is WooCommerce?",
        "How to install WooCommerce?",
        "What are shipping zones?",
        "How to set up international shipping?"
      ]
    },
    "gaps": [
      "No content about shipping zones",
      "Missing international shipping guide"
    ]
  },
  "recommendations": [
    {
      "type": "content_gap",
      "priority": "high",
      "action": "Create new content",
      "details": "Create content to answer sub-query: What are shipping zones?",
      "impact": "Enables multi-hop reasoning path"
    }
  ],
  "action_plan": {
    "immediate": [...],
    "short_term": [...],
    "long_term": [...]
  }
}
```

## Interpreting Results

### Content Gaps
These are sub-queries that Google might generate but your site doesn't answer. Creating this content enables Google to use your site in multi-hop reasoning.

### Orphan Content
Valuable content that isn't well-connected to your site's graph. Adding internal links helps Google traverse your content.

### Hub Pages
Pages with high potential to serve as central nodes in query paths. Optimizing these strengthens your site's authority.

### Semantic Clusters
Groups of related content that should be better interconnected to support query fan-out.

## Output Files

All reports and visualizations are automatically saved in the `reports/` directory with timestamps:

- **JSON Reports**: `reports/[filename]_YYYYMMDD_HHMMSS.json`
- **HTML Visualizations**: `reports/content_graph_YYYYMMDD_HHMMSS.html`

This ensures previous reports are never overwritten and you can track changes over time.

## Visualization

If you use the `--visualize` flag, the tool generates an interactive HTML graph showing:
- Blue nodes: Posts
- Orange nodes: Pages  
- Green nodes: Categories
- Red nodes: Tags
- Node size: Based on number of connections
- Edges: Internal links and relationships

The visualization is saved in the `reports/` directory with a timestamp.

## Best Practices

1. **Run Regularly**: Monthly analysis helps track improvements
2. **Focus on High-Priority**: Address "immediate" recommendations first
3. **Create Sub-Query Content**: Each piece should comprehensively answer one specific question
4. **Build Semantic Bridges**: Connect related content with contextual internal links
5. **Monitor Results**: Track performance in Google Search Console

## Troubleshooting

### REST API Blocked (403 Forbidden)
If you get a 403 error when using REST API mode, try sitemap mode instead:
```bash
python app.py https://yoursite.com YOUR_API_KEY --sitemap
```

Common causes:
- Cloudflare bot protection
- WordPress security plugins (Wordfence, iThemes Security)
- Server-level restrictions

### API Rate Limits
If you hit rate limits, the tool automatically slows down. For large sites, the analysis may take 10-20 minutes.

### Memory Issues
For very large sites (1000+ posts), you may need to modify the code to process in batches.

### Claude API Errors
Ensure your API key is valid and you have sufficient credits. Check the model name is correct for your account.

### Sitemap Issues
- Ensure `sitemap.xml` is accessible at the root of your site
- For custom sitemap locations, specify the full URL: `--sitemap https://yoursite.com/custom-sitemap.xml`
- The tool automatically handles nested sitemaps (sitemap index files)

## Example Use Cases

### E-commerce Site
Identifies complex product queries and ensures all comparison factors are covered.

### Tech Blog
Finds tutorial series that need better interconnection for step-by-step learning paths.

### Service Business
Discovers service-related questions that require multiple pages to answer fully.

## Advanced Usage

### Custom Analysis
Modify the `analyze_query_patterns()` method to focus on specific query types relevant to your niche.

### Export Formats
Extend the `export_report()` method to output in different formats (CSV, HTML, etc.).

### Integration
Use the report data to automatically create content briefs or update your content calendar.

## Support

For issues or questions:
1. **REST API Mode**: Check WordPress REST API is enabled: `https://yoursite.com/wp-json/`
2. **Sitemap Mode**: Verify sitemap is accessible: `https://yoursite.com/sitemap.xml`
3. Verify Claude API key is active
4. Ensure Python dependencies are installed correctly: `pip install -r requirements.txt`
5. Use `--debug` flag for detailed logging: `python app.py ... --debug`

## License

MIT License - Feel free to modify and use for your SEO optimization needs.
