from dataclasses import dataclass
from typing import Set

@dataclass
class ProcessingConfig:
    """Configuration for PII scrubbing and processing"""
    skip_file_types: Set[str] = None  # File extensions to skip PII scrubbing
    max_workers: int = 4  # Maximum number of parallel workers
    ocr_confidence_threshold: float = 80.0  # Minimum confidence for OCR results
    enable_progress_bar: bool = True
    retry_attempts: int = 3
    retry_delay: int = 1  # seconds

    def __post_init__(self):
        if self.skip_file_types is None:
            self.skip_file_types = set()

# Default configuration for the application
default_config = ProcessingConfig(
    skip_file_types={'txt', 'csv'},  # Skip PII scrubbing for these types
    max_workers=4,
    ocr_confidence_threshold=75.0,
    enable_progress_bar=True,
    retry_attempts=3
)
