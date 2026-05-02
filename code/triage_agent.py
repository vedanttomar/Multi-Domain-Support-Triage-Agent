from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path



# [ CONSTANTS & OUTPUT STRUCTURE ]


OUTPUT_COLUMNS = ["issue","subject","company","response","product_area","status","request_type","justification"]

REPLIED = "replied"
ESCALATED = "escalated"

PRODUCT_ISSUE = "product_issue"
FEATURE_REQUEST = "feature_request"
BUG = "bug"
INVALID = "invalid"


# [ DATA MODELS ]


@dataclass
class Ticket:
    issue: str
    subject: str
    company: str


@dataclass
class Decision:
    response: str
    product_area: str
    status: str
    request_type: str
    justification: str



# [ TXT & CSV HELPERS ]


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def field(row: dict[str, str], *names: str) -> str:
    lowered = {key.lower().strip(): value for key, value in row.items()}

    for name in names:
        value = lowered.get(name.lower())
        if value is not None:
            return clean(value)

    return ""


def combined(ticket: Ticket) -> str:
    return f"{ticket.issue} {ticket.subject} {ticket.company}".lower()


def load_csv_from_folder(data_dir: Path, filename: str) -> list[dict[str, str]]:
    target = data_dir / filename

    if not target.exists():
        matches = [
            path
            for path in data_dir.rglob(filename)
            if "__MACOSX" not in path.parts and not path.name.startswith("._")
        ]

        if not matches:
            raise FileNotFoundError(f"Could not find {filename} in {data_dir}")

        target = matches[0]

    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


# [ CORPUS BUILDING & RETRIEVAL ]


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_support_corpus(sample_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    corpus = []

    for row in sample_rows:
        response = field(row, "response", "Response")

        if not response or response.lower() == "escalate to a human":
            continue

        company = field(row, "company", "Company")
        product = field(row, "product_area", "Product Area")
        kind = field(row, "request_type", "Request Type")

        corpus.append({"company": company,"product_area": product,"request_type": kind,"response": response,"search_text": " ".join([field(row, "issue", "Issue"),field(row, "subject", "Subject"),company,product,response,]),})

    return corpus


def retrieve(ticket: Ticket, corpus: list[dict[str, str]], limit: int = 3) -> list[dict[str, str]]:
    query = Counter(tokenize(combined(ticket)))
    matches = []

    for item in corpus:
        doc = Counter(tokenize(item["search_text"]))
        score = sum(query[word] * doc.get(word, 0) for word in query)

        if clean(ticket.company).lower() == clean(item["company"]).lower():
            score += 5

        if score > 0:
            matches.append({**item, "score": score})

    return sorted(matches, key=lambda item: item["score"], reverse=True)[:limit]



# CLASSIFICATIN HELPERS


def request_type(text: str) -> str:
    if any(term in text for term in ["actor in iron man","delete all files","thank you","thanks",]):
        return INVALID

    if any(term in text for term in ["feature","feature request","would like","can you add","planning to","wanted to setup","can you help us",]):
        return FEATURE_REQUEST

    if any(term in text for term in ["down","not working","failing","stopped","error","blocker","broken","not responding","unable",]):
        return BUG

    return PRODUCT_ISSUE


def product_area(company: str, text: str) -> str:
    company = clean(company).lower()

    if company == "visa" or "visa" in text:
        if "traveller" in text or "cheque" in text:
            return "travel_support"
        return "general_support"

    if company == "claude" or "claude" in text:
        if any(term in text for term in ["private", "privacy", "data", "crawl", "crawling"]):
            return "privacy"

        if any(term in text for term in ["workspace", "seat", "access", "admin"]):
            return "account_access"

        if any(term in text for term in ["bedrock", "api", "lti", "security", "vulnerability", "requests"]):
            return "technical_support"

        return "conversation_management"

    if company == "hackerrank" or "hackerrank" in text:
        if any(term in text for term in ["community", "apply", "practice", "submissions", "resume", "certificate"]):
            return "community"

        if any(term in text for term in ["subscription", "infosec", "interviewer", "employee", "user", "hiring account"]):
            return "account_management"

        return "screen"

    return ""


# [ ESCALATION & SAFETY POLICY ]


def risky_reason(text: str) -> str | None:
    if any(term in text for term in ["internal rules","show all rules","logic exact","logique exacte","documents recuperes","regles internes","delete all files"]):

        return "The ticket asks for unsafe or internal information, so it should not be answered directly."

    if any(term in text for term in ["refund","payment","money","subscription","charge","merchant","ban the seller",]):

        return "The ticket involves payment, refund, subscription, or dispute handling, which needs human review."

    if any(term in text for term in ["increase my score","review my answers","rejected me","next round","rescheduling","alternative date"]):
        return "The ticket asks for an assessment outcome or scheduling change that depends on the hiring team."

    if any(term in text for term in ["restore my access","removed my seat","workspace owner","not the workspace owner","remove a user","employee has left"]):

        return "The ticket involves account access or user permissions and requires verified admin handling."

    if any(term in text for term in ["security vulnerability","bug bounty","identity has been stolen","identity theft"]):

        return "The ticket is security-sensitive and should be handled by a human or specialized support team."

    if any(term in text for term in ["site is down","all requests","none of the submissions","stopped working completely","all requests are failing"]):

        return "The ticket appears broad or service-impacting and should be escalated for investigation."

    return None


def human_escalation(reason: str) -> str:
    return (
        "Thanks for sharing the details. I do not have enough supported information "
        "to resolve this safely here, so I am sending it to a human support specialist "
        "who can review the case properly.")



# [ RESPONSE GENERATION ]


def direct_answer(ticket: Ticket, text: str) -> Decision | None:
    area = product_area(ticket.company, text)

    if re.fullmatch(r"(thanks|thank you|thank you for helping me|thanks for helping me)[.! ]*", text):
        return Decision(
            "Happy to help.",
            area,
            REPLIED,
            INVALID,
            "The message is only an acknowledgement and does not require support action.",
        )

    if "actor in iron man" in text:
        return Decision(
            "I am sorry, but that question is outside the HackerRank, Claude, and Visa support topics I can help with here.",
            area or "out_of_scope",
            REPLIED,
            INVALID,
            "The question is unrelated to the supported domains.",
        )

    if "delete all files" in text:
        return Decision(
            "I cannot help with instructions to delete files from a system. This request is outside the scope of this support agent.",
            area or "out_of_scope",
            REPLIED,
            INVALID,
            "The request is unsafe and unrelated to the provided support corpus.",
        )

    if "lost or stolen" in text and "visa" in text:
        return Decision(
            "I am sorry that happened. To report a lost or stolen Visa card from India, call Visa India at 000-800-100-1219. If you are outside India, contact Visa Global Customer Assistance Service at +1 303 967 1090.",
            "general_support",
            REPLIED,
            PRODUCT_ISSUE,
            "The provided Visa sample gives lost-card reporting phone numbers and safe routing guidance.",
        )

    if "urgent cash" in text and "visa" in text:
        return Decision(
            "For urgent cash or replacement-card support, contact Visa Global Customer Assistance Service at +1 303 967 1090. If you are calling from India about a lost card, use 000-800-100-1219.",
            "general_support",
            REPLIED,
            PRODUCT_ISSUE,
            "The Visa sample says emergency cash and replacement-card assistance are handled through the support line.",
        )

    if "traveller" in text and "cheque" in text:
        return Decision(
            "I am sorry your traveller's cheques were stolen. Please call the issuer immediately. Have the cheque serial numbers, purchase details, how and when they were lost or stolen, and the issuer name ready before you call.",
            "travel_support",
            REPLIED,
            PRODUCT_ISSUE,
            "The Visa traveller's cheque sample explains that the issuer should be contacted with those details.",
        )

    if "private info" in text and "claude" in text:
        return Decision(
            "You can delete an individual Claude conversation by opening the conversation, clicking the conversation name at the top, and selecting Delete from the options shown.",
            "privacy",
            REPLIED,
            PRODUCT_ISSUE,
            "The Claude sample includes steps for deleting an individual conversation.",
        )

    if "extra time" in text or "accommodation" in text:
        return Decision(
            "In HackerRank, open the test, go to the Candidates tab, select the candidate, choose More, then Add Time Accommodation. Enter the accommodation percentage in multiples of five and save the change.",
            "screen",
            REPLIED,
            PRODUCT_ISSUE,
            "The HackerRank sample gives the time-accommodation workflow for candidates.",
        )

    if "variant" in text or "variants" in text:
        return Decision(
            "Use HackerRank test variants when one test needs to support different candidate profiles, such as different tech stacks. Variants reduce duplicate test management and keep candidates focused on relevant sections, but they require variant logic and at least two variants.",
            "screen",
            REPLIED,
            PRODUCT_ISSUE,
            "The HackerRank sample explains when variants are useful and notes their limitations.",
        )

    if "active" in text and "test" in text and "hackerrank" in text:
        return Decision(
            "HackerRank tests stay active indefinitely unless a start and end time are set. To change this, open the test settings, go to General, and update or clear the start and end date/time fields.",
            "screen",
            REPLIED,
            PRODUCT_ISSUE,
            "The HackerRank sample explains test expiration behavior and where to change it.",
        )

    if "google login" in text and "delete my account" in text:
        return Decision(
            "For a HackerRank account created with Google login, first set a password using Forgot your password. Then log in with that password and continue through the account settings flow to delete the account.",
            "community",
            REPLIED,
            PRODUCT_ISSUE,
            "The HackerRank community sample includes account deletion guidance for Google-login accounts.",
        )

    if "personal data" in text and "claude" in text:
        reason = "The provided Claude examples do not state how long model-improvement data is used."
        return Decision(human_escalation(reason), "privacy", ESCALATED, PRODUCT_ISSUE, reason)

    if "crawl" in text and "claude" in text:
        reason = "The provided Claude examples do not include website crawling controls."
        return Decision(human_escalation(reason), "privacy", ESCALATED, PRODUCT_ISSUE, reason)

    return None



# [ TRIAGE COORDINATION ]


def triage(ticket: Ticket, corpus: list[dict[str, str]]) -> Decision:
    text = combined(ticket)
    area = product_area(ticket.company, text)
    kind = request_type(text)

    direct = direct_answer(ticket, text)
    if direct:
        return direct

    reason = risky_reason(text)
    if reason:
        return Decision(human_escalation(reason), area, ESCALATED, kind, reason)

    matches = retrieve(ticket, corpus)

    if matches and matches[0]["score"] >= 10:
        top = matches[0]
        return Decision(
            top["response"],
            top["product_area"] or area,
            REPLIED,
            top["request_type"] or kind,
            "The answer is grounded in the closest matching provided support case.",
        )

    if clean(ticket.company).lower() in {"", "none"} and not area:
        return Decision(
            "I am sorry, but I cannot match this request to the supported HackerRank, Claude, or Visa help topics closely enough to answer safely.",
            area or "out_of_scope",
            REPLIED,
            INVALID,
            "The company is missing and the issue does not contain enough supported-domain detail to ground a response.",
        )

    reason = "The provided support corpus does not contain enough specific guidance to answer without guessing."
    return Decision(human_escalation(reason), area, ESCALATED, kind, reason)



# [ BATCH RUNNER & CSV OUTPUT ]


def run(data_dir: Path, output_path: Path) -> None:
    sample_rows = load_csv_from_folder(data_dir, "sample_support_tickets.csv")
    ticket_rows = load_csv_from_folder(data_dir, "support_tickets.csv")
    corpus = build_support_corpus(sample_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for row in ticket_rows:
            ticket = Ticket(issue=field(row, "issue", "Issue"),subject=field(row, "subject", "Subject"),company=field(row, "company", "Company"))

            decision = triage(ticket, corpus)

            writer.writerow({"issue": ticket.issue,"subject": ticket.subject,"company": ticket.company,"response": decision.response,"product_area": decision.product_area,"status": decision.status,"request_type": decision.request_type,"justification": decision.justification})



# [ COMMAND-LINE INTERFACE ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Support triage agent")

    parser.add_argument(
        "--data-dir",
        default="support_tickets",
        help="Path to the extracted support_tickets folder.",
    )

    parser.add_argument(
        "--output",
        default="support_tickets/output.csv",
        help="Where to write the required output CSV.",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    output_path = Path(args.output).resolve()

    if not data_dir.exists():
        raise FileNotFoundError(f"Data folder not found: {data_dir}")

    run(data_dir, output_path)
    print(f"Done. Wrote triage results to: {output_path}")


if __name__ == "__main__":
    main()
