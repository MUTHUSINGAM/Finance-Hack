"""
Check if vector database has content_type and extraction_method metadata.
If not, re-ingest all PDFs to populate the metadata.
"""
import os
from vector_store import collection
from ingestion import ingest_pdfs
from paths import PDF_DIR

def check_metadata():
    """Check if existing chunks have content_type and extraction_method."""
    print("=" * 60)
    print("Checking Vector Database Metadata...")
    print("=" * 60)
    
    total_chunks = collection.count()
    print(f"\nTotal chunks in database: {total_chunks}")
    
    if total_chunks == 0:
        print("\n❌ Database is empty!")
        return False
    
    # Get a sample of chunks
    sample_size = min(100, total_chunks)
    results = collection.get(limit=sample_size, include=["metadatas"])
    metadatas = results.get("metadatas", [])
    
    # Check how many have the metadata
    has_content_type = 0
    has_extraction_method = 0
    
    for meta in metadatas:
        if meta:
            if meta.get("content_type") is not None:
                has_content_type += 1
            if meta.get("extraction_method") is not None:
                has_extraction_method += 1
    
    print(f"\nSample size analyzed: {len(metadatas)}")
    print(f"Chunks with content_type: {has_content_type}/{len(metadatas)}")
    print(f"Chunks with extraction_method: {has_extraction_method}/{len(metadatas)}")
    
    if has_content_type == 0 or has_extraction_method == 0:
        print("\n❌ PROBLEM DETECTED: Metadata is missing!")
        print("   The database was created before metadata tracking was added.")
        return False
    elif has_content_type < len(metadatas) * 0.9:
        print("\n⚠️  WARNING: Some chunks are missing metadata.")
        return False
    else:
        print("\n✅ Metadata looks good!")
        return True

def show_sample_metadata():
    """Show a few sample chunks with their metadata."""
    print("\n" + "=" * 60)
    print("Sample Chunks with Metadata:")
    print("=" * 60)
    
    results = collection.get(limit=5, include=["documents", "metadatas"])
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    
    for i, (doc, meta) in enumerate(zip(docs, metas), 1):
        print(f"\n--- Chunk {i} ---")
        print(f"Text: {doc[:100]}...")
        print(f"Source: {meta.get('source', 'N/A')}")
        print(f"Page: {meta.get('page', 'N/A')}")
        print(f"Content Type: {meta.get('content_type', 'NULL ❌')}")
        print(f"Extraction Method: {meta.get('extraction_method', 'NULL ❌')}")

def fix_metadata():
    """Re-ingest all PDFs to populate metadata."""
    print("\n" + "=" * 60)
    print("RE-INGESTING PDFs TO FIX METADATA")
    print("=" * 60)
    
    # Clear the existing database
    print("\n⚠️  Clearing existing vector database...")
    try:
        # Get all IDs
        all_data = collection.get()
        all_ids = all_data.get("ids", [])
        
        if all_ids:
            print(f"   Deleting {len(all_ids)} existing chunks...")
            # Delete in batches
            batch_size = 1000
            for i in range(0, len(all_ids), batch_size):
                batch_ids = all_ids[i:i+batch_size]
                collection.delete(ids=batch_ids)
                print(f"   Deleted {min(i+batch_size, len(all_ids))}/{len(all_ids)} chunks...")
        
        print("   ✅ Database cleared!")
    except Exception as e:
        print(f"   ❌ Error clearing database: {e}")
        return False
    
    # Re-ingest with metadata
    print("\n📥 Re-ingesting PDFs with metadata...")
    try:
        ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=256)
        print("\n✅ Re-ingestion complete!")
        return True
    except Exception as e:
        print(f"\n❌ Error during re-ingestion: {e}")
        return False

def main():
    print("\n" + "=" * 60)
    print("VECTOR DATABASE METADATA CHECKER & FIXER")
    print("=" * 60)
    
    # Check current state
    metadata_ok = check_metadata()
    
    # Show samples
    show_sample_metadata()
    
    if not metadata_ok:
        print("\n" + "=" * 60)
        print("RECOMMENDATION")
        print("=" * 60)
        print("\nYour vector database is missing content_type and extraction_method metadata.")
        print("This happened because the database was created before this feature was added.")
        print("\nTo fix this, you need to re-ingest all PDFs.")
        print("\n⚠️  WARNING: This will:")
        print("   1. Delete all existing chunks from the database")
        print("   2. Re-process all PDFs")
        print("   3. Re-create embeddings (may take several minutes)")
        print("   4. Populate all metadata fields correctly")
        
        response = input("\n❓ Do you want to fix this now? (yes/no): ").strip().lower()
        
        if response in ['yes', 'y']:
            success = fix_metadata()
            if success:
                print("\n" + "=" * 60)
                print("VERIFICATION")
                print("=" * 60)
                check_metadata()
                show_sample_metadata()
                print("\n✅ ALL DONE! Your database now has proper metadata.")
                print("   Restart your backend server and test the evidence display.")
            else:
                print("\n❌ Fix failed. Please check the errors above.")
        else:
            print("\n⏭️  Skipped. Run this script again when you're ready to fix it.")
    else:
        print("\n✅ No action needed. Your database has proper metadata!")

if __name__ == "__main__":
    main()
