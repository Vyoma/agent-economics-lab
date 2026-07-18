# Security Policy

## Project status

Agent Economics Lab is an alpha research, teaching, and conformance project. It is
not a production authorization layer, accounting system, sandbox, or security
boundary.

Until stable releases exist, only the latest `main` branch receives security fixes.

## Report a vulnerability

Use the repository's **Security → Advisories → Report a vulnerability** flow so the
report and any proof of concept remain private. Do not include vulnerability details
in a public issue.

If private vulnerability reporting is not yet enabled, open a minimal public issue
requesting a private security contact without including technical details. A
maintainer will establish a private channel.

Please include:

- the affected version or commit;
- the smallest reproducible case;
- expected and observed behavior;
- realistic impact and prerequisites; and
- any suggested mitigation.

## In scope

Security reports are especially useful when they show unsafe parsing, path or file
handling, untrusted-input behavior, integrity failures in the evidence digest, or a
way for missing required coverage to produce a complete decision.

Policy disagreements, new assurance checks, and counterexamples to the research
claim belong in the public issue templates unless disclosure would create a security
risk.
