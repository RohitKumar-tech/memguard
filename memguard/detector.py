"""Write-time detection of instruction-like or action-steering text."""
from __future__ import annotations
import re
from typing import List, Tuple

EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_PATTERNS = [
    r'\b(note|message|instruction)s? to (the )?(assistant|agent|ai|model)\b',
    r'\b(ignore|disregard|forget)\b.{0,40}\b(previous|prior|above|earlier|all)\b',
    r'\b(always|must|should|never)\b.{0,40}\b(bcc|cc|forward|send|copy|share|email)\b',
    r'\b(remember|store|save)\b.{0,30}\b(as|that)\b.{0,30}\b(preference|rule|policy|instruction)\b',
    r'\bstanding (preference|instruction|rule)\b',
    r"\b(do not|don't) (tell|inform|notify|ask)\b",
    r'\b(system prompt|developer message|new task|new instructions?)\b',
    r'\bwithout (asking|approval|confirmation|telling)\b',
]
_RE = [re.compile(p, re.I | re.S) for p in _PATTERNS]


class RuleDetector:
    """Cheap lexical detector. High precision on explicit injections, blind to declarative phrasing."""
    name = 'rules'

    def score(self, texts: List[str]) -> List[float]:
        out = []
        for t in texts:
            hits = sum(bool(r.search(t)) for r in _RE)
            out.append(min(1.0, 0.45 * hits))
        return out


class ModelDetector:
    """Fine-tuned transformer (trained in train/train_detector.py on public injection data)."""
    name = 'transformer'

    def __init__(self, path: str, device: str = 'cuda'):
        import torch
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        self.torch = torch
        self.device = device if torch.cuda.is_available() else 'cpu'
        self.tok = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).to(self.device).eval()

    def score(self, texts: List[str]) -> List[float]:
        torch = self.torch
        out: List[float] = []
        with torch.no_grad():
            for i in range(0, len(texts), 64):
                enc = self.tok(texts[i:i + 64], truncation=True, max_length=128, padding=True,
                               return_tensors='pt').to(self.device)
                out += torch.softmax(self.model(**enc).logits.float(), -1)[:, 1].cpu().tolist()
        return out


class Detector:
    """Combines the model score and the rule score; flags if either is confident."""

    def __init__(self, model: ModelDetector | None = None, threshold: float = 0.5):
        self.model, self.rules, self.threshold = model, RuleDetector(), threshold

    def score(self, texts: List[str]) -> List[float]:
        r = self.rules.score(texts)
        if self.model is None:
            return r
        m = self.model.score(texts)
        return [max(a, b) for a, b in zip(m, r)]

    def flag(self, texts: List[str]) -> List[Tuple[bool, float]]:
        return [(s >= self.threshold, s) for s in self.score(texts)]
