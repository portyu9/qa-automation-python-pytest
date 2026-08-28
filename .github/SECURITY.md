# Security Policy

## Supported versions

Security fixes are applied to the current default branch. Historical commits, tags, forks, and unsupported dependency versions may not receive fixes.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, tokens, exploit details, or sensitive test data in a public issue.

Use GitHub private vulnerability reporting if the repository presents that option. If private reporting is unavailable, open a minimal public issue requesting a private contact channel and do not include exploit or secret details.

Include:

- affected repository and commit SHA;
- impact and affected boundary;
- minimal reproduction steps;
- relevant dependency or tool versions;
- suggested mitigation, if known.

Reports will be validated against the current default branch. No bounty or response-time commitment is implied.

## Authorized testing

Do not use repository browser, API, DAST, or load-testing capabilities against systems you do not own or have explicit authorization to test. Keep credentials and production data out of committed fixtures and diagnostic artifacts.

## Disclosure

Coordinate disclosure after a fix or mitigation is available. Avoid publishing working exploit details before maintainers have had a reasonable opportunity to address the issue.
