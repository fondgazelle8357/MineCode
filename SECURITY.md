# Security policy

## Supported versions

Security maintenance targets the latest published MineCode release on a best-effort basis. Older versions and development snapshots have no guaranteed backports. Before the first public release, only the current release candidate is maintained; this policy does not imply that a public release already exists.

## Report a vulnerability privately

Use the official community repository's **Security → Report a vulnerability** button when available. This submits a private GitHub advisory to its maintainers. Include the affected version, minimal reproduction, likely impact and relevant permission flags. Use synthetic credentials and sanitized examples; do not attach personal data or live secrets.

Do not disclose exploitable details in public issues or pull requests. If the private-reporting button is absent, the channel is not active: wait for the repository owner to enable it rather than posting sensitive details publicly. Ordinary non-sensitive defects can use the normal issue tracker.

## Public release prerequisite

The future public repository owner under **uruk-king** must enable GitHub private vulnerability reporting when creating the public repository and verify the reporting entry point before publication. This cannot be verified before that repository exists. This source snapshot does **not** claim an active reporting channel.

Owner instructions: [enable private vulnerability reporting](https://docs.github.com/en/code-security/how-tos/report-and-fix-vulnerabilities/configure-vulnerability-reporting/configure-for-a-repository). Do not substitute a personal email or private development account.

## Maintenance and disclosure

Reports, fixes and coordinated disclosure are handled as maintainer availability permits. There is no guaranteed response deadline, ongoing support schedule or bounty. Prefer a focused fix and release for a confirmed issue. MineCode's execution opt-ins and best-effort output redaction are not an OS sandbox or an absolute secrecy guarantee.
