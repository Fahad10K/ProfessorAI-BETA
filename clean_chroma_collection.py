import chromadb
import os
import json
from dotenv import load_dotenv

def interactive_cleanup():
    """
    Interactive cleanup for both ChromaDB collection and course_output.json
    """
    load_dotenv()
    
    try:
        # Connect to ChromaDB Cloud
        client = chromadb.CloudClient(
            api_key=os.getenv("CHROMA_CLOUD_API_KEY"),
            tenant=os.getenv("CHROMA_CLOUD_TENANT"),
            database=os.getenv("CHROMA_CLOUD_DATABASE")
        )
        
        collection_name = "profai_documents"
        collection = client.get_collection(name=collection_name)
        
        print(f"\n📊 Current ChromaDB collection size: {collection.count()}")
        
        # Get all items with metadata
        print("🔍 Fetching all documents...")
        all_items = collection.get(include=["metadatas"])
        
        # Get unique sources
        sources = {}
        for i, metadata in enumerate(all_items["metadatas"]):
            source = metadata.get("source", "unknown")
            if source not in sources:
                sources[source] = []
            sources[source].append(all_items["ids"][i])
        
        print(f"\n📋 Found {len(sources)} unique sources in ChromaDB:")
        for i, (source, ids) in enumerate(sources.items(), 1):
            print(f"  {i}. {source} ({len(ids)} documents)")
        
        # Ask user which sources to KEEP
        print(f"\n🎯 Which sources do you want to KEEP? (Enter numbers separated by commas)")
        print("   Example: 1,3 (to keep sources 1 and 3)")
        keep_input = input("Enter your choice: ").strip()
        
        if not keep_input:
            print("❌ No selection made. Exiting...")
            return
        
        # Parse user input
        try:
            keep_indices = [int(x.strip()) for x in keep_input.split(',')]
            sources_list = list(sources.keys())
            sources_to_keep = [sources_list[i-1] for i in keep_indices if 1 <= i <= len(sources_list)]
        except (ValueError, IndexError):
            print("❌ Invalid input. Exiting...")
            return
        
        print(f"\n✅ You chose to KEEP: {sources_to_keep}")
        
        # Find IDs to delete (everything NOT in keep list)
        ids_to_delete = []
        for source, ids in sources.items():
            if source not in sources_to_keep:
                ids_to_delete.extend(ids)
        
        print(f"🗑️  Will delete {len(ids_to_delete)} documents from ChromaDB")
        
        # Confirm deletion
        confirm = input("Proceed with ChromaDB cleanup? (y/N): ").strip().lower()
        if confirm != 'y':
            print("❌ ChromaDB cleanup cancelled.")
        else:
            # Delete in batches
            batch_size = 1000
            for i in range(0, len(ids_to_delete), batch_size):
                batch = ids_to_delete[i:i+batch_size]
                collection.delete(ids=batch)
                print(f"  Deleted batch {i//batch_size + 1}")
            
            print(f"✅ ChromaDB cleaned! New size: {collection.count()}")
        
        # Now handle course_output.json
        cleanup_course_json(sources_to_keep)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

def cleanup_course_json(sources_to_keep):
    """
    Clean course_output.json based on sources to keep
    """
    course_file = 'data/courses/course_output.json'
    
    try:
        # Load existing courses
        if os.path.exists(course_file):
            with open(course_file, 'r') as f:
                courses = json.load(f)
        else:
            courses = []
        
        print(f"\n📚 Found {len(courses)} courses in course_output.json:")
        for i, course in enumerate(courses, 1):
            title = course.get('course_title', 'Unknown')
            print(f"  {i}. {title}")
        
        if not courses:
            print("📝 No courses found in course_output.json")
            return
        
        # Map courses to sources (based on your knowledge)
        course_source_mapping = {
            'Generative AI Handson': 'big-book-generative-ai-databricks.pdf',
            'Class 10 Economics NCERT': 'NCERT-Class-10-Economics.pdf',
            'NCERT Class 10 Science': 'NCERT-Class-10-Science.pdf',
            'Professional Communication and Soft Skills': 'English Speaking1.pdf'
        }
        
        # Filter courses based on sources to keep
        courses_to_keep = []
        for course in courses:
            title = course.get('course_title', '')
            # Check if this course's source should be kept
            source = course_source_mapping.get(title, 'unknown')
            if source in sources_to_keep or any(keep_source in source for keep_source in sources_to_keep):
                courses_to_keep.append(course)
                print(f"✅ Keeping course: {title}")
            else:
                print(f"🗑️  Removing course: {title}")
        
        # Confirm course cleanup
        if len(courses_to_keep) != len(courses):
            confirm = input(f"\nProceed with course_output.json cleanup? ({len(courses_to_keep)}/{len(courses)} courses will remain) (y/N): ").strip().lower()
            if confirm == 'y':
                # Save filtered courses
                with open(course_file, 'w') as f:
                    json.dump(courses_to_keep, f, indent=4)
                print(f"✅ course_output.json updated! {len(courses_to_keep)} courses remaining.")
            else:
                print("❌ course_output.json cleanup cancelled.")
        else:
            print("📝 No changes needed for course_output.json")
            
    except Exception as e:
        print(f"❌ Error cleaning course_output.json: {e}")

def clean_chroma_collection():
    """
    Legacy function - calls interactive cleanup
    """
    interactive_cleanup()

if __name__ == "__main__":
    interactive_cleanup()
