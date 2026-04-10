"""
Quick script to re-ingest all PDFs with proper metadata.
Use this to fix content_type and extraction_method being null.
"""
import os
from vector_store import collection
from ingestion import ingest_pdfs
from paths import PDF_DIR

def reingest_all():
    """Clear database and re-ingest all PDFs with metadata."""
    print("\n" + "=" * 70)
    print("RE-INGESTING ALL PDFs WITH METADATA")
    print("=" * 70)
    
    # Step 1: Show current state
    current_count = collection.count()
    print(f"\nCurrent chunks in database: {current_count}")
    
    # Step 2: Clear database
    print("\n🗑️  Clearing existing database...")
    try:
        all_data = collection.get()
        all_ids = all_data.get("ids", [])
        
        if all_ids:
            batch_size = 1000
            for i in range(0, len(all_ids), batch_size):
                batch_ids = all_ids[i:i+batch_size]
                collection.delete(ids=batch_ids)
                progress = min(i+batch_size, len(all_ids))
                print(f"   Deleted {progress}/{len(all_ids)} chunks...")
        
        print("   ✅ Database cleared!")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Step 3: Re-ingest with metadata
    print("\n📥 Re-ingesting PDFs with content_type and extraction_method...")
    print("   This may take several minutes depending on PDF count...")
    
    try:
        ingest_pdfs(pdf_dir=str(PDF_DIR), batch_size=256)
        print("\n✅ Re-ingestion complete!")
    except Exception as e:
        print(f"\n❌ Error during ingestion: {e}")
        return False
    
    # Step 4: Verify
    new_count = collection.count()
    print(f"\n📊 New chunks in database: {new_count}")
    
    # Check metadata
    print("\n🔍 Verifying metadata...")
    sample = collection.get(limit=5, include=["metadatas"])
    metas = sample.get("metadatas", [])
    
    has_metadata = 0
    for meta in metas:
        if meta and meta.get("content_type") and meta.get("extraction_method"):
            has_metadata += 1
    
    print(f"   Chunks with metadata: {has_metadata}/{len(metas)}")
    
    if has_metadata == len(metas):
        print("\n✅ SUCCESS! All chunks now have content_type and extraction_method!")
        print("\n📝 Sample metadata:")
        for i, meta in enumerate(metas[:3], 1):
            print(f"   {i}. content_type: {meta.get('content_type')}, extraction_method: {meta.get('extraction_method')}")
        
        print("\n🚀 Next steps:")
        print("   1. Restart your backend server: python3 main.py")
        print("   2. Test in frontend or Postman")
        print("   3. Evidence should now show content_type and extraction_method!")
        return True
    else:
        print("\n⚠️  WARNING: Some chunks still missing metadata.")
        return False

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will delete all existing chunks and re-process all PDFs.")
    print("   This is necessary to add content_type and extraction_method metadata.")
    
    response = input("\n❓ Continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        success = reingest_all()
        if success:
            print("\n" + "=" * 70)
            print("✅ ALL DONE!")
            print("=" * 70)
        else:
            print("\n❌ Process failed. Check errors above.")
    else:
        print("\n⏭️  Cancelled. No changes made.")
