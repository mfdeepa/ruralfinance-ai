import os
import streamlit as st
from typing import List

_HERE    = os.path.dirname(os.path.abspath(__file__))
_ROOT    = os.path.dirname(_HERE)
_KB_PATH = os.path.join(_ROOT, "data", "knowledge_base")
_DB_PATH = os.path.abspath(os.getenv("CHROMA_DB_PATH") or os.path.join(_ROOT, "data", "chroma_db"))


@st.cache_resource(show_spinner=False)
def _get_collection():
    try:
        import chromadb
        from chromadb.utils import embedding_functions

        os.makedirs(_DB_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=_DB_PATH)
        ef = embedding_functions.DefaultEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="ruralfinance_kb",
            embedding_function=ef,
        )
        if collection.count() == 0:
            _load_knowledge_base(collection)
        return collection
    except Exception as e:
        print(f"[RAG] ChromaDB init failed: {e}")
        return None


def _load_knowledge_base(collection):
    if not os.path.exists(_KB_PATH):
        print(f"[RAG] Knowledge base path not found: {_KB_PATH}")
        return

    docs, ids, metas = [], [], []
    idx = 0

    for filename in sorted(os.listdir(_KB_PATH)):
        if not filename.endswith(".txt"):
            continue
        filepath = os.path.join(_KB_PATH, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            category = filename.replace(".txt", "")
            for chunk in _chunk_text(content, 350):
                docs.append(chunk)
                ids.append(f"{category}_{idx}")
                metas.append({"source": filename, "category": category})
                idx += 1
        except Exception as e:
            print(f"[RAG] Error loading {filename}: {e}")

    if docs:
        for i in range(0, len(docs), 100):
            collection.add(
                documents=docs[i : i + 100],
                ids=ids[i : i + 100],
                metadatas=metas[i : i + 100],
            )
    print(f"[RAG] Loaded {len(docs)} chunks from {_KB_PATH}")


def _chunk_text(text: str, size: int = 350) -> List[str]:
    words = text.split()
    return [
        " ".join(words[i : i + size])
        for i in range(0, len(words), size)
        if " ".join(words[i : i + size]).strip()
    ]


def query(text: str, n: int = 3) -> str:
    """Return the most relevant knowledge base chunks for a query."""
    try:
        collection = _get_collection()
        if collection is None or collection.count() == 0:
            return ""
        results = collection.query(
            query_texts=[text],
            n_results=min(n, collection.count()),
        )
        if results and results["documents"] and results["documents"][0]:
            return "\n\n---\n\n".join(results["documents"][0])
        return ""
    except Exception:
        return ""
