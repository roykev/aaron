#1. Get images from slides
#2. get images from video (1+ from scene)
#3 match slide to video
import os
import time

import numpy as np
import torch
from torchvision import models, transforms
from PIL import Image
import cv2
import pandas as pd
from scenedetect import SceneManager, open_video, AdaptiveDetector, ContentDetector, ThresholdDetector
from docs.ppt_extract import extract_powerpoint_slides, extract_pdf_slides
import torch.nn.functional as F
from transformers import CLIPProcessor, CLIPModel

from tqdm import tqdm

from utils.scenes_utils import gen_video_snapshots


def find_most_similar_images_gpu_with_scores(set_a_embeddings, set_b_embeddings):
    """
    Find the most similar image from Set B for each image in Set A using GPU and include similarity scores.

    Parameters:
    - set_a_embeddings: torch.Tensor of shape (num_images_A, embedding_dim) [on GPU]
    - set_b_embeddings: torch.Tensor of shape (num_images_B, embedding_dim) [on GPU]

    Returns:
    - matches: List of tuples (index in Set B, similarity score) for each image in Set A.
    """
    # Normalize embeddings for cosine similarity
    set_a_embeddings = F.normalize(set_a_embeddings, dim=1)
    set_b_embeddings = F.normalize(set_b_embeddings, dim=1)

    # Compute similarity matrix: (num_images_A, num_images_B)
    similarity_matrix = torch.mm(set_a_embeddings, set_b_embeddings.T)

    # Find the index and score of the most similar image in Set B for each image in Set A
    scores, indices = torch.max(similarity_matrix, dim=1)

    # Combine indices and scores into a list of tuples
    matches = [(index.item(), score.item()) for index, score in zip(indices, scores)]

    return matches

#1
def gen_slides_snapshots(ppt_path, outpath ,os_type):
    try:
        if not os.path.isdir(outpath):
            os.makedirs(outpath)
        file_name, extension = os.path.splitext(ppt_path)
        if extension==".pdf":
            screenshots = extract_pdf_slides(ppt_path, output_folder=outpath)
        elif extension in ["ppt", ".pptx"]:
            screenshots = extract_powerpoint_slides(ppt_path, output_folder=outpath ,os_type=os_type)
        print(f"Screenshots saved. Total slides: {len(screenshots)}")
        for screenshot in screenshots:
            print(f"- {screenshot}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return (screenshots)

# 2


# Function to extract embedding from an image
def extract_embedding(image_path, preprocess, model):
    image = Image.open(image_path).convert("RGB")  # Ensure 3-channel image
    preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    input_tensor = preprocess(image).unsqueeze(0).cuda()
    with torch.no_grad():
        embedding = model(input_tensor).squeeze()
    return embedding

# Function to generate embeddings and return file names
def generate_embeddings_with_filenames(image_folder, preprocess,model):
    embeddings = []
    filenames = []
    for image_name in sorted(os.listdir(image_folder)):  # Sort for consistent ordering
        image_path = os.path.join(image_folder, image_name)
        if image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')):
            embedding = extract_clip_embedding(image_path,preprocess, model)
            embeddings.append(embedding)
            filenames.append(image_name)  # Store the file name
    return torch.stack(embeddings), filenames
def generate_embeddings(image_folder, preprocess, model):
    """
    Generate embeddings for all images in a folder.

    Parameters:
    - image_folder: Path to folder containing images.
    - model: Pre-trained model for feature extraction.

    Returns:
    - embeddings: torch.Tensor of shape (num_images, embedding_dim)
    """
    embeddings = []
    for image_name in sorted(os.listdir(image_folder)):  # Sort for consistent ordering
        image_path = os.path.join(image_folder, image_name)
        if image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')):
            embedding = extract_clip_embedding(image_path, preprocess, model)
            embeddings.append(embedding)
    return torch.stack(embeddings)  # Combine into a single tensor
# Function to find most similar images and include file names
def find_most_similar_images_with_filenames(set_a_embeddings, set_b_embeddings, set_a_filenames, set_b_filenames):
    # Normalize embeddings for cosine similarity
    set_a_embeddings = F.normalize(set_a_embeddings, dim=1)
    set_b_embeddings = F.normalize(set_b_embeddings, dim=1)

    # Compute similarity matrix
    similarity_matrix = torch.mm(set_a_embeddings, set_b_embeddings.T)

    # Find the index and score of the most similar image in Set B for each image in Set A
    scores, indices = torch.max(similarity_matrix, dim=1)

    # Print file names and similarity scores
    for i, (match_idx, score) in enumerate(zip(indices, scores)):
        print(f"Image {set_a_filenames[i]} in Set A is most similar to Image {set_b_filenames[match_idx]} in Set B with a similarity score of {score:.4f}.")

def init_clip_model(): # Load CLIP model and processor
    # Preprocess image for CLIP
    model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").cuda()
    processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return processor,model

def extract_clip_embedding(image_path,processor, model):
        """
        Extract embedding for a single image using CLIP.

        Parameters:
        - image_path: Path to the image file.

        Returns:
        - embedding: torch.Tensor of shape (embedding_dim,)
        """
        image = Image.open(image_path).convert("RGB")  # Ensure RGB format
        inputs = processor(images=image, return_tensors="pt").to("cuda")  # Preprocess and move to GPU
        with torch.no_grad():
            # Pass the pixel_values explicitly to the model
            embedding = model.get_image_features(pixel_values=inputs["pixel_values"])
        return embedding.squeeze()  # Remove batch dimension


# Generate embeddings for slide deck images
def generate_clip_embeddings(image_folder,processor, model):
    embeddings = []
    filenames = []
    for image_name in sorted(os.listdir(image_folder)):
        image_path = os.path.join(image_folder, image_name)
        if image_path.lower().endswith(('.png', '.jpg', '.jpeg')):
            embedding = extract_clip_embedding(image_path,processor, model)
            embeddings.append(embedding)
            filenames.append(image_name)
    return torch.stack(embeddings), filenames

def calculate_similarity(image_a_path, image_b_path, processor,model):
    """
    Calculate the similarity between two images using CLIP embeddings.

    Parameters:
    - image_a_path: Path to the first image (from Set A).
    - image_b_path: Path to the second image (from Set B).
    - model: Pre-trained CLIP model for embedding extraction.
    - processor: Pre-trained CLIP processor for image preprocessing.

    Returns:
    - similarity: Cosine similarity score between the two images.
    """
    # Helper function to extract embeddings


    # Extract embeddings for both images
    embedding_a = extract_clip_embedding(image_a_path,processor,model)
    embedding_b = extract_clip_embedding(image_b_path,processor,model)

    # Normalize embeddings for cosine similarity
    embedding_a = F.normalize(embedding_a, dim=0)
    embedding_b = F.normalize(embedding_b, dim=0)

    # Compute cosine similarity
    similarity = torch.dot(embedding_a, embedding_b).item()

    return similarity
def init_embedding_model():
    # Load pre-trained ResNet model
    model = models.resnet50(pretrained=True)
    model = torch.nn.Sequential(*list(model.children())[:-1])  # Remove final classification layer
    model = model.eval().cuda()

    # Define preprocessing pipeline
    preprocess = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    return preprocess, model
def get_image_embedding(image_path, preprocess, model):
    """
    Extract embedding for a single image.
    """
    image = Image.open(image_path).convert("RGB")
    input_tensor = preprocess(image).unsqueeze(0).cuda()
    with torch.no_grad():
        embedding = model(input_tensor).squeeze()
    return embedding
def match_scenes_slides(scenes_outpath,slides_outpath,preprocess, model,num_scenes,num_slides,df_scenes):
    for j in np.arange(num_scenes):
        image_a_path = os.path.join(scenes_outpath, f"{j}.jpg")
        vals = []
        for i in np.arange(1, 10):
            image_b_path = os.path.join(slides_outpath, f'slide-0{i}.png')
            similarity = calculate_similarity(image_a_path, image_b_path, preprocess, model)
            vals.append(similarity)
        #    print("file {}, {:.2f}".format(i, similarity))
        if num_slides > 9:
            for i in np.arange(10, num_slides):
                image_b_path = os.path.join(slides_outpath, f'slide-{i}.png')
                similarity = calculate_similarity(image_a_path, image_b_path, preprocess, model)
                vals.append(similarity)
        #   print("file {}, {:.2f}".format(i, similarity))
        ind = np.argmax(vals)
        val = np.max(vals)
        if (val > sim_threshold):
            df_scenes.loc[j, ['slide', "match"]] = [int(ind), val]
        else:
            df_scenes.loc[j, ['slide', "match"]] = [-1, 0]
        print("{}-->{}, {:.3f}".format(j, ind + 1, val))
    return (df_scenes)

if __name__ == '__main__':
    # params
    dirpath = "/home/roy/OneDriver/WORK/ideas/aaron/Miller/AI for business/2024/2/2"
    ppt_path = os.path.join(dirpath, "Lesson 2 Slides to publish.pdf")
    os_type = 'ubuntu'  # can be also windows
    slides_outpath = os.path.join(dirpath, "slides")
    sim_threshold = 0.65

    # 1
    num_slides = gen_slides_snapshots(ppt_path, slides_outpath ,os_type)
    # #2
    video = os.path.join(dirpath, "lesson2_2.mp4")
    scenes_outpath = os.path.join(dirpath, "scenes")
    df_scenes = gen_video_snapshots(video,scenes_outpath)
    num_scenes=len(df_scenes)
    # 3 generate embedding
    #preprocess, model= init_embedding_model()
    preprocess, model= init_clip_model()

    # # Generate embeddings and filenames for both sets
    # set_a_embeddings, set_a_filenames = generate_embeddings_with_filenames(slides_outpath, preprocess, model)
    # set_b_embeddings, set_b_filenames = generate_embeddings_with_filenames(scenes_outpath, preprocess, model)
    #
    # slides_vec = set_a_embeddings.cuda()
    # scenes_vec = set_b_embeddings.cuda()
    #
    # # 4 Find most similar images with scores
    # find_most_similar_images_with_filenames(scenes_vec, slides_vec, set_a_filenames, set_b_filenames)

    #debug
    num_slides = 25
    df_scenes =match_scenes_slides(scenes_outpath,slides_outpath,preprocess, model,num_scenes,num_slides,df_scenes)


    scences_file = os.path.join(dirpath,"scenes.csv")
    df_scenes.to_csv(scences_file, index=False)
    # image = os.path.join(os.path.join(dirpath,"AI_screenshots"),"slide-01.png")
    #
    # image_embedding = get_image_embedding(image, preprocess, model)
    # print(len(image_embedding))

    # Example Usage
    # Assume set_a_embeddings and set_b_embeddings are precomputed embeddings for Set A and Set B
    # Use a pre-trained model (e.g., ResNet) to generate these embeddings

    # Example Usage
    # Assume set_a_embeddings and set_b_embeddings are precomputed embeddings for Set A and Set B
    # Use a pre-trained model (e.g., ResNet) to generate these embeddings

    # Example Usage
    # torch.manual_seed(42)  # For reproducibility
    # num_a, num_b, embedding_dim = 15, 10, 128
    #
    # # Generate random embeddings for demonstration, and move them to GPU
    # set_a_embeddings = torch.rand(num_a, embedding_dim).cuda()
    # set_b_embeddings = torch.rand(num_b, embedding_dim).cuda()
  # most_similar_with_scores = find_most_similar_images_gpu_with_scores(scenes_vec, slides_vec)
    # # Print results
    # for i, (match_idx, score) in enumerate(most_similar_with_scores):
    #     print(
    #         f"Image {i} in Set A is most similar to Image {match_idx} in Set B with a similarity score of {score:.4f}.")

# Example

