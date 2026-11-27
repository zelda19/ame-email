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


@pytest.mark.parametrize("body", [
    "Can you confirm your availability for the interview?",
    "Book a time for your interview using this link. No reply needed.",
    "Use the link below to schedule your interview.",
])
def test_interview_availability_and_booking_require_attention(body):
    decision = classify("Interview invitation", body)
    assert (decision.category, decision.attention) == ("Interview invitation", True)


def test_interview_booking_confirmation_does_not_require_attention():
    decision = classify("Interview invitation", "Your interview is booked. No reply needed.")
    assert (decision.category, decision.attention) == ("Interview invitation", False)


@pytest.mark.parametrize("body, attention", [
    ("Could you confirm if you are available on Tuesday?", True),
    ("Could you confirm whether you're available on Tuesday?", True),
    ("Could you confirm whether you’re available? No reply needed.", False),
    ("We can confirm you’re available on Tuesday.", False),
])
def test_interview_availability_questions_and_statements(body, attention):
    decision = classify("Interview invitation", body)
    assert (decision.category, decision.attention) == ("Interview invitation", attention)
