"""Persistent vectors for content that this application may index."""
import hashlib
import os
import re
from collections import Counter
from contextlib import contextmanager

from filelock import FileLock

from .db import directory


class LocalEmbeddings:
    """Dependency-free token feature hashing for offline lexical retrieval."""

    def embed_documents(self, documents):
        return [self.embed_query(document) for document in documents]

    def embed_query(self, document):
        vector = [0.0] * 512
        for word, count in Counter(re.findall(r"\w+", document.casefold())).items():
            key = int.from_bytes(hashlib.sha256(word.encode()).digest()[:4], "big")
            vector[key % len(vector)] += count if key & 512 else -count
        return vector

    def __call__(self, document):
        return self.embed_query(document)


@contextmanager
def store(source, vectorizer=None):
    import chromadb
    from langchain_chroma import Chroma

    if source not in {"demo", "import"}:
        raise ValueError("Source is not authorized for indexing")
    server = os.getenv("CHROMA_HOST")
    name = "restaurants-" + source + "-hash-v1"
    if server:
        client = chromadb.HttpClient(host=server, port=int(os.getenv("CHROMA_PORT", "8001")))
        try:
            yield Chroma(client=client, collection_name=name, embedding_function=vectorizer or LocalEmbeddings())
        finally:
            client.close()
    else:
        # Embedded mode is for a single process. Run the Chroma service when
        # the API and indexing worker run as separate processes.
        with FileLock(str(directory / "chroma.lock"), timeout=15):
            client = chromadb.PersistentClient(path=str(directory / "chroma"))
            try:
                yield Chroma(client=client, collection_name=name, embedding_function=vectorizer or LocalEmbeddings())
            finally:
                client.close()


def upsert(places, index_store):
    from langchain_core.documents import Document

    if any(p.source not in {"demo", "import"} for p in places):
        raise ValueError("Source is not authorized for indexing")
    index_store.add_documents([
        Document(page_content=f"{p.name} | {', '.join(p.cuisine)}",
                 metadata={"place_id": p.id, "source": p.source})
        for p in places
    ], ids=[p.id for p in places])


def imported_evidence(question, records):
    with store("import") as index_store:
        return index_store.similarity_search(
            question, k=min(12, len(records)), filter={"place_id": {"$in": [p.id for p in records]}},
        )
