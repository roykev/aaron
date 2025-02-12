import logging
import os
from transformers import BitsAndBytesConfig

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM, pipeline
from transformers import pipeline, AutoModelForSeq2SeqLM, AutoTokenizer, BitsAndBytesConfig
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline, BitsAndBytesConfig

import torch
from torch.cuda.amp import autocast
# Specify the model name

class ScenesSummarizer:

    def __init__(self,  model_name = "sshleifer/distilbart-cnn-12-6"):

        # 1. Set CUDA debugging mode
        os.environ["CUDA_LAUNCH_BLOCKING"] = "1"  # Forces synchronous CUDA execution
        logging.debug("CUDA_LAUNCH_BLOCKING set to:", os.environ["CUDA_LAUNCH_BLOCKING"])
        # 2. Check CUDA availability and set device
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            logging.debug("CUDA is available. Using device:", torch.cuda.get_device_name(0))
            print(torch.cuda.get_device_name(0))
        else:
            self.device = torch.device("cpu")
            logging.debug("CUDA is not available. Using CPU.")

        # 3. Load Pretrained Model and Tokenizer
        logging.debug("Loading model and tokenizer...")




        if model_name.lower() not in ["h", "hebrew", "g", "general"]:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)

            # Load model
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(self.device)

            # Alternatively, use a pipeline for ease
            self.summarizer = pipeline("summarization", model=self.model, tokenizer=self.tokenizer,
                              device=0 if torch.cuda.is_available() else -1)


        else:


            device = 0 if torch.cuda.is_available() else "cpu"

            # Configure 8-bit quantization with CPU offload
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_enable_fp32_cpu_offload=True  # Allow offloading to CPU
            )

            # Load model with device auto-assignment
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                "google/mt5-base",
                quantization_config=quantization_config,
                device_map="auto"  # `accelerate` will automatically assign devices
            )

            self.tokenizer = AutoTokenizer.from_pretrained("google/mt5-base")

            # ❌ REMOVE `device` FROM PIPELINE CREATION
            self.summarizer = pipeline("summarization", model=self.model, tokenizer=self.tokenizer)

            # self.summarizer = pipeline(          "summarization",
            #                                      model="google/mt5-base",
            #                                      tokenizer="google/mt5-base",
            #                                      device=0 if torch.cuda.is_available() else -1


        #
    # 4. Define Summarization Function
    def summarize_or_copy(self, text, min_text_length=15, max_input_length=1024):
        """
        Summarizes text if it's above a certain length, otherwise returns the original text.

        Args:
            text (str): The input text to summarize.
            min_text_length (int): Minimum length for summarization to be applied.
            max_input_length (int): Maximum input length for the tokenizer/model.

        Returns:
            str: Summarized or original text.
        """
        # If text is too short, return it as is
        if len(text) < min_text_length:
            return text

        # Ensure text is within the model's max input length
        text = f'summarize: {text[:max_input_length]}'

       # model_name = "google/mt5-small"  # Multilingual T5 model
        #device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load tokenizer and model
        #tokenizer = AutoTokenizer.from_pretrained(model_name)
        #model = AutoModelForSeq2SeqLM.from_pretrained(model_name).to(device)

        # Tokenize input
        #inputs = tokenizer(text, return_tensors="pt", max_length=1024, truncation=True).to(device)

        # Generate summary
        try:

            # # Generate output
            # summary_ids = model.generate(
            #     inputs["input_ids"],
            #     max_length=150,
            #     min_length=50,
            #     length_penalty=1.0,
            #     num_beams=4,
            #     no_repeat_ngram_size=3,
            #     early_stopping=True,
            # )
            # Ensure input tensors are on the correct device
            device = next(self.model.parameters()).device
            inputs = self.tokenizer(text, return_tensors="pt").to(device)  # Move inputs to the same device

            # Generate summary
            outputs = self.model.generate(**inputs, max_length=50)

            # Decode result
            summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            print(summary)
            # summary = self.summarizer(
            #     text,
            #     max_length=50,  # Adjust for desired summary length
            #     min_length=30,
            #     length_penalty=1.0,
            #     num_beams=4,
            #     no_repeat_ngram_size=3,
            #     early_stopping=True
            # )[0]["summary_text"]
            # Decode and print summary
           # summary = tokenizer.decode(summary, skip_special_tokens=True, clean_up_tokenization_spaces=True)
         #   summary = summary.replace("<extra_id_0>", "").strip()
            return summary
        except Exception as e:
            print(f"Error summarizing text: {e}")
            return text  # Fallback to original text on error

