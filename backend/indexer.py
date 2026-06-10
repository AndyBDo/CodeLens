import os

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db")

# CodeLens never reads the local filesystem: source content only comes from the
# configured GitHub/GitLab repository via build_index_from_documents.
INDEXED_EXTENSIONS = (".java", ".jsx", ".js", ".ts", ".tsx", ".properties", ".xml")


def _get_embeddings():
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def build_index_from_documents(documents):
    """documents: list of (content, metadata) tuples. Rebuilds the index from scratch."""
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)

    texts = []
    metadatas = []
    for content, metadata in documents:
        for chunk in splitter.split_text(content):
            texts.append(chunk)
            metadatas.append(metadata)

    print(f"Created {len(texts)} chunks. Embedding and storing in ChromaDB...")

    if os.path.exists(PERSIST_DIR):
        try:
            Chroma(
                persist_directory=PERSIST_DIR,
                embedding_function=_get_embeddings(),
            ).delete_collection()
        except Exception as e:
            print(f"Could not clear old collection: {e}")

    vectorstore = Chroma.from_texts(
        texts=texts,
        embedding=_get_embeddings(),
        metadatas=metadatas,
        persist_directory=PERSIST_DIR,
    )
    vectorstore.persist()
    print(f"Index built and persisted to {PERSIST_DIR}")
    return vectorstore


def load_index():
    return Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=_get_embeddings(),
    )
