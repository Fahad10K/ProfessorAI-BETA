import chromadb
import os
from dotenv import load_dotenv

def check_chromadb_cloud():
    """
    Connects to ChromaDB Cloud and inspects the collection.
    """
    # Load environment variables from .env file
    print("Loading environment variables from .env file...")
    load_dotenv()

    try:
        # --- 1. Configuration ---
        api_key = os.getenv("CHROMA_CLOUD_API_KEY")
        tenant = os.getenv("CHROMA_CLOUD_TENANT")
        database = os.getenv("CHROMA_CLOUD_DATABASE")
        collection_name = "profai_documents"  # As defined in your project

        if not all([api_key, tenant, database]):
            print("\n❌ Error: ChromaDB Cloud credentials are not fully configured in the .env file.")
            print("Please ensure CHROMA_CLOUD_API_KEY, CHROMA_CLOUD_TENANT, and CHROMA_CLOUD_DATABASE are set.")
            return

        print("\nConnecting to ChromaDB Cloud...")
        
        # --- 2. Connect to Client ---
        client = chromadb.CloudClient(
            api_key=api_key,
            tenant=tenant,
            database=database
        )
        
        print(f"✅ Connected successfully!")
        
        # --- 3. Get the Collection ---
        print(f"Fetching collection: '{collection_name}'...")
        collection = client.get_collection(name=collection_name)
        
        # --- 4. Get Total Count ---
        total_items = collection.count()
        print(f"\n📊 Total items (chunks) in the collection: {total_items}")
        
        # --- 5. Get Unique Sources ---
        if total_items > 0:
            print("\n🔍 Finding unique sources...")
            print(f"Fetching metadata for all {total_items} items in batches. This may take a moment...")
            all_metadata = []
            batch_size = 300  # ChromaDB Cloud's 'Get' limit
            for offset in range(0, total_items, batch_size):
                print(f"  Fetching batch from offset {offset}...")
                batch = collection.get(
                    limit=batch_size,
                    offset=offset,
                    include=["metadatas"]
                )
                all_metadata.extend(batch["metadatas"])
            print("✅ All metadata fetched.")
            
            sources = set()
            for meta in all_metadata:
                if 'source' in meta:
                    sources.add(meta['source'])
            
            if sources:
                print("Found the following unique sources:")
                for i, source_name in enumerate(sorted(list(sources))):
                    print(f"  {i + 1}. {source_name}")
            else:
                print("No documents with a 'source' metadata field found.")
        else:
            print("Collection is empty.")

    except Exception as e:
        print(f"\n💥 An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Make sure you have python-dotenv installed: pip install python-dotenv
    check_chromadb_cloud()
