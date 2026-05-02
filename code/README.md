# Multi-Domain Support Triage Agent

## Overview

This project is a terminal-based support triage agent for HackerRank, Claude, and Visa tickets. It reads the provided CSV files, checks
the support information it has, decides whether each ticket can be answered safely, and writes the final predictions to output.csv.

The main goal of the agent is to be careful. If a ticket is clearly supported by the provided corpus, the agent gives a direct answer. If
the ticket is sensitive, unclear, risky, or not supported by the corpus, the agent escalates it instead of guessing.

The agent does not use external websites, hidden knowledge, API calls, or live LLM responses. It only uses the provided CSV files.

## How to Run

From the project root, run:
python code/triage_agent.py --data-dir support_tickets --output support_tickets/output.csv

If the zip extracts into a nested folder, this command also works:
python code/triage_agent.py --data-dir support_tickets/support_tickets --output support_tickets/support_tickets/output.csv

The final output file should be:
support_tickets/output.csv

## Files

The agent reads these files:
support_tickets/sample_support_tickets.csv
support_tickets/support_tickets.csv

The agent writes this file:
support_tickets/output.csv

The output columns are:
issue, subject, company, response, product_area, status, request_type, justification

status is always either:
replied
escalated

request_type is always one of:
product_issue
feature_request
bug
invalid

## Agent Design

The implementation is split into small pieces:

1. CSV loading and field normalization
2. support corpus construction from the provided examples
3. keyword retrieval over the provided corpus
4. request type and product area classification
5. explicit escalation rules for sensitive or unsupported cases
6. structured CSV writing

For each ticket, the agent combines the issue, subject, and company fields into one text string. It uses that text to understand the
domain, find similar examples, and decide whether the answer can be safely grounded in the provided corpus.

## Escalation Policy

The agent escalates tickets involving payments, refunds, subscriptions, disputes, account access, admin permissions, security issues,
identity theft, assessment outcomes, hiring decisions, broad outages, unsafe requests, prompt-injection style requests, or anything that
is not clearly supported by the corpus.

This conservative approach is intentional. I would rather escalate a borderline ticket than give an answer that sounds confident but is
not actually supported

## Why This Approach
I chose a deterministic script because the challenge focuses on grounded answers, safe escalation, and reproducibility. A live LLM-based 
solution would be more flexible, but it could also be harder to reproduce and easier to hallucinate with such a small corpus.

The tradeoff is that this agent may miss tickets that use very different wording from the sample cases. With more time, I would improve 
it with embedding-based retrieval, stronger confidence scoring, and more test cases.

## Reproducibility
The script only uses Python standard library modules. There are no external dependencies, no random sampling, and no network calls.
Given the same input files, it should produce the same output every time.

## Code Map
The main functions are:

1. load_csv_from_folder: finds and reads the CSV files.

2. build_support_corpus: builds the reference corpus from the provided examples.

3. retrieve: finds the closest matching support examples.

4. request_type: classifies the ticket as a product issue, feature request, bug, or invalid request.

5. product_area: assigns the most relevant support area.

6. risky_reason: detects tickets that should be escalated.

7. triage: makes the final decision for one ticket.

8. run: writes the final output CSV.

## Known Limitations

The main limitation is that retrieval is based on keyword overlap. If a ticket has the same meaning as an example but uses very different 
words, the agent may not retrieve the best match.

The escalation and product-area rules are also hand-written. They are easy to inspect and reproduce, but they would need to be expanded 
as new ticket patterns appear.

## AI Assistance Disclosure

AI assistance was used to read the challenge requirements, review the first version of the script, identify issues such as output casing
and path problems, and improve the wording and structure.

The final design direction was chosen by me: a terminal-based, dependency-free, corpus-grounded agent that escalates when it cannot 
safely answer.