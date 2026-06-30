import argparse
import json
import meilisearch
import sys

def clean_chunk_id(chunk_id):
    if chunk_id is None:
        return ""
    return str(chunk_id).replace('.', '_').replace('/', '_')

def process_record(record, source_file):
    # Clean chunk_id
    if 'chunk_id' in record:
        record['chunk_id'] = clean_chunk_id(record['chunk_id'])
    
    # Fill None fields with ""
    for key, value in record.items():
        if value is None:
            record[key] = ""
            
    # Add source_file
    record['source_file'] = source_file
    return record

def main():
    parser = argparse.ArgumentParser(description="Index JSONL into MeiliSearch")
    parser.add_argument("file_path", help="Path to JSONL file")
    parser.add_argument("--source-file", required=True, help="Source file name")
    args = parser.parse_args()

    client = meilisearch.Client('http://localhost:7700', 'ayurveda-dev-key')
    index = client.index('ayurveda')

    batch_size = 500
    documents = []
    
    print(f"Reading {args.file_path} for {args.source_file}...")
    try:
        with open(args.file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                processed_record = process_record(record, args.source_file)
                documents.append(processed_record)
                
                if len(documents) >= batch_size:
                    print(f"Uploading batch of {len(documents)} documents...")
                    task = index.add_documents(documents)
                    client.wait_for_task(task.task_uid, timeout_in_ms=300000)
                    task_info = client.get_task(task.task_uid)
                    if task_info.status == 'failed':
                        print(f"Error indexing batch: {task_info.error}")
                        sys.exit(1)
                    documents = []

        if documents:
            print(f"Uploading final batch of {len(documents)} documents...")
            task = index.add_documents(documents)
            client.wait_for_task(task.task_uid, timeout_in_ms=300000)
            task_info = client.get_task(task.task_uid)
            if task_info.status == 'failed':
                print(f"Error indexing batch: {task_info.error}")
                sys.exit(1)
                
        print(f"Indexing complete for {args.source_file}.")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
