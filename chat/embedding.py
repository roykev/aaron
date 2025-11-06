from sentence_transformers import SentenceTransformer
import numpy as np
import pickle

def save_embeddings(path, segments):
    with open(path, "wb") as f:
        pickle.dump(segments, f)

def load_embeddings(path):
    with open(path, "rb") as f:
        return pickle.load(f)

def embed_segments(segments, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
    model = SentenceTransformer(model_name)
    texts = [s["text"] for s in segments]
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

    for i, emb in enumerate(embeddings):
        segments[i]["embedding"] = emb
    return segments,model

def embed_all(segments, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
    return embed_segments(segments, model_name=model_name)

