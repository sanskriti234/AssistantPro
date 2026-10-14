import pytest

from app.services.registration_response_parser import (
    DIPLOMA_FIELDS,
    REQUIRED_FIELDS,
    ResponseValidationError,
    parse_response,
)

FIELD_MAPPING = {
    "name": "q-name", "roll_number": "q-roll", "gender": "q-gender", "date_of_birth": "q-dob",
    "email": "q-email", "student_mobile": "q-mobile", "batch_confirmation": "q-confirm", "semester": "q-sem",
    "father_name": "q-father", "mother_name": "q-mother", "address": "q-address",
    "high_school_board": "q-hs-board", "high_school_institution": "q-hs-inst",
    "high_school_passing_year": "q-hs-year", "high_school_score": "q-hs-score",
    "intermediate_board": "q-int-board", "intermediate_institution": "q-int-inst",
    "intermediate_passing_year": "q-int-year", "intermediate_score": "q-int-score",
    "diploma_board": "q-dip-board",
    "profile_photo_file_id": "q-photo",
}


def _text_answer(question_id: str, value: str):
    return question_id, {"textAnswers": {"answers": [{"value": value}]}}


def _base_response(**overrides) -> dict:
    answers = dict([
        _text_answer("q-name", "Jane Doe"),
        _text_answer("q-roll", "230099"),
        _text_answer("q-gender", "Female"),
        _text_answer("q-dob", "2005-04-12"),
        _text_answer("q-email", "jane@example.com"),
        _text_answer("q-mobile", "9876543210"),
        _text_answer("q-confirm", "Yes"),
        _text_answer("q-sem", "5"),
        _text_answer("q-father", "John Doe"),
        _text_answer("q-mother", "Mary Doe"),
        _text_answer("q-address", "123 Main St"),
        _text_answer("q-hs-board", "CBSE"),
        _text_answer("q-hs-inst", "St. Xavier's"),
        _text_answer("q-hs-year", "2019"),
        _text_answer("q-hs-score", "92"),
        _text_answer("q-int-board", "CBSE"),
        _text_answer("q-int-inst", "St. Xavier's"),
        _text_answer("q-int-year", "2021"),
        _text_answer("q-int-score", "88.5"),
    ])
    answers.update(overrides)
    return {"responseId": "resp-1", "answers": answers}


def test_parse_response_happy_path():
    raw = parse_response(_base_response(), FIELD_MAPPING)
    assert raw["name"] == "Jane Doe"
    assert raw["roll_number"] == "230099"
    assert raw["email"] == "jane@example.com"
    assert raw["date_of_birth"] == "2005-04-12"
    assert raw["semester"] == 5
    assert raw["high_school_passing_year"] == 2019


def test_parse_response_missing_required_field_raises():
    response = _base_response()
    del response["answers"]["q-father"]
    with pytest.raises(ResponseValidationError, match="father_name"):
        parse_response(response, FIELD_MAPPING)


def test_parse_response_invalid_email_raises():
    response = _base_response(**{"q-email": {"textAnswers": {"answers": [{"value": "not-an-email"}]}}})
    with pytest.raises(ResponseValidationError, match="email"):
        parse_response(response, FIELD_MAPPING)


def test_parse_response_invalid_date_raises():
    response = _base_response(**{"q-dob": {"textAnswers": {"answers": [{"value": "not-a-date"}]}}})
    with pytest.raises(ResponseValidationError):
        parse_response(response, FIELD_MAPPING)


def test_parse_response_missing_batch_confirmation_raises():
    response = _base_response(**{"q-confirm": {"textAnswers": {"answers": [{"value": "No"}]}}})
    with pytest.raises(ResponseValidationError, match="Batch confirmation"):
        parse_response(response, FIELD_MAPPING)


def test_parse_response_empty_field_mapping_raises():
    with pytest.raises(ResponseValidationError, match="question mapping"):
        parse_response(_base_response(), {})


def test_parse_response_diploma_optional_when_blank():
    raw = parse_response(_base_response(), FIELD_MAPPING)
    for f in DIPLOMA_FIELDS:
        assert f not in raw


def test_parse_response_diploma_included_when_present():
    response = _base_response(**{"q-dip-board": {"textAnswers": {"answers": [{"value": "State Board"}]}}})
    raw = parse_response(response, FIELD_MAPPING)
    assert raw["diploma_board"] == "State Board"


def test_parse_response_profile_photo_extracted_from_file_upload_answer():
    response = _base_response(**{"q-photo": {"fileUploadAnswers": {"answers": [{"fileId": "drive-file-123"}]}}})
    raw = parse_response(response, FIELD_MAPPING)
    assert raw["profile_photo_file_id"] == "drive-file-123"


def test_required_fields_do_not_include_diploma():
    assert not set(DIPLOMA_FIELDS) & set(REQUIRED_FIELDS)


def test_parse_response_without_profile_photo_in_mapping():
    """Newly generated forms without profile-photo questions must parse all required fields successfully."""
    mapping_without_photo = {k: v for k, v in FIELD_MAPPING.items() if k != "profile_photo_file_id"}
    raw = parse_response(_base_response(), mapping_without_photo)
    assert raw["name"] == "Jane Doe"
    assert raw["roll_number"] == "230099"
    assert raw["email"] == "jane@example.com"
    assert "profile_photo_file_id" not in raw

