import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

#def semantic_search_with_answer(query, segments, model, top_k=5):
    # query_embedding = model.encode([query], convert_to_numpy=True)
    # segment_embeddings = np.array([s["embedding"] for s in segments])
    # similarities = cosine_similarity(query_embedding, segment_embeddings)[0]
    # top_indices = similarities.argsort()[::-1][:top_k]
    #
    # results = []
    # for idx in top_indices:
    #     s = segments[idx]
    #     results.append({
    #         "score": round(float(similarities[idx]), 3),
    #         "reference": s.get("reference", "Unknown source"),
    #         "text": s["text"]
    #     })
    #
    # short_answer = results[0]["text"] if results else "No answer found."
    # return short_answer, results
def semantic_search_with_answer(query, segments, model, top_k=5, score_threshold=0.5):
        results = semantic_search(query, segments, model, top_k=top_k, score_threshold=score_threshold)
        short_answer = results[0]["text"] if results else "No answer found."
        return short_answer, results




def semantic_search(query, segments, model, top_k=5, score_threshold=0.5):
    query_embedding = model.encode([query], convert_to_numpy=True)
    segment_embeddings = np.array([s["embedding"] for s in segments])

    similarities = cosine_similarity(query_embedding, segment_embeddings)[0]
    top_indices = similarities.argsort()[::-1]

    results = []
    for idx in top_indices:
        score = float(similarities[idx])
        if score < score_threshold:
            continue  # skip low-relevance results
        s = segments[idx]
        results.append({
            "score": round(score, 3),
            "reference": s.get("reference", "Unknown source"),
            "text": s["text"]
        })
        if len(results) >= top_k:
            break

    return results


