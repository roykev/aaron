import os
import openai
from aaron_GPT import source_key
# Load your API key from an environment variable or secret management service
openai.api_key = source_key()
name = "economics"
file_path = f"/home/roy/Downloads/{name}.txt"

# Load the text file
with open(file_path, 'r') as file:
    text = file.read()
def call_openai(messages, max_tokens=5000):
    response = openai.chat.completions.create(
 #       model="gpt-3.5-turbo",
        model="gpt-4o",
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def split_text_into_chunks(text, chunk_size=4500):
    words = text.split()
    for i in range(0, len(words), chunk_size):
        yield ' '.join(words[i:i + chunk_size])

content_description="a transcript ((with timestamps of each section) of an interview with a researcher of the the middle east"
content_description="a transcript ((with timestamps of each section) of a lecture on behavioral economics"

lan = "Hebrew"
summary_len = 500
num_q=10
def process_long_text(text, task_prompt, max_tokens=1000):
    chunks = list(split_text_into_chunks(text))
    results = []
    for chunk in chunks:
        messages = [
            {"role": "system", "content": f"You are a helpful assistant. I give you several tasks and provide {content_description}. the content is in {lan}, and so is the required output. pay attention to the requested output format."},
            {"role": "user", "content": f"{task_prompt}\n\n{chunk}"}
        ]
        result = call_openai(messages, max_tokens=max_tokens)
        results.append(result)
    return ' '.join(results)

# Define tasks
tasks = {
    "Partition":"split the text to the chapters. examples introduction, Body of the lecture, questions, closing remarks"
                "the output format is "
                "Chapter: from time - to time",
    "Summarization": f"Summarize the Body of the lecture (as in the partition task) in at least {summary_len} words in {lan}:",
    "keyword_extraction": "Extract the key phrases, names and concepts from the following transcript:"
                                          "the output format is: "
                                          "new line"
                                          "concept; start-end, start-end. e.g.,"
                                          "AAA; 00:15-01:40, 04:55-10:20"
                                          "BBB; 35:15-36:50"
                                          "and so on"
                                          "when AAA, BBB are examples for concepts and 00:15-01:40 are start-end (from the beginning of the transcript) of when the concept is mentioned."
                                          "note that in this examples AAA is mentioned twice: in 00:15-01:40 and 04:55-10:20 from the beginning of the transcript"
                                          "new line",
    "Quiz":f"Compose a quiz about the of the lecture: {num_q} questions (multiple choice, multiple answers are allowed). write '*' before the correct answers of the questions in the following format:"
                                          "new line "
                                          "question_number; question"
                                          "new line"
                                          "* choice A"
                                          "new line"
                                          "choice B"
                                           "and so on"
                                          "new line "                                         
                                          "e.g., "
                                          "1; what is the color of an orange?"
                                          "A; red"
                                          "B; blue"
                                          "* C; orange"
                                          "D; green",
    "Additional":f" Suggest {num_q} additional reading, media, and sources about the topics of the interview. Add references authors and pointers where appropriate"
}
tasks1 = {
# "short_Summary":
#     "You will be provided a large transcript of a lecture"
#     "Write short summary of the transcript. "
#     "the summary should be 2-3 paragraph long "
#     f"Your summary should be in {lan} language",
# "Summary":
#     "You will be provided a large transcript of a lecture"
#           "Write a detailed, accurate summary of the transcript. "
#           "The summary should include several chapters"
#           "You should include chapter headers with timestamps for when that chapter begins. "
#           "Each chapter should contain one or more paragraphs, not bullet points. "
#           f"Your summary should be in {lan} language"
#           "Do not leave out any important information. " ,
# "keyword_extraction":
#     "Extract the key phrases, persons names and concepts from the transcript."
#     "the output format is: concept; start-end, start-end. e.g.,"
#     "AAA; 00:15-01:40, 04:55-10:20"
#     "BBB; 35:15-36:50"
#     "and so on, when AAA, BBB are examples of concepts and 00:15-01:40 are start-end (from the beginning of the transcript) of when the concept is mentioned."
#     "note that a concept can be mentioned more than once. In this examples AAA is mentioned twice: in 00:15-01:40 and 04:55-10:20 from the beginning of the transcript",
# "Additional":
#     f" Suggest {num_q} additional reading, media, and sources about the topics of the interview. Add references authors and pointers where appropriate",
"Quiz":
    f"Compose a quiz in {lan} about the of the lecture. {num_q} questions (multiple choice, multiple answers are allowed). "
    f"write '*' before the correct answers of the questions in the following format:"
            "question_number; question"
            "new line"
            "* choice A"
            "new line"
            "choice B"
            "and so on"
            "new line "
            "e.g., "
            "1; what is the color of an orange?"
            "A; red"
            "B; blue"
            "* C; orange"
            "D; green",
}
tasks2 = {
    "Summary": "You will be provided a transcript in write an accurate, 3-5 sentence summary of what you've read so far. Your summary should be in the same language as the transcript. Here is the first section of the transcript, which you should write a 3-5 sentence summary for:"
        "(0:40 - 0:59) אתם זוכרים ששוחחנו, רק נתתי שקף וזה יעסיק אותנו לכמעט הרצאה שלמה או חצי הרצאה. אז אני מקווה שהקריאה שמה לא תבוא במקום זה שתגיעו לדיון שלנו. אני בטוח שיהיו דברים שונים, אבל מאוד מעניין מה שקורה."
"(0:59 - 1:31)מה שהזכרנו, המוביליות של הדור החדש, לעבוד מהבית, יש לזה כל מיני השלכות מבחינת ההתארגנות שלהם לפנסיה ודברים כאלה ואחרים. אז אני מאוד ממליץ לעקוב אחר הסדרה הזאת. דיברנו גם על עולם שמחפש את עצמו, הגלובליזציה, לאן? וראיתם אתמול כישלון טוטאלי לראש ממשלת בריטניה, תרסה מאי, בלנסות להעביר שוב את תוכנית הברקזיט."
"(1:31 - 1:58) בריטניה מבולבלת לחלוטין מה לעשות עם הפרויקט הזה של הברקזיט וכו'. ואני חושב ששוב כולנו מופתעים כל פעם מחדש על הנושאים האלה. כמובן שדונלד טראמפ כל שבוע והוא גם יופיע בהרצאה של היום, כפי שאתם תראו, אני מאוד נהנה להזכיר אותו."
"(1:58 - 2:29) אוקיי, אז מה אנחנו עושים היום? קודם כל היום אנחנו מערכים חוקר צעיר מוביל באוניברסיטה בתחום של כלכלה התנהגותית, החיבור בין פסיכולוגיה לכלכלה, דוקטור יניב שני שנמצא פה איתנו. אז הוא באמת, אני מאוד מאוד מודה לו על המאמץ. אמנם הוא חוקר והוא יודע את הדברים האלה בעל פה, אבל בכל זאת הוא השקיע בהכנת ההרצאה ולעשות אותה נגישה בהקשר הזה."
"(2:30 - 3:26) יניב הוא חבר סגל בפקולטה לניהול כאן על שם קולר והמומחיות שלו זה באמת קבלת החלטות, בעיקר על ידי כל אחד מאיתנו כצרכנים, כפירמות. והחיבור הזה בין פסיכולוג, הוא בא מתחום הפסיכולוגיה, אבל יושב בפקולטה לניהול, ואני חושב שאינטראקציה הזאת היא אינטראקציה מאוד מאוד חשובה בימינו, כפי שאנחנו נראה בהמשך. וכן, כל התחום הזה, אני אסתפק בלומר כמה מילות פתיחה לגבי התחום הזה, מהזווית של כלכלן, שכאילו כל הנושא הזה של כלכלה ביהיווריסטית, של פסיכולוגיה בכלכלה, נכנס גם אלינו לתחום של כלכלה, מנקודת המבט של כלכלה."
"(3:26 - 4:17) אז כולנו יודעים שהמוח שלנו, יש לו חלקים שמטפלים בנושא הרציונלי, השכלי, ויש חלקים של המוח שלנו שמטפלים בנושא האמוציונלי הרגשי. מחקרים חדשים בתחום המוח מצביעים על זה שההבחנה הזאת היא לא מאוד מאוד חדה, ושמה שחשבנו שזאת איזו סגמנטציה, בין נקרא לזה צד ימין וצד שמאל, כיום זה פחות ברור שהדברים, אני מדבר על מחקרים על בסיס אמראי, וכל מיני מבחנים אפילו רפואיים, איך המוח שלנו מגיב לכל מיני סיטואציות. אז זה מה שיעסיק אותנו היום בהרצאה של יני."
" (4:17 - 5:15) עכשיו, איך אנחנו מגיעים לזה ככלכלנים מתחום הכלכלה? הגישה הדומיננטית בכלכלה לאורך השנים, ובבסיס של מה שקרוי מדע כלכלה אם נקרא לזה מדע או הדיסציפלינה של הכלכלה, זאת הגישה של מה שנקרא הומו אקונומיקוס, האדם הכלכלי, האדם הרציונלי. משם התחילה הכלכלה, ומשם התחילה הכלכלה כדיסציפלינה גם מחקרית, גם באוניברסיטאות וכולי וכולי. מה אומרת הגישה של הומו אקונומיקוס? היא אומרת שאנחנו כפרטים, אנחנו כבני אדם, כאנשים, מקבלים החלטות לפי מקסימיזציה של התועלת שלנו בכפוף למגבלות התקציב שלנו."
" (5:15 - 5:31) כלומר, אנחנו מפיקים תועלת, אנחנו מרגישים טוב עם שורה של פעולות ושורה של דברים. אפשר לטייל פה, לטייל שם. אפשר לאכול במסעדה כזאת, אפשר במסעדה אחרת, וכולי וכולי."
" (5:31 - 5:51) והחלטות שלנו הן כאלה שמביאות למקסימום את הרווחה שלנו, את הרגשות שלנו, את המרגיש טוב הזה, בכפוף למגבלת תקציב. בכלכלה ..."


}
# Execute tasks
results = {}
for task, task_prompt in tasks1.items():
    result = process_long_text(text, task_prompt)
    results[task] = result

# Print results
for task, result in results.items():
    print(f"{task.capitalize()} Result:\n{result}\n")
# Optionally, save results to a file
for task, result in results.items():
    with open(f'/home/roy/Downloads/RAG_{name}_{task}.txt', 'w') as file:
        file.write(f"{task.capitalize()} Result:\n{result}\n\n")
