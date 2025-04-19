import os
from sentence_transformers import SentenceTransformer
from chat.parsers import load_transcript, parse_pdf_slides, parse_transcript_in_chunks, load_summary, load_concepts, \
    load_quiz, parse_all
from chat.embedding import embed_segments, embed_all, save_embeddings, load_embeddings
from chat.search import semantic_search, semantic_search_with_answer

def parse_and_embed(d_path,course_name="course",lesson="less"):
    trans_path = os.path.join(d_path, "transcript.json")
    slides_path = os.path.join(d_path, "שיעור מספר 4 מסע הלקוח.pdf")# TODO need to provide name
    short_file = os.path.join(d_path, "short_summary.txt")
    long_file = os.path.join(d_path, "long_summary.txt")
    quiz_file = os.path.join(d_path, "quiz.txt")
    concepts_file = os.path.join(d_path, "concepts.txt") # currently doesn't work
    # Load lesson-specific content
    lesson_segments = parse_all(
        transcript_path=trans_path,
        slide_path=None,
        short_summary_path=None,
        long_summary_path=long_file,
        concepts_path=None,
        quiz_path=quiz_file,
        course_id=course_name,
        lesson_id=lesson
    )
    #
    # Load course-level content
    course_segments = parse_all(
        transcript_path=None,
        slide_path=slides_path,
        short_summary_path=None,
        long_summary_path=None,
        concepts_path=None,
        quiz_path=None,
        course_id=course_name,
        lesson_id=None
    )

    # Combine and embed
    all_segments, model = embed_all(lesson_segments + course_segments)
    return all_segments


if __name__ == "__main__":
    d_path = "/home/roy/FS/OneDrive/WORK/ideas/aaron/רייכמן/marketing/semesterA/arifacts/"
    course_name="marketing"
    # part 1: embed and save (batch offline)
    embedding_file = os.path.join(d_path,"embeddings.pkl")
    embedding = parse_and_embed(d_path,course_name=course_name,lesson="1")
    save_embeddings(embedding_file, embedding)
    embedding=load_embeddings(embedding_file)
    if False:        # in the future

        embedding_2 = parse_and_embed(d_path,course_name=course_name,lesson="2")
        embedded_2, _ = embed_all(embedding_2)

        # update + save
        embedding += embedded_2
        save_embeddings(embedding_file, embedding)
        embedding=load_embeddings(embedding_file)

# part 2: query
    segments = load_embeddings(embedding_file)
    # reuse same model name
    model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    query = "מה זה תוכנית עבודה שיווקית"
    answer, refs = semantic_search_with_answer(query, segments, model)

    #     query = " explain what is מתיחת מותג לקטגוריות חדשות"
    #    # query = "כלי פרסום אשר בונים מעורבותexplain what is "
    #     query = "explain what is מהי תוכנית עבודה שיווקית?"
    #     query="how do i analyze category?"
    #     query = "give examples to כלי פרסום לבנית נאמנות"

    print (f"\n🔹query: {query}")
    print("🔹 Answer:")
    print(answer)

    print("\n🔹 References:")
    for r in refs:
        print(f"[{r['reference']}] (score: {r['score']}): {r['text']}")

    query="מה זה תדמית של מותג"
    answer, refs = semantic_search_with_answer(query, segments, model)

    print (f"\n🔹query: {query}")
    print("🔹 Answer:")
    print(answer)

    print("\n🔹 References:")
    for r in refs:
        print(f"[{r['reference']}] (score: {r['score']}): {r['text']}")