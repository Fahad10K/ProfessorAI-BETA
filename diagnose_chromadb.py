"""
ChromaDB Diagnostic Script
Verify the state of ChromaDB Cloud collection and inspect documents
"""

import os
import sys
from dotenv import load_dotenv
import chromadb
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables
load_dotenv()

# Configuration
CHROMA_CLOUD_API_KEY = os.getenv("CHROMA_CLOUD_API_KEY")
CHROMA_CLOUD_TENANT = os.getenv("CHROMA_CLOUD_TENANT")
CHROMA_CLOUD_DATABASE = os.getenv("CHROMA_CLOUD_DATABASE")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "profai_documents")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")

def main():
    print("=" * 80)
    print("🔍 CHROMADB CLOUD DIAGNOSTIC TOOL")
    print("=" * 80)
    print()
    
    # Step 1: Verify environment variables
    print("📋 STEP 1: Verifying Configuration")
    print("-" * 80)
    
    missing = []
    if not CHROMA_CLOUD_API_KEY:
        missing.append("CHROMA_CLOUD_API_KEY")
    if not CHROMA_CLOUD_TENANT:
        missing.append("CHROMA_CLOUD_TENANT")
    if not CHROMA_CLOUD_DATABASE:
        missing.append("CHROMA_CLOUD_DATABASE")
    if not OPENAI_API_KEY:
        missing.append("OPENAI_API_KEY")
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   Please check your .env file")
        sys.exit(1)
    
    print(f"✅ CHROMA_CLOUD_TENANT: {CHROMA_CLOUD_TENANT}")
    print(f"✅ CHROMA_CLOUD_DATABASE: {CHROMA_CLOUD_DATABASE}")
    print(f"✅ CHROMA_COLLECTION_NAME: {CHROMA_COLLECTION_NAME}")
    print(f"✅ EMBEDDING_MODEL: {EMBEDDING_MODEL_NAME}")
    print()
    
    # Step 2: Connect to ChromaDB Cloud
    print("🔌 STEP 2: Connecting to ChromaDB Cloud")
    print("-" * 80)
    
    try:
        client = chromadb.CloudClient(
            api_key=CHROMA_CLOUD_API_KEY,
            tenant=CHROMA_CLOUD_TENANT,
            database=CHROMA_CLOUD_DATABASE
        )
        print("✅ Successfully connected to ChromaDB Cloud")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)
    print()
    
    # Step 3: List all collections
    print("📚 STEP 3: Listing Collections")
    print("-" * 80)
    
    try:
        collections = client.list_collections()
        print(f"Found {len(collections)} collections:")
        for coll in collections:
            print(f"  - {coll.name}")
        print()
    except Exception as e:
        print(f"❌ Failed to list collections: {e}")
        print()
    
    # Step 4: Check target collection
    print(f"🎯 STEP 4: Inspecting Collection '{CHROMA_COLLECTION_NAME}'")
    print("-" * 80)
    
    try:
        collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
        doc_count = collection.count()
        
        print(f"📊 Collection Statistics:")
        print(f"   - Name: {collection.name}")
        print(f"   - ID: {collection.id}")
        print(f"   - Document Count: {doc_count}")
        print()
        
        if doc_count == 0:
            print("❌ CRITICAL: Collection is EMPTY!")
            print("   This is the root cause of your RAG hallucination issue.")
            print("   The LLM has no context to work with, causing garbage output.")
            print()
            print("🔧 SOLUTION:")
            print("   1. Upload course PDFs using the /api/upload-pdfs endpoint")
            print("   2. Or add documents manually to ChromaDB")
            print()
            sys.exit(0)
        
        # Step 5: Sample documents
        print(f"📄 STEP 5: Sampling Documents (first 5)")
        print("-" * 80)
        
        # Get first 5 documents
        results = collection.get(
            limit=5,
            include=['documents', 'metadatas']
        )
        
        if results and results.get('documents'):
            docs = results['documents']
            metadatas = results.get('metadatas', [])
            
            for idx, (doc, meta) in enumerate(zip(docs, metadatas)):
                print(f"\n📝 Document {idx + 1}:")
                print(f"   Length: {len(doc)} characters")
                print(f"   Metadata: {meta}")
                print(f"   Preview: {doc[:200]}...")
                print()
        
        # Step 6: Test retrieval
        print(f"🔍 STEP 6: Testing Retrieval")
        print("-" * 80)
        
        # Initialize embeddings
        embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL_NAME,
            openai_api_key=OPENAI_API_KEY,
            chunk_size=200
        )
        
        # Create vector store
        vector_store = Chroma(
            client=client,
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings
        )
        
        # Test query
        test_query = "What is this course about?"
        print(f"Test query: '{test_query}'")
        print()
        
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 3})
        retrieved_docs = retriever.invoke(test_query)
        
        print(f"Retrieved {len(retrieved_docs)} documents:")
        for idx, doc in enumerate(retrieved_docs):
            print(f"\n   Doc {idx + 1}:")
            print(f"   Length: {len(doc.page_content)} chars")
            print(f"   Preview: {doc.page_content[:150]}...")
        print()
        
        # Step 7: Health Check Summary
        print("=" * 80)
        print("✅ CHROMADB HEALTH CHECK SUMMARY")
        print("=" * 80)
        print(f"✅ Connection: Working")
        print(f"✅ Collection: Exists")
        print(f"✅ Documents: {doc_count} documents")
        print(f"✅ Retrieval: Working")
        print()
        print("🎉 Your ChromaDB setup appears healthy!")
        print()
        
    except Exception as e:
        print(f"❌ Error inspecting collection: {e}")
        print()
        print("💡 This might mean the collection doesn't exist yet.")
        print("   You need to upload course content first.")
        sys.exit(1)

if __name__ == "__main__":
    main()
