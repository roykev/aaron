import os




def chunk_configs():
    return (
  {
      'display_name' : 'display-file-name',
      'chunking_config': {
          'white_space_config': {
              'max_tokens_per_chunk': 300,
              'max_overlap_tokens': 40
          }
      }
  }
    )