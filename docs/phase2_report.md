# Design Document

A functional Personal Financial Portal (GitHub repo link for coders or exported workflow file for no-coders).
A 1–2 page design document detailing agent roles, workflows, and pattern implementation rationale.


^ Reuse from Phase 1 report 


# Reflection Essay

## Tool Selection Trade-offs

Decision is made for quick prototyping and be more involved in our learning experience, therefore we use LangChain and SQLite ... 


## Ethical Considerations

1. Automation bias - and also the general disclaimer not financial advice 
2. Data Privacy - financial data are sensitive, and we are using various third party LLMs. We send data to Mistral OCR. We send data to OAI for the questions and also pass the query results etc 
3. Security - SQL injection related, input sanitation
4. Accuracy 

## Lesson Learnt
