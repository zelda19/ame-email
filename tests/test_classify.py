import pytest

from recruitment_mail.classify import classify


@pytest.mark.parametrize(
    "subject,text,category,attention,disposition",
    [
        ("Application received", "We received your application.", "Application confirmation", False, "matched"),
        ("Interview invitation", "Please reply with your availability.", "Interview invitation", True, "matched"),
        ("Next step", "Complete the coding\nexercise. No reply needed.", "Assessment invitation", True, "matched"),
        ("Hiring update", "Thank you for applying. We will not be moving forward with your application.", "Rejection", False, "matched"),
        ("Recruiting", "Please confirm your location.", "Response request", True, "matched"),
        ("Next steps", "Please schedule an interview and complete the hiring test.", None, True, "ambiguous"),
        ("Application", "No reply needed. Please reply if you got this.", None, False, "unrelated"),
    ],
)
def test_classifier_returns_expected_decision(subject, text, category, attention, disposition):
    decision = classify(subject, text)
    assert (decision.category, decision.attention, decision.disposition) == (
        category, attention, disposition,
    )
