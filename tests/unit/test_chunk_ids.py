from app.ingestion.chunking import Chunker, make_chunk_id
from tests.unit.test_chunking import _section


def test_make_chunk_id_is_deterministic() -> None:
    kwargs = {
        "corpus_id": "finra-synthetic",
        "corpus_version": "v1",
        "section_id": "sec_test",
        "chunk_index": 0,
        "normalized_text": "FINRA Rule 1000(a)\n\nMembers must maintain written policies.",
    }

    assert make_chunk_id(**kwargs) == make_chunk_id(**kwargs)
    assert make_chunk_id(**kwargs).startswith("chk_")


def test_make_chunk_id_changes_for_version_index_or_text() -> None:
    base = make_chunk_id(
        corpus_id="finra-synthetic",
        corpus_version="v1",
        section_id="sec_test",
        chunk_index=0,
        normalized_text="same text",
    )

    assert base != make_chunk_id(
        corpus_id="finra-synthetic",
        corpus_version="v2",
        section_id="sec_test",
        chunk_index=0,
        normalized_text="same text",
    )
    assert base != make_chunk_id(
        corpus_id="finra-synthetic",
        corpus_version="v1",
        section_id="sec_test",
        chunk_index=1,
        normalized_text="same text",
    )
    assert base != make_chunk_id(
        corpus_id="finra-synthetic",
        corpus_version="v1",
        section_id="sec_test",
        chunk_index=0,
        normalized_text="changed text",
    )


def test_chunker_produces_stable_ids_for_same_section() -> None:
    section = _section("Members must maintain written policies and escalation channels.")
    first = Chunker().chunk_section(section)
    second = Chunker().chunk_section(section)

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
