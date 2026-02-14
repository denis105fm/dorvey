"""Keyword clustering with scikit-learn."""

from typing import List
import re


def cluster_keywords(keywords: List[str], n_clusters: int = 5) -> List[int]:
    """
    Cluster keywords by similarity. Returns cluster_id for each keyword.
    Uses TF-IDF-like bag of words and KMeans.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
    except ImportError:
        return [0] * len(keywords)
    if not keywords or len(keywords) < 2:
        return [0] * len(keywords)
    n_clusters = min(n_clusters, len(keywords))
    vec = TfidfVectorizer(lowercase=True, tokenizer=lambda x: re.findall(r"\w+", x))
    X = vec.fit_transform(keywords)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    labels = kmeans.fit_predict(X)
    return labels.tolist()
