import meilisearch
import time
import sys

# Configure stdout to handle UTF-8 characters like Sanskrit diacritics
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    client = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')
    index = client.index('ayurveda')

    # Wait for any pending tasks to complete before querying
    tasks = client.get_tasks({'statuses': ['enqueued', 'processing']})
    while tasks.results:
        print("Waiting for pending tasks to finish...")
        time.sleep(2)
        tasks = client.get_tasks({'statuses': ['enqueued', 'processing']})

    print("\n--- Running Hybrid Search Test ---")
    results = index.search('vata dosha jwara treatment', {
        'hybrid': {
            'semanticRatio': 0.5,
            'embedder': 'default'
        },
        'attributesToHighlight': ['commentary'],
        'limit': 3
    })

    for hit in results['hits']:
        print(f"\nChunk ID: {hit.get('chunk_id')}")
        print(f"Source: {hit.get('source_file')} - {hit.get('chapter_title')} ({hit.get('sthana')})")
        
        formatted_commentary = hit.get('_formatted', {}).get('commentary', hit.get('commentary', ''))
        if len(formatted_commentary) > 200:
            formatted_commentary = formatted_commentary[:200] + "..."
            
        print(f"Highlighted Commentary: {formatted_commentary}")

    print("\n--- Index Stats ---")
    # Get total document count
    stats = index.get_stats()
    print(f"Total documents: {stats.number_of_documents}")

    # Use facet distribution to get counts per source_file
    facet_results = index.search('', {
        'facets': ['source_file'],
        'limit': 0
    })
    
    distribution = facet_results.get('facetDistribution', {}).get('source_file', {})
    for source, count in distribution.items():
        print(f"  - {source}: {count} documents")

if __name__ == "__main__":
    main()
