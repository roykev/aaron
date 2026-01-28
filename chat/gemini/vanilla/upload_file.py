from google import genai
from google.genai import types
import sys
from pathlib import Path

# Add project root to path to import utils
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.utils import source_key


def init_store(client, display_name):#only one time 
    # File name will be visible in citations
    file_search_store = client.file_search_stores.create(config={'display_name': display_name})
    return file_search_store.name


def upload_file_with_metadata(client, file_search_store_name, file_path,inst_name,course_name,class_name,year,semester):
    op = client.file_search_stores.upload_to_file_search_store(
        file=file_path,
        file_search_store_name=file_search_store_name,
        config={
            "display_name": f"{inst_name}_{course_name}_{class_name}",
            "chunking_config":
                {
          'white_space_config': {
              'max_tokens_per_chunk': 300,
              'max_overlap_tokens': 40
          }
                }
            ,
            "custom_metadata": [
                {"key": "institute", "string_value": inst_name},
                {"key": "course", "string_value": course_name},
                {"key": "class", "string_value": class_name},
                {"key": "year", "string_value": year},
                {"key": "semester", "string_value": semester},
            ],
        },
    )

    print(op)

if __name__ == '__main__':
    api_key = source_key("GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    display_name="aaron"
    # only one time in project initiation
        
    #name = init_store(client, display_name)#fileSearchStores/sites-qto443d7uryu


    store_name="fileSearchStores/aaron-250pjghbtrh5"
    # store_name="fileSearchStores/aaron-250pjghbtrh5-roie-test"

    file_path = "/mnt/d/Documents/Work/AaronTheOwl/Courses/Ono College/פסיכולוגיה/Lecture5_chat/transcript.vtt"
    inst_name= "one"
    course_name = "psychology2"
    class_name = "class2"
    year="2025"
    semester="A"


    upload_file_with_metadata(client, store_name, file_path,inst_name, course_name,class_name,year,semester)

    #print(name)
