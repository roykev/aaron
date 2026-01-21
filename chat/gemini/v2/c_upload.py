from google import genai
from google.genai import types
import time

from utils.utils import source_key


#
# # File name will be visible in citations
# file_search_store = client.file_search_stores.create(config={'display_name': 'agamon_hefer'})
# file_path="/home/roy/FS/git/chat/data/locations/hefer_valley/agamon_hefer/nature_reserve.txt"
# operation = client.file_search_stores.upload_to_file_search_store(
#   file=file_path,
#   file_search_store_name=file_search_store.name,
#   config= chunk_configs()
#
# )
#
#
# while not operation.done:
#     time.sleep(5)
#     operation = client.operations.get(operation)
#
# print(file_search_store.name)


def init_store(client, display_name):
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
    #name = init_store(client, display_name)#fileSearchStores/sites-qto443d7uryu

    store_name="fileSearchStores/tarasa-ezosp3airt9x"
    store_name="fileSearchStores/aaron-250pjghbtrh5"
    file_path = "/home/roy/FS/Dropbox/WORK/Ideas/aaron/ono/ella/transcript.vtt"
    inst_name= "one"
    course_name = "anatomy"
    class_name = "class2"
    year="2025"
    semester="A"


    # file_path="/home/roy/FS/git/chat/data/locations/hefer_valley/alexander_stream/hiking_trails.txt"
    # file_path="/home/roy/FS/git/chat/data/locations/tel_aviv_district/jaffa_port/historical_tour.txt"
    #
    # store_name="fileSearchStores/sites-qto443d7uryu"
    # file_search_store = client.file_search_stores.get(name=store_name)
    # display_file_name="jaffa-port--historical-tour-3"
    # metadata = [
    #     {"key": "area","string_value":"tel-aviv"},
    #             {"key": "scope", "string_value": "class_1"}
    #             ]
    # upload_file(client, file_search_store, file_path, display_file_name,metadata)
    upload_file_with_metadata(client, store_name, file_path,inst_name, course_name,class_name,year,semester)

    #print(name)




if __name__ == '__main__':
    api_key = source_key("GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    display_name="TARASA"

    #1 only once per project
    # we may have a store per TARASA or per project (hefer/TLV)




    # name = init_store(client, display_name)
    # #print(name)
    #
    # name is e.g., #fileSearchStores/TARASA-qto443d7uryu




    store_name="fileSearchStores/TARASA-qto443d7uryu" #what was retutred once
    file_path="/home/roy/FS/git/chat/data/locations/hefer_valley/agamon_hefer/nature_reserve.txt"

    area= "hefer"
    site= "alexander_stream"
    doc = 'hikingtrails'


    file_path="/home/roy/FS/git/chat/data/locations/hefer_valley/alexander_stream/hiking_trails.txt"
    file_search_store = client.file_search_stores.get(name=store_name)


    upload_file_with_metadata(client, store_name, file_path,area,site,doc)


