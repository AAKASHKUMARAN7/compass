# Demo Questions

Every question below was run against the seeded corpus and verified to return
`answered` with a citation to the correct section. Scores are from
`all-MiniLM-L6-v2` in extractive mode; a configured LLM key changes the prose,
not the retrieval.

Regenerate the check any time with `bash eval/run.sh`.

---

## Leave & Time Off

| Question | Cites |
| --- | --- |
| How many annual leave days do full-time employees get per year? | 2. Annual Leave |
| How many unused leave days can I carry into next year? | 2.1 Carryover |
| By when must carried-over leave days be taken? | 2.1 Carryover |
| How much notice must I give for an absence of five days or more? | 2.2 Requesting Annual Leave |
| How many paid sick days do I get per year? | 3. Sick Leave |
| When do I need a medical certificate for sick leave? | 3. Sick Leave |
| How much parental leave does a primary caregiver get? | 4. Parental Leave |
| How much parental leave does a secondary caregiver get? | 4. Parental Leave |
| How many days of bereavement leave for an immediate family member? | 6. Bereavement Leave |
| What happens if I have to work on a public holiday? | 7. Public Holidays |

## Compensation

| Question | Cites |
| --- | --- |
| When does the annual compensation review take effect? | 3. Annual Review Cycle |
| What is the target bonus percentage at level L5? | 5. Bonus |
| When is the annual bonus paid? | 5. Bonus |
| What is the minimum increase when I am promoted? | 4. Promotions |
| How often are promotions approved? | 4. Promotions |
| What is the referral bonus for a standard role? | 7. Referral Bonus |
| When are salaries paid each month? | 8. Payroll |
| What market percentile does the company target for base salary? | 1. Principles |
| What is the overtime rate for working on a public holiday? | 6. Overtime and On-Call |
| How much is the on-call allowance per week? | 6. Overtime and On-Call |

## Benefits

| Question | Cites |
| --- | --- |
| How much does the company match on retirement contributions? | 5. Retirement Savings |
| Is dental cover included in the medical plan? | 3.1 Dental and Vision |
| What is the monthly fitness allowance? | 6.3 Fitness Allowance |
| What is the annual learning budget per employee? | 7. Learning and Development |
| How many mental health days can I take each year? | 6.2 Mental Health Days |
| How much life assurance cover do employees get? | 4. Life and Income Protection |
| Up to what age can children be enrolled as dependents? | 3.2 Dependents |
| How long do I have to change my elections after a life event? | 2. Qualifying Life Events |
| What is the monthly childcare contribution? | 8. Family Support |
| When does medical cover end if I leave the company? | 10. Leavers |

## Expenses & Travel

| Question | Cites |
| --- | --- |
| What is the nightly accommodation limit for London? | 3.2 Accommodation |
| What is the daily dinner allowance? | 4. Meals and Subsistence |
| Within how many days must I submit an expense claim? | 2. Submission and Approval |
| What approval do I need for an expense of 1500 USD? | 2. Submission and Approval |
| When is business class air travel permitted? | 3.1 Air Travel |
| What is the home office allowance for a new joiner? | 6. Home Office and Equipment |
| How much internet cost is reimbursed for remote employees? | 6. Home Office and Equipment |
| What is the per-head limit for client entertainment? | 5. Client Entertainment |
| Are traffic and parking fines reimbursable? | 7. Non-Reimbursable Expenses |
| When is premium economy allowed on a flight? | 3.1 Air Travel |

## Security & IT

| Question | Cites |
| --- | --- |
| What is the minimum password length? | 2.1 Passwords |
| Is SMS accepted as a second factor? | 2.2 Multi-Factor Authentication |
| How quickly must I report a lost or stolen laptop? | 3.1 Lost or Stolen Devices |
| Can I paste confidential customer data into a public AI tool? | 4.2 Generative AI Tools |
| What are the four data classification tiers? | 4. Data Handling |
| How quickly must a security incident be reported? | 5. Incident Reporting |
| Can I use a personal device for company email? | 3. Device Security |
| How soon must operating system updates be applied? | 3. Device Security |
| Can production customer data be copied into a test environment? | 4.1 Customer Data |
| How quickly is access revoked when someone leaves? | 2.3 Access Reviews |

## Conduct & Compliance

| Question | Cites |
| --- | --- |
| What is the limit on accepting a gift from a supplier? | 5. Gifts and Hospitality |
| Do I need to declare a relationship with a colleague? | 4. Conflicts of Interest |
| Within how many days must a conflict of interest be declared? | 4. Conflicts of Interest |
| How do I report harassment? | 3. Harassment and Discrimination |
| How quickly is a harassment report acknowledged? | 3.1 Reporting |
| What is the policy on insider trading? | 7. Insider Trading |
| Can I accept a gift card from a vendor? | 5. Gifts and Hospitality |
| What should I do if a competitor discusses pricing with me? | 8. Fair Competition |
| What is the policy on retaliation against someone who reports a concern? | 3.2 Non-Retaliation |
| When is the annual code of conduct attestation due? | 12. Annual Attestation |

## Workplace

| Question | Cites |
| --- | --- |
| How many days a week do I need to be in the office? | 1. Working Model |
| What are the core hours I must be reachable? | 2.1 Core Hours |
| How far in advance can I book a desk? | 4.1 Desks and Booking |
| Can I work from another country for a few weeks? | 5.3 Working from Another Country |
| What internet speed is required for remote work? | 5.1 Workspace Requirements |
| When must company equipment be returned after leaving? | 5.2 Equipment |
| How often are fire drills held? | 6.1 First Aid and Fire |
| Can I bring my pet to the office? | 9. Pets and Children |
| What happens if the office closes due to severe weather? | 7. Office Closures and Severe Weather |
| How do I request a compressed four-day week? | 2.3 Compressed Weeks |

---

## Questions that should be refused

These are the ones worth demonstrating. Each is plausibly something an employee
would ask, and none is covered by the published set, so the assistant declines
and logs a coverage gap instead of inventing an answer.

| Question | Score |
| --- | --- |
| Do we offer a sabbatical after five years of service? | 0.44 |
| What is our company stock ticker symbol? | 0.22 |
| How do I request a company car? | 0.41 |
| How many stock options do I get? | 0.21 |
| What is the dividend payout schedule? | 0.35 |
| Can I expense a helicopter charter? | 0.38 |
| Who won the football match last night? | 0.11 |

## Questions that expose the limits

Ask these only if you want to talk about the boundary honestly. They are
tracked in `eval/known_gaps.txt`.

| Question | What happens | Why |
| --- | --- | --- |
| `leaves balance` | Refused at 0.30 | Two-word fragment; "balance" appears nowhere in the corpus. Fails closed, which is the safe direction. |
| `my remaining leaves` | Refused at 0.46 | Same. Just under the 0.48 floor. |
| `what is the company policy on space travel` | Answered at 0.53 | Contains a genuinely covered topic word. Retrieval scoring cannot separate business travel from space travel — only reading the excerpt can, which is the model layer's job. |
