import os
import sys
import argparse
import json
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

# Load figures configuration
config_path = Path(__file__).parent.parent / "api" / "figures" / "config.json"
with open(config_path, 'r', encoding='utf-8') as f:
    FIGURES_CONFIG = json.load(f)['figures']

# Create dictionary for fast lookup
FIGURES = {fig['id']: fig for fig in FIGURES_CONFIG}

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

                # Extract text from all pages and create a Document for each page
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        doc = Document(
                            page_content=page_text,
                            metadata={
                                "source": pdf_file,
                                "page": page_num + 1,  # Page numbers are 1-based
                                "total_pages": len(pdf.pages)
                            }
                        )
                        documents.append(doc)
                print(f"   OK: Extracted {len(pdf.pages)} pages from {pdf_file}")

        except Exception as e:
            print(f"   ERROR processing {pdf_file}: {str(e)}")
            continue

    return documents

def chunk_documents(documents):
    """Split documents into smaller chunks"""
    print(f"\n>> Chunking documents...")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )

    chunks = splitter.split_documents(documents)
    print(f"   OK: Created {len(chunks)} chunks")

    return chunks

def upload_to_pinecone(chunks, namespace):
    """Upload chunks to Pinecone with namespace"""
    print(f"\n>> Uploading to Pinecone in namespace: {namespace}...")

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index_name = os.getenv("PINECONE_INDEX_NAME")

    if index_name not in [idx['name'] for idx in pc.list_indexes()]:
        print(f"ERROR: Index '{index_name}' not found!")
        return False

    embeddings = OpenAIEmbeddings()

    try:
        batch_size = 100
        total_chunks = len(chunks)
        print(f"   Uploading {total_chunks} chunks in batches of {batch_size}...")

        for i in range(0, total_chunks, batch_size):
            batch = chunks[i:i + batch_size]
            print(f"   Uploading batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size}...")
            PineconeVectorStore.from_documents(
                batch,
                embeddings,
                index_name=index_name,
                namespace=namespace
            )
        print(f"   OK: Successfully uploaded all {total_chunks} chunks to namespace '{namespace}'!")
        return True
    except Exception as e:
        print(f"   ERROR uploading: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Process and upload PDFs for a specific figure.")
    parser.add_argument("figure_id", help="The ID of the figure to process (e.g., 'lrh', 'marcus-aurelius').")
    args = parser.parse_args()

    figure_id = args.figure_id
    if figure_id not in FIGURES:
        print(f"ERROR: Figure ID '{figure_id}' not found in config.json.")
        return

    figure_config = FIGURES[figure_id]
    namespace = figure_config['namespace']

    print("=" * 60)
    print(f"Processing PDFs for: {figure_config['name']}")
    print("=" * 60)

    pdf_folder = Path(__file__).parent.parent / "pdfs" / figure_id

    if not pdf_folder.exists():
        print(f"ERROR: PDFs folder not found: {pdf_folder}")
        return

    documents = extract_pdfs(pdf_folder)

    if not documents:
        print("\nERROR: No documents to process. Exiting.")
        return

    chunks = chunk_documents(documents)
    success = upload_to_pinecone(chunks, namespace)

    if success:
        print("\n" + "=" * 60)
        print(f"SUCCESS! All PDFs for {figure_config['name']} processed and uploaded.")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("ERROR: Upload failed. Check errors above.")
        print("=" * 60)

if __name__ == "__main__":
    main()