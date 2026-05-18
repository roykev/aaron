import csv
import re
import argparse
import os


def normalize_space(text):
    tokens = re.split(r'\s+', text)
    return r'\s+'.join(re.escape(t) for t in tokens if t)


def translate_markdown_contextual(md_file_path, csv_file_path, target_language, output_file_path):
    if target_language.lower() == 'english':
        print(" שפת היעד היא אנגלית. לא תתבצע המרה.")
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return

    if not os.path.exists(csv_file_path) or not os.path.exists(md_file_path):
        raise FileNotFoundError("אחד מקבצי המקור (MD או CSV) לא נמצא.")

    translation_map = {}

    with open(csv_file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        if target_language not in reader.fieldnames:
            raise ValueError(f"השפה '{target_language}' לא קיימת ב-CSV.")

        for row in reader:
            # החלפת ה-'\n' המילולי מה-CSV למעבר שורה אמיתי במידת הצורך
            source = row['SourceText'].replace('\\n', '\n').strip() if row['SourceText'] else ""
            target = row[target_language].replace('\\n', '\n').strip() if row[target_language] else ""
            if source and target:
                translation_map[source] = target

    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    # מיון מהטקסט הארוך לקצר ביותר
    sorted_sources = sorted(translation_map.keys(), key=len, reverse=True)

    translated_content = md_content
    for source in sorted_sources:
        target = translation_map[source]

        # יצירת תבנית חיפוש גמישה שמתעלמת מהבדלי רווחים ומעברי שורה קלים בקוד
        flexible_source_pattern = normalize_space(source)

        # ביצוע ההחלפה המבוססת קונטקסט
        translated_content = re.sub(flexible_source_pattern, target, translated_content)

    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(translated_content)

    print(f" הקובץ תורגם בהצלחה תחת הקונטקסט המבוקש לשפה '{target_language}'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="תרגום מבוסס קונטקסט של קבצי MD.")
    parser.add_argument('--input', type=str, default='input_sample.md')
    parser.add_argument('--csv', type=str, default='complete_translation_mapping.csv')
    parser.add_argument('--lang', type=str, default='Hebrew')
    parser.add_argument('--output', type=str, default='output_translated.md')

    args = parser.parse_args()

    try:
        translate_markdown_contextual(args.input, args.csv, args.lang, args.output)
    except Exception as e:
        print(f"❌ שגיאה: {e}")