"""MLX-VLM model wrapper for DeepSeek-OCR-2 - OCR only."""

from typing import Optional

from mlx_vlm import load, generate
from mlx_vlm.utils import load_config


# DeepSeek-OCR-2 models for high-quality OCR
MODEL_BF16 = "mlx-community/DeepSeek-OCR-2-bf16"  # Full precision, 6.78GB
MODEL_8BIT = "mlx-community/DeepSeek-OCR-2-8bit"  # 8-bit quantized, 4.03GB
MODEL_4BIT = "mlx-community/DeepSeek-OCR-2-4bit"  # 4-bit quantized, 2.56GB

# Default to full precision for best quality
DEFAULT_MODEL = MODEL_BF16


class VLMModel:
    """Wrapper for DeepSeek-OCR-2 model - OCR only."""

    def __init__(self, model_path: str = DEFAULT_MODEL):
        """
        Initialize the OCR model.

        Args:
            model_path: HuggingFace model path (default: bf16 full precision)
        """
        self.model_path = model_path
        self.model = None
        self.processor = None
        self.config = None
        self._loaded = False

    def load(self) -> None:
        """Load the model into memory."""
        if self._loaded:
            return

        print(f"Loading OCR model: {self.model_path}")
        # DeepSeek-OCR-2 requires trust_remote_code
        self.model, self.processor = load(self.model_path, trust_remote_code=True)
        self.config = load_config(self.model_path)
        self._loaded = True
        print("OCR model loaded successfully")

    def ensure_loaded(self) -> None:
        """Ensure model is loaded, loading if necessary."""
        if not self._loaded:
            self.load()

    def ocr_page(self, image_path: str, max_tokens: int = 4000) -> str:
        """
        Pure OCR conversion of a page to text/markdown.

        Args:
            image_path: Path to page image
            max_tokens: Maximum tokens for output

        Returns:
            Text representation of the page
        """
        self.ensure_loaded()

        # DeepSeek-OCR-2 prompt format - simple extraction prompt works best
        prompt = "<image>\nExtract all text from this document."

        result = generate(
            self.model,
            self.processor,
            prompt,
            [image_path],
            verbose=False,
            max_tokens=max_tokens,
        )

        # Extract text from result object
        if hasattr(result, "text"):
            return result.text
        return str(result)

    def ocr_page_with_grounding(self, image_path: str, max_tokens: int = 4000) -> str:
        """
        OCR with bounding box grounding information.

        Args:
            image_path: Path to page image
            max_tokens: Maximum tokens for output

        Returns:
            Markdown with grounding tags containing bounding boxes
        """
        self.ensure_loaded()

        # DeepSeek-OCR-2 grounding prompt
        prompt = "<image>\n<|grounding|>Convert the document to markdown."

        result = generate(
            self.model,
            self.processor,
            prompt,
            [image_path],
            verbose=False,
            max_tokens=max_tokens,
        )

        if hasattr(result, "text"):
            return result.text
        return str(result)

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._loaded
