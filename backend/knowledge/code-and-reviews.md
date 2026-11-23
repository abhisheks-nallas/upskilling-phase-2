# Code, Pull Requests and Releases

## Repository access
Developers get read access to all team repositories on day 2 and write access after completing the security awareness quiz. Access is requested through the helpdesk portal and approved by your manager. Direct pushes to the main branch are blocked for everyone.

## Branches and commits
Create a branch from main named type/short-description, for example feature/login-page or fix/timeout-bug. Keep commits small and write the message in the imperative, such as "Add retry to the sync job". Do not commit secrets, keys or customer data. If you do, tell the security team at once, because removing it from git history is not enough.

## Pull requests
Every pull request needs at least 2 approvals, and one of them must be from a code owner. Keep pull requests under 400 changed lines where possible. The author makes sure the CI pipeline is green before asking for review. Reviewers aim to respond within 1 working day.

## Releases
Production releases happen on Tuesdays and Thursdays between 10:00 and 15:00 IST. There are no production releases on Fridays or before public holidays. A rollback plan is written in the pull request description for every production change.

## Testing
New code needs unit tests, and a pull request that lowers the coverage of the changed files below 80 percent is sent back by the CI check.
