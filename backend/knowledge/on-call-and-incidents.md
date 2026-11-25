# On-call and Incident Response

## Who is on call
Engineers join the on-call rota after 3 months in the team. Before taking your first rota you shadow one full on-call week with an experienced colleague, and you do not carry the pager alone during that week. A rota week starts on Monday at 10:00 and ends the following Monday at 10:00. The rota is published a month ahead in the team calendar, and swaps are fine as long as both people confirm in writing in the team channel.

## On-call allowance and time off
Each on-call week earns an allowance of INR 2,500, paid with the next payroll. If you are paged between 22:00 and 06:00 and the incident work adds up to more than one hour in that night, you get one compensatory day off. The compensatory day must be used within 30 days and it cannot be added to annual leave to make a longer break without manager approval. Time spent on a page during working hours does not earn a compensatory day.

## Severity levels
Severity 1 means a customer-wide outage or data loss. Acknowledge the page within 10 minutes and post a status update every 30 minutes until the incident is resolved. Severity 2 means a major feature is degraded for many customers. Acknowledge within 30 minutes and post updates every 2 hours. Severity 3 is a minor problem with a workaround, and it is handled on the next working day. If you are unsure, treat the incident as the higher severity and lower it later.

## Incident commander and escalation
The first responder is the incident commander until someone else formally takes over in the incident channel. The commander coordinates, keeps the timeline and decides when to escalate, and does not have to be the person who fixes the problem. For a Severity 1 that is still unresolved after 30 minutes, page the engineering manager. If the manager does not respond within 15 minutes, page the head of engineering. Customer communication goes through the delivery lead and never directly from the engineers.

## Postmortems
Every Severity 1 and Severity 2 incident gets a blameless postmortem within 5 working days. Use the template in the wiki: summary, timeline, root cause, what went well, what went badly and follow-up actions with owners and dates. The postmortem is reviewed in the weekly reliability meeting on Wednesday at 15:00. Follow-up actions are tracked in the team backlog and reviewed until they are closed.
