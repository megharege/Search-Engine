import meilisearch
import time

def setup_meilisearch():
    # Connect to Meilisearch
    client = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')

    # Wait for Meilisearch to be ready
    for _ in range(10):
        try:
            if client.is_healthy():
                break
        except Exception:
            time.sleep(1)
    else:
        print("Meilisearch is not ready.")
        return

    print("Creating index 'ayurveda'...")
    try:
        task = client.create_index('ayurveda', {'primaryKey': 'chunk_id'})
        client.wait_for_task(task.task_uid, timeout_in_ms=600000)
    except meilisearch.errors.MeilisearchApiError as e:
        if e.code == 'index_already_exists':
            print("Index already exists.")
        else:
            raise e

    index = client.index('ayurveda')

    settings = {
        'searchableAttributes': [
            'topic_heading',
            'transliteration',
            'commentary',
            'sanskrit_text',
            'chapter_title',
            'sthana'
        ],
        'filterableAttributes': [
            'source_file',
            'sthana',
            'chapter_number',
            'primary_category',
            'categories_found'
        ],
        'sortableAttributes': [
            'chapter_number'
        ],
        'embedders': {
            'default': {
                'source': 'huggingFace',
                'model': 'intfloat/multilingual-e5-small',
                'documentTemplate': '{{doc.topic_heading}} {{doc.transliteration}} {{doc.commentary}}'
            }
        },
        'typoTolerance': {
            'enabled': True,
            'disableOnAttributes': ['sanskrit_text', 'transliteration']
        }
    }

    print("Updating settings...")
    task = index.update_settings(settings)
    client.wait_for_task(task.task_uid, timeout_in_ms=600000)
    
    print("Settings updated successfully.")
    print("Settings:", index.get_settings())

if __name__ == "__main__":
    setup_meilisearch()
