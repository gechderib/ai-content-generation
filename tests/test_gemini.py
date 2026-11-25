import base64

from pipeline.gemini import extract_audio, extract_text, model_output_blocks

# Shape confirmed live against the real API on 2026-11-25: a "thought" step
# carries no usable output and must be skipped; the real output lives in the
# "model_output" step's content blocks.
TEXT_RESPONSE = {
    "status": "completed",
    "steps": [
        {"type": "thought", "signature": "opaque-reasoning-blob"},
        {"type": "model_output", "content": [{"type": "text", "text": "OK"}]},
    ],
    "object": "interaction",
    "model": "gemini-3.6-flash",
}

AUDIO_RESPONSE = {
    "status": "completed",
    "steps": [
        {
            "type": "model_output",
            "content": [{"type": "audio", "data": base64.b64encode(b"RIFF....fake-wav-bytes").decode(), "mime_type": "audio/wav"}],
        }
    ],
    "object": "interaction",
    "model": "gemini-3.8-flash-tts",
}


def test_model_output_blocks_skips_thought_steps():
    blocks = model_output_blocks(TEXT_RESPONSE)
    assert blocks == [{"type": "text", "text": "OK"}]


def test_extract_text_joins_text_blocks():
    assert extract_text(TEXT_RESPONSE) == "OK"


def test_extract_text_is_empty_for_audio_only_response():
    assert extract_text(AUDIO_RESPONSE) == ""


def test_extract_audio_decodes_base64_and_returns_mime_type():
    audio_bytes, mime_type = extract_audio(AUDIO_RESPONSE)
    assert audio_bytes.startswith(b"RIFF")
    assert mime_type == "audio/wav"


def test_extract_audio_empty_for_text_only_response():
    audio_bytes, mime_type = extract_audio(TEXT_RESPONSE)
    assert audio_bytes == b""
    assert mime_type == ""
