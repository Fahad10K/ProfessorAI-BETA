"""
ChromaDB Data Extraction Script
Extracts all chunks and metadata from ChromaDB Cloud for review and debugging

This script helps diagnose:
- Data drift issues
- Missing or corrupted chunks
- Metadata problems
- Embedding quality issues
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_chromadb_data() -> Dict[str, Any]:
    """
    Extract all data from ChromaDB Cloud collection.
    
    Returns:
        Dict containing:
        - collection_info: metadata about the collection
        - chunks: list of all document chunks with metadata
        - statistics: summary statistics
    """
    
    logger.info("=" * 80)
    logger.info("ChromaDB Data Extraction Tool")
    logger.info("=" * 80)
    
    try:
        # Import ChromaDB Cloud components
        from core.cloud_vectorizer import CloudVectorizer
        
        logger.info(f"\n📊 Collection: {config.CHROMA_COLLECTION_NAME}")
        logger.info(f"🔗 Tenant: {config.CHROMA_CLOUD_TENANT}")
        logger.info(f"🗄️ Database: {config.CHROMA_CLOUD_DATABASE}")
        
        # Initialize CloudVectorizer
        logger.info("\n🔄 Connecting to ChromaDB Cloud...")
        cloud_vectorizer = CloudVectorizer()
        vector_store = cloud_vectorizer.get_vector_store()
        
        if not vector_store:
            logger.error("❌ Failed to connect to ChromaDB Cloud")
            return {
                "error": "Failed to connect to ChromaDB Cloud",
                "collection_info": None,
                "chunks": [],
                "statistics": {}
            }
        
        # Get the ChromaDB collection
        collection = vector_store._collection
        
        # Get collection metadata
        logger.info("\n📋 Fetching collection metadata...")
        collection_metadata = collection.metadata if hasattr(collection, 'metadata') else {}
        doc_count = collection.count()
        
        logger.info(f"✅ Connected successfully!")
        logger.info(f"📊 Total documents: {doc_count}")
        
        # Extract all documents with pagination (ChromaDB has limits)
        logger.info(f"\n📦 Extracting all {doc_count} chunks and metadata...")
        logger.info("⏳ This may take a few minutes for large collections...")
        
        # ChromaDB limits results, so we need to paginate
        batch_size = 300  # Fetch 5000 at a time
        all_ids = []
        all_documents = []
        all_metadatas = []
        all_embeddings = []
        
        offset = 0
        while offset < doc_count:
            logger.info(f"  Fetching batch {offset // batch_size + 1} (items {offset} - {min(offset + batch_size, doc_count)})...")
            
            result = collection.get(
                limit=batch_size,
                offset=offset,
                include=['documents', 'metadatas', 'embeddings']
            )
            
            batch_ids = result.get('ids', [])
            if not batch_ids:  # No more results
                break
            
            all_ids.extend(batch_ids)
            all_documents.extend(result.get('documents', []))
            all_metadatas.extend(result.get('metadatas', []))
            all_embeddings.extend(result.get('embeddings', []))
            
            offset += len(batch_ids)
            
            if len(batch_ids) < batch_size:  # Last batch
                break
        
        logger.info(f"✅ Retrieved {len(all_documents)} total chunks")
        
        # Process results
        chunks = []
        
        # Format chunks for JSON export
        for idx, (chunk_id, doc, meta, emb) in enumerate(zip(all_ids, all_documents, all_metadatas, all_embeddings)):
            # Fix numpy array check - use 'is not None' and check length
            emb_dim = 0
            emb_sample = None
            
            if emb is not None:
                try:
                    emb_dim = len(emb)
                    emb_sample = emb[:5] if emb_dim > 5 else emb
                    # Convert numpy array to list for JSON serialization
                    if hasattr(emb_sample, 'tolist'):
                        emb_sample = emb_sample.tolist()
                except:
                    emb_dim = 0
                    emb_sample = None
            
            chunk_data = {
                'id': chunk_id,
                'chunk_number': idx + 1,
                'content': doc,
                'content_length': len(doc),
                'metadata': meta or {},
                'embedding_dimensions': emb_dim,
                'embedding_sample': emb_sample
            }
            chunks.append(chunk_data)
        
        # Calculate statistics
        logger.info("\n📊 Calculating statistics...")
        
        content_lengths = [len(doc) for doc in all_documents]
        sources = set()
        chunk_ids = set()
        
        for meta in all_metadatas:
            if meta:
                if 'source' in meta:
                    sources.add(meta['source'])
                if 'chunk_id' in meta:
                    chunk_ids.add(str(meta['chunk_id']))
        
        # Get embedding dimension safely
        emb_dimension = 0
        if all_embeddings and len(all_embeddings) > 0:
            try:
                emb_dimension = len(all_embeddings[0])
            except:
                emb_dimension = 0
        
        statistics = {
            'total_chunks': len(all_documents),
            'unique_sources': len(sources),
            'unique_chunk_ids': len(chunk_ids),
            'avg_chunk_length': sum(content_lengths) / len(content_lengths) if content_lengths else 0,
            'min_chunk_length': min(content_lengths) if content_lengths else 0,
            'max_chunk_length': max(content_lengths) if content_lengths else 0,
            'embedding_dimension': emb_dimension,
            'sources_list': sorted(list(sources))
        }
        
        # Print statistics
        logger.info(f"\n📈 Statistics:")
        logger.info(f"  • Total chunks: {statistics['total_chunks']}")
        logger.info(f"  • Unique sources: {statistics['unique_sources']}")
        logger.info(f"  • Unique chunk IDs: {statistics['unique_chunk_ids']}")
        logger.info(f"  • Average chunk length: {statistics['avg_chunk_length']:.0f} chars")
        logger.info(f"  • Min chunk length: {statistics['min_chunk_length']} chars")
        logger.info(f"  • Max chunk length: {statistics['max_chunk_length']} chars")
        logger.info(f"  • Embedding dimensions: {statistics['embedding_dimension']}")
        logger.info(f"\n📚 Sources found:")
        for source in statistics['sources_list']:
            logger.info(f"  • {source}")
        
        # Prepare export data
        export_data = {
            'extraction_timestamp': datetime.utcnow().isoformat(),
            'collection_info': {
                'name': config.CHROMA_COLLECTION_NAME,
                'tenant': config.CHROMA_CLOUD_TENANT,
                'database': config.CHROMA_CLOUD_DATABASE,
                'metadata': collection_metadata,
                'total_documents': doc_count
            },
            'statistics': statistics,
            'chunks': chunks
        }
        
        return export_data
        
    except Exception as e:
        logger.error(f"❌ Error extracting ChromaDB data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'error': str(e),
            'collection_info': None,
            'chunks': [],
            'statistics': {}
        }


def save_to_json(data: Dict[str, Any], filename: str = None):
    """Save extracted data to JSON file."""
    
    if filename is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chromadb_export_{timestamp}.json"
    
    logger.info(f"\n💾 Saving to {filename}...")
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Successfully saved to {filename}")
        logger.info(f"📁 File size: {len(json.dumps(data)) / 1024:.2f} KB")
        
        return filename
        
    except Exception as e:
        logger.error(f"❌ Error saving to JSON: {e}")
        return None


def analyze_data_drift(chunks: List[Dict[str, Any]]):
    """Analyze potential data drift issues."""
    
    logger.info("\n🔍 Analyzing for data drift issues...")
    
    issues = []
    
    # Check for empty chunks
    empty_chunks = [c for c in chunks if not c['content'].strip()]
    if empty_chunks:
        issues.append(f"⚠️ Found {len(empty_chunks)} empty chunks")
    
    # Check for very short chunks (< 50 chars)
    short_chunks = [c for c in chunks if c['content_length'] < 50]
    if short_chunks:
        issues.append(f"⚠️ Found {len(short_chunks)} very short chunks (< 50 chars)")
    
    # Check for missing metadata
    no_metadata = [c for c in chunks if not c['metadata']]
    if no_metadata:
        issues.append(f"⚠️ Found {len(no_metadata)} chunks without metadata")
    
    # Check for missing source in metadata
    no_source = [c for c in chunks if c['metadata'] and 'source' not in c['metadata']]
    if no_source:
        issues.append(f"⚠️ Found {len(no_source)} chunks without 'source' in metadata")
    
    # Check for duplicate content
    content_map = {}
    for c in chunks:
        content_hash = hash(c['content'])
        if content_hash in content_map:
            content_map[content_hash] += 1
        else:
            content_map[content_hash] = 1
    
    duplicates = sum(1 for count in content_map.values() if count > 1)
    if duplicates > 0:
        issues.append(f"⚠️ Found {duplicates} duplicate content chunks")
    
    if issues:
        logger.info("\n⚠️ Data Quality Issues Found:")
        for issue in issues:
            logger.info(f"  {issue}")
    else:
        logger.info("\n✅ No data quality issues detected")
    
    return issues


def main():
    """Main execution function."""
    
    print("\n" + "=" * 80)
    print("ChromaDB Data Extraction & Analysis Tool")
    print("=" * 80 + "\n")
    
    # Extract data
    data = extract_chromadb_data()
    
    if 'error' in data and data['error']:
        logger.error(f"\n❌ Extraction failed: {data['error']}")
        return
    
    # Analyze for data drift
    if data['chunks']:
        analyze_data_drift(data['chunks'])
    
    # Save to JSON
    filename = save_to_json(data)
    
    if filename:
        logger.info("\n" + "=" * 80)
        logger.info("✅ Extraction Complete!")
        logger.info("=" * 80)
        logger.info(f"\n📄 Review the data in: {filename}")
        logger.info(f"📊 Total chunks extracted: {len(data['chunks'])}")
        logger.info("\n💡 Next Steps:")
        logger.info("  1. Open the JSON file to review chunk content")
        logger.info("  2. Check for missing or corrupted data")
        logger.info("  3. Verify metadata is correct")
        logger.info("  4. Look for any unexpected patterns")
    
    return data


if __name__ == "__main__":
    main()


def main():
    """Main execution function."""
    
    print("\n" + "=" * 80)
    print("ChromaDB Data Extraction & Analysis Tool")
    print("=" * 80 + "\n")
    
    # Extract data
    data = extract_chromadb_data()
    
    if 'error' in data and data['error']:
        logger.error(f"\n❌ Extraction failed: {data['error']}")
        return
    
    # Analyze for data drift
    if data['chunks']:
        analyze_data_drift(data['chunks'])
    
    # Save to JSON
    filename = save_to_json(data)
    
    if filename:
        logger.info("\n" + "=" * 80)
        logger.info("✅ Extraction Complete!")
        logger.info("=" * 80)
        logger.info(f"\n📄 Review the data in: {filename}")
        logger.info(f"📊 Total chunks extracted: {len(data['chunks'])}")
        logger.info("\n💡 Next Steps:")
        logger.info("  1. Open the JSON file to review chunk content")
        logger.info("  2. Check for missing or corrupted data")
        logger.info("  3. Verify metadata is correct")
        logger.info("  4. Look for any unexpected patterns")
    
    return data


if __name__ == "__main__":
    main()
