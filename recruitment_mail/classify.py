import re
from dataclasses import dataclass


ACKNOWLEDGMENT = "Application confirmation"
INTERVIEW = "Interview invitation"
ASSESSMENT = "Assessment invitation"
REJECTION = "Rejection"
RESPONSE = "Response request"
LABELS = {
    category: f"Recruitment - {category}"
    for category in (ACKNOWLEDGMENT, INTERVIEW, ASSESSMENT, REJECTION, RESPONSE)
}
SPECIFIC = {
    INTERVIEW: r"\b(?:interview invitation|(?:invite|inviting) you (?:to|for) (?:an? |the )?interview|(?:attend|book|schedule) (?:an? |your )?interview)\b",
    ASSESSMENT: r"\b(?:assessment invitation|(?:complete|take|submit) (?:the |a |your |our )?(?:hiring test|coding exercise|(?:recruitment )?assessment))\b",
    REJECTION: r"\b(?:will not be moving forward with your application|decided not to proceed with your application|were not selected)\b",
}
REPLY = r"\b(?:please (?:reply|respond|confirm|provide|send)|let us know|reply with)\b"
NO_REPLY = r"\b(?:no (?:reply|response) (?:is )?(?:needed|required)|do not reply)\b"
ACTION = r"\b(?:please (?:book|schedule|complete|take|submit)|complete (?:the |a |your |our )?(?:hiring test|coding exercise|(?:recruitment )?assessment))\b"


@dataclass(frozen=True)
class Decision:
    category: str | None
    attention: bool
    disposition: str


def classify(subject: str, current_text: str) -> Decision:
    text = " ".join(f"{subject} {current_text}".casefold().split())
    specific = [
        category for category, pattern in SPECIFIC.items() if re.search(pattern, text)
    ]
    reply = bool(re.search(REPLY, text) and not re.search(NO_REPLY, text))
    attention = reply or bool(re.search(ACTION, text))
    if len(specific) > 1:
        return Decision(None, attention, "ambiguous")
    if specific:
        return Decision(specific[0], attention, "matched")
    if re.search(r"\b(?:we received your application|thank you for applying)\b", text):
        return Decision(ACKNOWLEDGMENT, attention, "matched")
    if reply and re.search(r"\b(?:recruitment|recruiting|hiring|job application|your application|candidate)\b", text):
        return Decision(RESPONSE, True, "matched")
    return Decision(None, False, "unrelated")
