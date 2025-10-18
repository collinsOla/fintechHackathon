
import json
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from openai import OpenAI
from sentence_transformers import SentenceTransformer, util
import os
from tqdm import tqdm

# ----------------------------
# Step 0: Initialize clients
# ----------------------------
# OpenAI client for DeepSeek-V3.2-Exp
HF_TOKEN = os.environ.get("HF_API_KEY")
if not HF_TOKEN:
    raise ValueError("Please set your HF_API_KEY environment variable.")

client = OpenAI(base_url="https://router.huggingface.co/v1", api_key=HF_TOKEN)

# Local Sentence Transformer for embeddings
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# ----------------------------
# Step 1: Helper — Get embeddings locally
# ----------------------------
def get_embeddings_local(texts, batch_size=16):
    embeddings = []
    for i in tqdm(range(0, len(texts), batch_size), desc="Generating embeddings"):
        batch = texts[i:i+batch_size]
        batch_emb = embedding_model.encode(batch, convert_to_tensor=True)
        embeddings.extend(batch_emb.cpu().numpy())
    return np.array(embeddings)

# ----------------------------
# Step 2: Load metadata
# ----------------------------
with open("arxiv_recent_qfin_15.json", "r", encoding="utf-8") as f: ### CHange to correct file
    data_json = json.load(f)

data = pd.DataFrame(data_json)
print(f"Loaded {len(data)} papers.")

# ----------------------------
# Step 3: Generate embeddings for "title + abstract" locally
# ----------------------------
combined_texts = (data["title"] + ". " + data["abstract"]).tolist()
abstract_embeddings = get_embeddings_local(combined_texts)
print("Embeddings generated locally using SentenceTransformer.")

# ----------------------------
# Step 4: Cluster papers
# ----------------------------
num_clusters = 10
kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
clusters = kmeans.fit_predict(abstract_embeddings)
data["Cluster"] = clusters
print(f"Papers clustered into {num_clusters} clusters.")

# ----------------------------
# Step 5: Summarize clusters & compute semantic similarities
# ----------------------------
cluster_summaries = []
intra_sims, semantic_sims = [], []

for i in range(num_clusters):
    cluster_data = data[data["Cluster"] == i]
    cluster_emb = abstract_embeddings[data["Cluster"] == i]

    titles = "; ".join(cluster_data["title"].tolist()[:3])
    categories = ", ".join(set(cluster_data.get("categories", pd.Series(["N/A"])).tolist()))
    authors = ", ".join(set(cluster_data.get("authors", pd.Series(["N/A"])).tolist()[:5]))
    summary = f"Cluster {i+1} covers categories: {categories}. Example papers: {titles}. Authors include: {authors}."
    cluster_summaries.append(summary)

    # Intra-cluster similarity
    if len(cluster_emb) > 1:
        sim_matrix = cosine_similarity(cluster_emb)
        avg_intra = np.mean(sim_matrix[np.triu_indices_from(sim_matrix, k=1)])
    else:
        avg_intra = 1.0
    intra_sims.append(avg_intra)

    # Semantic similarity (summary vs cluster embeddings) locally
    summary_emb = embedding_model.encode([summary], convert_to_tensor=True).cpu().numpy()
    avg_sem = cosine_similarity(summary_emb, cluster_emb).mean()
    semantic_sims.append(avg_sem)

    print(f"\nCluster {i+1} Summary:\n{summary}")
    print(f"Intra-cluster similarity: {avg_intra:.4f}")
    print(f"Semantic similarity: {avg_sem:.4f}")

# ----------------------------
# Step 6: Select top clusters
# ----------------------------
cluster_scores = [(i, (intra_sims[i] + semantic_sims[i]) / 2) for i in range(num_clusters)]
cluster_scores.sort(key=lambda x: x[1], reverse=True)
top_n = 5
selected_clusters = [i for i, _ in cluster_scores[:top_n]]
print("\nTop clusters selected:", selected_clusters)

# ----------------------------
# Step 7: Generate prompt for DeepSeek-V3.2-Exp
# ----------------------------
prompt = "You are an AI business strategist. Based on the following research insights, propose 1 innovative but realistic fintech-related business ideas. Include title and short description, and write a market analysis and talk about the real world problems that are being solved, and create separate paragraphs for each . Don't talk about the clusters, talk specifically about the information in the clusters. Don't try to aggregate all the information, just ascertain the best idea from the information given\n\n"
for i in selected_clusters:
    prompt += cluster_summaries[i] + "\n\n"

print("\nGenerated Prompt:\n", prompt)

# ----------------------------
# Step 8: Call DeepSeek-V3.2-Exp for business ideas
# ----------------------------
completion = client.chat.completions.create(
    model="deepseek-ai/DeepSeek-V3.2-Exp:novita",
    messages=[{"role": "user", "content": prompt}],
    temperature=0.7
)

deepseek_output = completion.choices[0].message
print("\nDeepSeek Output:\n", deepseek_output)

# ----------------------------
# Step 9: Save results locally
# ----------------------------
results = {
    "selected_clusters": selected_clusters,
    "cluster_summaries": [cluster_summaries[i] for i in selected_clusters],
    "deepseek_output": deepseek_output
}

with open("cluster_analysis_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print("\nAll outputs printed in terminal and saved to 'cluster_analysis_results.json'")

