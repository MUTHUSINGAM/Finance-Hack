"""
Force re-ingestion by clearing the database.
The backend server will auto-detect empty database and re-ingest on next startup.
"""
import shutil
import os
from pathlib import Path

def force_reingest():
    """Delete the database folder to trigger auto-ingestion."""
    chroma_dir = Path("chroma_db")
    
    print("\n" + "=" * 70)
    print("FORCE RE-INGESTION SETUP")
    print("=" * 70)
    
    if not chroma_dir.exists():
        print("\n✅ Database folder doesn't exist. Backend will auto-ingest on startup.")
        return True
    
    print(f"\n🗑️  Deleting database folder: {chroma_dir}")
    
    try:
        shutil.rmtree(chroma_dir)
        print("   ✅ Database folder deleted!")
        print("\n📝 Next steps:")
        print("   1. Stop your backend server (Ctrl+C)")
        print("   2. Restart it: python3 main.py")
        print("   3. Backend will auto-detect empty database")
        print("   4. It will automatically re-ingest all PDFs with metadata")
        print("   5. Wait for: 'Vector store loaded with XXXX text chunks'")
        print("\n✅ This will fix the NULL metadata issue!")
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nManual fix:")
        print(f"   1. Close any programs using the database")
        print(f"   2. Manually delete folder: {chroma_dir.absolute()}")
        print("   3. Restart backend server")
        return False

if __name__ == "__main__":
    print("\n⚠️  This will delete the vector database folder.")
    print("   The backend server will rebuild it on next startup.")
    print("   Your PDF files will NOT be deleted.")
    
    response = input("\n❓ Continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        success = force_reingest()
        if success:
            print("\n" + "=" * 70)
            print("✅ READY FOR RE-INGESTION")
            print("=" * 70)
            print("\nNow restart your backend server!")
    else:
        print("\n⏭️  Cancelled.")
