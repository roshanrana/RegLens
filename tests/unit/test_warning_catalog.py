from app.generation.warnings import warning_details


def test_warning_details_include_known_severity_and_message() -> None:
    details = warning_details(["source_instruction_filtered"])

    assert details == [
        {
            "code": "source_instruction_filtered",
            "severity": "high",
            "message": "Retrieved source text contained instructions that were filtered.",
        }
    ]


def test_warning_details_handle_unknown_codes() -> None:
    details = warning_details(["new_warning_code"])

    assert details == [
        {
            "code": "new_warning_code",
            "severity": "medium",
            "message": "Uncataloged warning: new_warning_code.",
        }
    ]
