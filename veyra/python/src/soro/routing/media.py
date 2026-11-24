"""Speech and image requests for UPP pointers on an omni backbone (Gemma 4 E2B/E4B).

The tool catalog stays text and is encoded once; only the *request* changes modality.
``MediaEncoder`` turns a wav or an image into the backbone's own soft tokens (its
frozen audio / vision tower + projector, exactly what the backbone sees in normal
use) and returns them with the token-id layout the request needs:

    {"tokens": [boa, MEDIA, MEDIA, ..., eoa], "embeds": Tensor(n_media, d)}

``MEDIA`` (-3) marks the positions whose embeddings come from ``embeds``. UPP places
these tokens inside the request block at the fixed request offset, so every
exactness property of the block layout (composition, order equivariance, budget
nesting) holds unchanged for spoken and visual requests.
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
import torch

MEDIA = -3
SR = 16_000


def load_wav_16k(path: str | Path) -> np.ndarray:
    """Mono float32 at 16 kHz (Kokoro writes 24 kHz; Audio2Tool varies)."""
    import soundfile as sf

    wav, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if wav.ndim > 1:
        wav = wav.mean(axis=1)
    if sr != SR:
        try:
            from math import gcd

            from scipy.signal import resample_poly

            g = gcd(int(sr), SR)
            wav = resample_poly(wav, SR // g, int(sr) // g).astype(np.float32)
        except ImportError:  # linear interpolation is enough for speech features
            n = int(round(len(wav) * SR / sr))
            wav = np.interp(np.linspace(0, len(wav) - 1, n), np.arange(len(wav)), wav).astype(np.float32)
    return wav


class MediaEncoder:
    """Frozen media towers of a multimodal backbone, with a small LRU cache per file."""

    def __init__(self, mm_model: Any, model_name: str, cache_size: int = 2048):
        from transformers import AutoProcessor

        self.model = mm_model
        self.processor = AutoProcessor.from_pretrained(model_name)
        self.tok = self.processor.tokenizer
        cfg = mm_model.config
        self.audio_token_id = getattr(cfg, "audio_token_id", None)
        self.image_token_id = getattr(cfg, "image_token_id", None)
        self.cache_size = cache_size
        self._cache: OrderedDict[tuple[Any, ...], dict[str, Any]] = OrderedDict()
        for p in self.model.parameters():
            p.requires_grad_(False)

    TOWERS = ("audio_tower", "vision_tower", "embed_audio", "embed_vision")

    def to(self, device: torch.device | str) -> "MediaEncoder":
        """Move only the media towers (the language model is placed by UPPModel)."""
        for name in self.TOWERS:
            mod = getattr(self.model, name, None)
            if mod is not None and not getattr(mod, "is_loaded_in_4bit", False):
                mod.to(device)
        return self

    def _device_dtype(self, tower: str) -> tuple[torch.device, torch.dtype]:
        mod = getattr(self.model, tower)
        p = next(mod.parameters())
        dtype = p.dtype if p.dtype.is_floating_point else torch.float16
        return p.device, dtype

    def _layout(self, input_ids: torch.Tensor, media_id: int) -> list[int]:
        bos = self.tok.bos_token_id
        ids = [int(i) for i in input_ids[0].tolist()]
        if ids and bos is not None and ids[0] == bos:
            ids = ids[1:]
        return [MEDIA if i == media_id else i for i in ids]

    @torch.no_grad()
    def audio(self, path: str | Path) -> dict[str, Any]:
        wav = load_wav_16k(path)
        inp = self.processor(text=self.processor.audio_token, audio=[wav], return_tensors="pt")
        dev, dt = self._device_dtype("audio_tower")
        out = self.model.get_audio_features(inp["input_features"].to(dev, dt),
                                            inp["input_features_mask"].to(dev), return_dict=True)
        emb = out.pooler_output[out.attention_mask.to(out.pooler_output.device)]
        tokens = self._layout(inp["input_ids"], self.audio_token_id)
        return self._check(tokens, emb, path)

    @torch.no_grad()
    def image(self, path: str | Path) -> dict[str, Any]:
        from PIL import Image

        img = Image.open(str(path)).convert("RGB")
        inp = self.processor(text=self.processor.image_token, images=[img], return_tensors="pt")
        dev, dt = self._device_dtype("vision_tower")
        out = self.model.get_image_features(inp["pixel_values"].to(dev, dt), inp["image_position_ids"].to(dev),
                                            return_dict=True)
        emb = torch.cat(list(out.pooler_output), dim=0)
        tokens = self._layout(inp["input_ids"], self.image_token_id)
        return self._check(tokens, emb, path)

    @staticmethod
    def _check(tokens: list[int], emb: torch.Tensor, path: Any) -> dict[str, Any]:
        n = sum(1 for t in tokens if t == MEDIA)
        if n != emb.shape[0]:
            raise ValueError(f"{path}: {n} media slots but {emb.shape[0]} media embeddings")
        return {"tokens": tokens, "embeds": emb.detach()}

    def encode(self, media: dict[str, Any] | None) -> dict[str, Any] | None:
        """``{"audio": path}`` / ``{"image": path}`` / ``{"audio": path, "image": path}``
        -> tokens + embeds. Already-encoded dicts pass through.
        Supports simultaneous audio + image inputs in one turn.
        Returns tagged outputs: 'trusted_audio_tokens', 'untrusted_image_tokens'.
        """
        if not media:
            return None
        if "embeds" in media:
            return media

        has_audio = bool(media.get("audio"))
        has_image = bool(media.get("image"))
        if not has_audio and not has_image:
            return None

        cache_key = (
            str(media.get("audio")) if has_audio else None,
            str(media.get("image")) if has_image else None,
        )
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        audio_enc = self.audio(media["audio"]) if has_audio else None
        image_enc = self.image(media["image"]) if has_image else None

        if audio_enc and image_enc:
            combined_tokens = list(audio_enc["tokens"]) + list(image_enc["tokens"])
            combined_embeds = torch.cat([audio_enc["embeds"], image_enc["embeds"]], dim=0)
        elif audio_enc:
            combined_tokens = list(audio_enc["tokens"])
            combined_embeds = audio_enc["embeds"]
        else:
            combined_tokens = list(image_enc["tokens"])
            combined_embeds = image_enc["embeds"]

        res = {
            "tokens": combined_tokens,
            "embeds": combined_embeds.detach(),
            "trusted_audio_tokens": list(audio_enc["tokens"]) if audio_enc else [],
            "trusted_audio_embeds": audio_enc["embeds"].detach() if audio_enc else None,
            "untrusted_image_tokens": list(image_enc["tokens"]) if image_enc else [],
            "untrusted_image_embeds": image_enc["embeds"].detach() if image_enc else None,
            "has_audio": has_audio,
            "has_image": has_image,
        }

        self._cache[cache_key] = res
        if len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
        return res
