"""Download the pinned Hugging Face train split."""

from __future__ import annotations

import logging

import pandas as pd
from datasets import load_dataset

logger = logging.getLogger(__name__)


def download_train_split(dataset_id: str, dataset_revision: str) -> pd.DataFrame:
    """Fetch the train split at the configured revision and return a DataFrame."""
    logger.info(
        "Downloading dataset %s at revision %s",
        dataset_id,
        dataset_revision,
    )
    dataset = load_dataset(
        dataset_id,
        split="train",
        revision=dataset_revision,
    )
    frame = dataset.to_pandas()
    if not isinstance(frame, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame from the train split")
    logger.info("Downloaded %s raw listings", len(frame))
    return frame
