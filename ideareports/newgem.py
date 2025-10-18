import google.genai as genai
import os
import json
from pathlib import Path
from criteria import crit

# Your Gemini function, slightly modified to return output
def getData(criteria, data):
    client = genai.Client(api_key="AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Based on criteria" + criteria + " analyse this data into a standard human readable format: " + data
    )
    return response.text


# Folder containing your JSON files
data_folder = Path("./Data")
output_folder = Path("./processed")
output_folder.mkdir(exist_ok=True)

# How many papers to process per file
papers_to_process = 15

# Loop over all JSON files in Data folder
for input_file in data_folder.glob("arxiv_*_100.json"):
    with open(input_file, "r", encoding="utf-8") as f:
        papers = json.load(f)

    processed_papers = []

    for paper in papers[:papers_to_process]:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")

        # Format the data string exactly like your example
        data_str = f"title: {title}, abstract: {abstract}"

        # Call Gemini
        gemini_output = getData(crit, data_str)

        # Combine original paper info + Gemini output
        combined = paper.copy()
        combined["gemini_output"] = gemini_output

        processed_papers.append(combined)

    # Save new JSON for this category
    output_file = output_folder / f"{input_file.stem}_processed.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(processed_papers, f, indent=2)

    print(f"Processed {len(processed_papers)} papers from {input_file.name}, saved to {output_file.name}")
