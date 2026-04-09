from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


@dataclass
class SemanticClusteringConfig:
    model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    similarity_threshold: float = 0.84
    max_label_length: int = 120
    normalize_arabic: bool = False
    verbose: bool = False


# =========================================================
# Loading + normalization
# =========================================================

def load_queries_csv(csv_path: str | Path, encoding: str = "utf-8") -> pd.DataFrame:
    return pd.read_csv(csv_path, encoding=encoding)


def normalize_queries_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]

    aliases = {
        "student_id": "user_id",
        "user": "user_id",
        "userid": "user_id",
        "query_text": "query",
        "search_query": "query",
        "question": "query",
        "class": "name",
        "lecture_name": "name",
        "lesson": "name",
        "type": "source_type",
        "source": "source_type",
        "entity": "entity_id",
    }

    for old, new in aliases.items():
        if old in out.columns and new not in out.columns:
            out = out.rename(columns={old: new})

    required = {"user_id", "query"}
    missing = required - set(out.columns)
    if missing:
        raise ValueError(f"Missing required columns in queries CSV: {sorted(missing)}")

    if "name" not in out.columns:
        out["name"] = None

    if "source_type" not in out.columns:
        out["source_type"] = None

    if "entity_id" not in out.columns:
        out["entity_id"] = None

    return out


def normalize_source_type(value: Any) -> str:
    if pd.isna(value):
        return "unknown"
    s = str(value).strip().lower()
    if s in {"lecture", "class", "lesson"}:
        return "lecture"
    if s in {"course", "global"}:
        return "course"
    return s


def normalize_query_text(text: Any, normalize_arabic: bool = False) -> str:
    if text is None or pd.isna(text):
        return ""

    s = str(text).strip()
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()

    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[\"'`“”‘’.,;:!?()\[\]{}<>|/\\\-_=+~*#%^&]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    if normalize_arabic:
        s = (
            s.replace("أ", "ا")
             .replace("إ", "ا")
             .replace("آ", "ا")
             .replace("ى", "ي")
             .replace("ة", "ه")
        )

    return s


def prepare_queries_df(
    csv_path: str | Path,
    encoding: str = "utf-8",
    normalize_arabic: bool = False,
) -> pd.DataFrame:
    df = load_queries_csv(csv_path, encoding=encoding)
    df = normalize_queries_columns(df)

    df = df.copy()
    df["source_type"] = df["source_type"].map(normalize_source_type)
    df["query"] = df["query"].astype(str)
    df["normalized_query"] = df["query"].map(
        lambda x: normalize_query_text(x, normalize_arabic=normalize_arabic)
    )

    df = df[df["normalized_query"] != ""].copy()
    return df.reset_index(drop=True)


# =========================================================
# Embeddings + clustering
# =========================================================

def load_embedding_model(model_name: str) -> SentenceTransformer:
    return SentenceTransformer(model_name)


class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1


def build_unique_query_index(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("normalized_query", as_index=False)
        .agg(
            query_frequency=("normalized_query", "size"),
            unique_students=("user_id", "nunique"),
            query=("query", lambda s: s.iloc[0]),
        )
        .sort_values(
            ["query_frequency", "unique_students", "normalized_query"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )


def cluster_queries_semantically(
    unique_queries_df: pd.DataFrame,
    model: SentenceTransformer,
    config: SemanticClusteringConfig,
) -> pd.DataFrame:
    if unique_queries_df.empty:
        out = unique_queries_df.copy()
        out["cluster_id"] = []
        return out

    texts = unique_queries_df["normalized_query"].tolist()
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=config.verbose,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    sim = embeddings @ embeddings.T
    n = len(texts)
    uf = UnionFind(n)

    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= config.similarity_threshold:
                uf.union(i, j)

    root_to_cluster = {}
    cluster_ids = []
    next_cluster = 1

    for i in range(n):
        root = uf.find(i)
        if root not in root_to_cluster:
            root_to_cluster[root] = next_cluster
            next_cluster += 1
        cluster_ids.append(root_to_cluster[root])

    out = unique_queries_df.copy()
    out["cluster_id"] = cluster_ids
    return out


def attach_cluster_ids_back(
    original_df: pd.DataFrame,
    clustered_unique_queries_df: pd.DataFrame,
) -> pd.DataFrame:
    mapping = clustered_unique_queries_df[["normalized_query", "cluster_id"]].drop_duplicates()
    return original_df.merge(mapping, on="normalized_query", how="left")


# =========================================================
# Cluster labeling
# =========================================================

def pick_cluster_label(cluster_df: pd.DataFrame, max_label_length: int = 120) -> str:
    agg = (
        cluster_df.groupby("query", as_index=False)
        .agg(
            query_frequency=("query", "size"),
            qlen=("query", lambda s: min(len(str(x)) for x in s)),
        )
        .sort_values(["query_frequency", "qlen"], ascending=[False, True])
    )

    if agg.empty:
        return ""

    label = str(agg.iloc[0]["query"]).strip()
    if len(label) > max_label_length:
        label = label[: max_label_length - 3].rstrip() + "..."
    return label


def build_cluster_variants(cluster_df: pd.DataFrame) -> str:
    variants = (
        cluster_df.groupby("query", as_index=False)
        .agg(query_frequency=("query", "size"))
        .sort_values(["query_frequency", "query"], ascending=[False, True])
    )["query"].tolist()
    return " | ".join(variants)


# =========================================================
# Dedup logic
# =========================================================

def dedup_user_concept_per_class(df_with_clusters: pd.DataFrame) -> pd.DataFrame:
    lecture_df = df_with_clusters[df_with_clusters["source_type"] == "lecture"].copy()
    if lecture_df.empty:
        return lecture_df
    return lecture_df.drop_duplicates(subset=["user_id", "name", "cluster_id"]).reset_index(drop=True)


def dedup_user_concept_coursewide(df_with_clusters: pd.DataFrame) -> pd.DataFrame:
    return df_with_clusters.drop_duplicates(subset=["user_id", "cluster_id"]).reset_index(drop=True)


# =========================================================
# Table generation
# =========================================================

def build_class_level_clustered_tables(
    clustered_queries_df: pd.DataFrame,
    top_n_per_class: int = 10,
) -> Dict[str, pd.DataFrame]:
    dedup = dedup_user_concept_per_class(clustered_queries_df)
    lecture_df = clustered_queries_df[clustered_queries_df["source_type"] == "lecture"].copy()

    if lecture_df.empty:
        return {}

    students_by_cluster = (
        dedup.groupby(["name", "cluster_id"], as_index=False)
        .agg(unique_students=("user_id", "nunique"))
    )

    total_queries = (
        lecture_df.groupby(["name", "cluster_id"], as_index=False)
        .agg(total_queries=("query", "size"))
    )

    rows = []
    for (lecture_name, cluster_id), grp in lecture_df.groupby(["name", "cluster_id"]):
        rows.append(
            {
                "name": lecture_name,
                "cluster_id": cluster_id,
                "concept": pick_cluster_label(grp),
                "variants": build_cluster_variants(grp),
            }
        )

    meta = pd.DataFrame(rows)

    merged = (
        meta.merge(students_by_cluster, on=["name", "cluster_id"], how="left")
            .merge(total_queries, on=["name", "cluster_id"], how="left")
    )

    tables = {}
    for lecture_name, grp in merged.groupby("name"):
        tables[lecture_name] = (
            grp.sort_values(["unique_students", "total_queries", "concept"], ascending=[False, False, True])
               .head(top_n_per_class)
               [["concept", "variants", "unique_students", "total_queries"]]
               .reset_index(drop=True)
        )

    return tables


def build_course_level_clustered_table(
    clustered_queries_df: pd.DataFrame,
    top_n_course: int = 20,
) -> pd.DataFrame:
    if clustered_queries_df.empty:
        return pd.DataFrame(
            columns=[
                "concept",
                "variants",
                "unique_students",
                "total_queries",
                "lectures_involved",
                "seen_in_course_level",
                "seen_in_class_level",
            ]
        )

    dedup_course = dedup_user_concept_coursewide(clustered_queries_df)

    students = (
        dedup_course.groupby("cluster_id", as_index=False)
        .agg(unique_students=("user_id", "nunique"))
    )

    total_queries = (
        clustered_queries_df.groupby("cluster_id", as_index=False)
        .agg(total_queries=("query", "size"))
    )

    lectures_involved = (
        clustered_queries_df[clustered_queries_df["source_type"] == "lecture"]
        .dropna(subset=["name"])
        .groupby("cluster_id", as_index=False)
        .agg(lectures_involved=("name", "nunique"))
    )

    rows = []
    for cluster_id, grp in clustered_queries_df.groupby("cluster_id"):
        rows.append(
            {
                "cluster_id": cluster_id,
                "concept": pick_cluster_label(grp),
                "variants": build_cluster_variants(grp),
                "seen_in_course_level": int((grp["source_type"] == "course").any()),
                "seen_in_class_level": int((grp["source_type"] == "lecture").any()),
            }
        )

    meta = pd.DataFrame(rows)

    out = (
        meta.merge(students, on="cluster_id", how="left")
            .merge(total_queries, on="cluster_id", how="left")
            .merge(lectures_involved, on="cluster_id", how="left")
    )

    out["lectures_involved"] = out["lectures_involved"].fillna(0).astype(int)

    return (
        out.sort_values(
            ["unique_students", "total_queries", "lectures_involved", "concept"],
            ascending=[False, False, False, True],
        )
        .head(top_n_course)[
            [
                "concept",
                "variants",
                "unique_students",
                "total_queries",
                "lectures_involved",
                "seen_in_course_level",
                "seen_in_class_level",
            ]
        ]
        .reset_index(drop=True)
    )


# =========================================================
# Export
# =========================================================

def export_class_tables_to_csv(
    class_tables: Dict[str, pd.DataFrame],
    output_dir: str | Path,
    prefix: str = "class_top_queries",
) -> List[Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for lecture_name, df in class_tables.items():
        safe_name = re.sub(r"[^\w\-]+", "_", str(lecture_name), flags=re.UNICODE).strip("_")
        out_path = output_dir / f"{prefix}_{safe_name}.csv"
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        paths.append(out_path)
    return paths


def export_course_table_to_csv(course_table: pd.DataFrame, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    course_table.to_csv(output_path, index=False, encoding="utf-8-sig")
    return output_path


# =========================================================
# Main orchestration
# =========================================================

def analyze_queries_csv_semantic(
    csv_path: str | Path,
    config: Optional[SemanticClusteringConfig] = None,
    top_n_per_class: int = 10,
    top_n_course: int = 20,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    config = config or SemanticClusteringConfig()

    raw_df = prepare_queries_df(
        csv_path=csv_path,
        encoding=encoding,
        normalize_arabic=config.normalize_arabic,
    )

    unique_query_index = build_unique_query_index(raw_df)

    model = load_embedding_model(config.model_name)
    clustered_unique_queries = cluster_queries_semantically(
        unique_query_index,
        model=model,
        config=config,
    )

    clustered_queries_df = attach_cluster_ids_back(raw_df, clustered_unique_queries)

    class_tables = build_class_level_clustered_tables(
        clustered_queries_df,
        top_n_per_class=top_n_per_class,
    )

    course_table = build_course_level_clustered_table(
        clustered_queries_df,
        top_n_course=top_n_course,
    )

    return {
        "raw_queries_df": raw_df,
        "unique_query_index": unique_query_index,
        "clustered_unique_queries": clustered_unique_queries,
        "clustered_queries_df": clustered_queries_df,
        "course_table": course_table,
        "class_tables": class_tables,
    }


# =========================================================
# Example usage
# =========================================================

if __name__ == "__main__":
    config = SemanticClusteringConfig(
        similarity_threshold=0.84,
        verbose=True,
    )

    result = analyze_queries_csv_semantic(
        csv_path="/home/roy/Downloads/attachments/queries.csv",
        config=config,
        top_n_per_class=10,
        top_n_course=20,
        encoding="utf-8",
    )

    print("\n=== COURSE TABLE ===")
    print(result["course_table"].to_string(index=False))

    print("\n=== CLASS TABLES ===")
    for class_name, table in result["class_tables"].items():
        print(f"\n--- {class_name} ---")
        print(table.to_string(index=False))

    export_course_table_to_csv(result["course_table"], "outputs/course_top_queries.csv")
    export_class_tables_to_csv(result["class_tables"], "outputs/")