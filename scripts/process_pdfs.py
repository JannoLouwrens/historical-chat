import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.docstore.document import Document
from pinecone import Pinecone

# Load environment variables
load_dotenv()

def extract_pdfs(folder_path):
    """Extract text from all PDFs in folder"""
    print(f"\n>> Reading PDFs from {folder_path}...")
    documents = []

    pdf_files = [f for f in os.listdir(folder_path) if f.endswith('.pdf')]

    if not pdf_files:
        print("ERROR: No PDF files found!")
        return documents

    print(f"Found {len(pdf_files)} PDF files\n")

    for idx, pdf_file in enumerate(pdf_files, 1):
        filepath = os.path.join(folder_path, pdf_file)
        print(f"[{idx}/{len(pdf_files)}] Processing: {pdf_file}")

        try:
            with open(filepath, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                text = ""

                # Extract text from all pages
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    text += page_text

                # Create document with metadata
                doc = Document(
                    page_content=text,
                    metadata={
                        "source": pdf_file,
                        "total_pages": len(pdf.pages)
                    }
                )
                documents.append(doc)
                print(f"   OK: Extracted {len(pdf.pages)} pages, {len(text)} characters")

        except Exception as e:
            print(f"   ERROR processing {pdf_file}: {str(e)}")
            continue

    return documents

def chunk_documents(documents):
    """Split documents into smaller chunks"""
    print(f"\n>> Chunking documents...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )

    chunks = splitter.split_documents(documents)
    print(f"   OK: Created {len(chunks)} chunks")

    return chunks

def upload_to_pinecone(chunks):
    """Upload chunks to Pinecone"""
    print(f"\n>> Uploading to Pinecone...")

    # Initialize Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    index_name = os.getenv("PINECONE_INDEX_NAME")

    # Check if index exists
    index_list = pc.list_indexes()
    index_names = [idx['name'] for idx in index_list]

    if index_name not in index_names:
        print(f"ERROR: Index '{index_name}' not found!")
        print("Please create it in Pinecone dashboard first.")
        print(f"Available indexes: {index_names}")
        return False

    # Create embeddings
    print("   Creating embeddings (this may take a while)...")
    embeddings = OpenAIEmbeddings()

    # Upload to Pinecone
    try:
        vectorstore = PineconeVectorStore.from_documents(
            chunks,
            embeddings,
            index_name=index_name
        )
        print(f"   OK: Successfully uploaded {len(chunks)} chunks!")
        return True
    except Exception as e:
        print(f"   ERROR uploading: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("LRH PDF Processing & Upload Script")
    print("=" * 60)

    # Get PDFs folder path
    pdf_folder = Path(__file__).parent.parent / "pdfs"

    if not pdf_folder.exists():
        print(f"ERROR: PDFs folder not found: {pdf_folder}")
        return

    # Step 1: Extract text from PDFs
    documents = extract_pdfs(pdf_folder)

    if not documents:
        print("\nERROR: No documents to process. Exiting.")
        return

    # Step 2: Chunk documents
    chunks = chunk_documents(documents)

    # Step 3: Upload to Pinecone
    success = upload_to_pinecone(chunks)

    if success:
        print("\n" + "=" * 60)
        print("SUCCESS! All PDFs processed and uploaded.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("ERROR: Upload failed. Check errors above.")
        print("=" * 60)

if __name__ == "__main__":
    main()
