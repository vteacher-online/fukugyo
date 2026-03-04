# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**fukugyo** is a Japanese freelance/side-job management tool that automates time tracking, invoicing, payment monitoring, and debt collection processes. It integrates with Slack for time tracking and freee for accounting, providing a complete workflow from contract analysis to legal escalation.

## Command Structure

This project is built around Python scripts that handle different aspects of freelance business management:

### Core Scripts
- `scripts/setup.py` - Interactive setup for configuration file creation
- `scripts/timecard.py` - Time tracking via Slack messages or Chrome history
- `scripts/contract.py` - AI-powered contract analysis and storage
- `scripts/invoice.py` - Invoice generation with tax compliance
- `scripts/payment.py` - Payment monitoring and reminder generation
- `scripts/escalate.py` - Legal escalation documents (demand letters, court filings)

### Skill Commands (defined in SKILL.md)
All commands are prefixed with `/fukugyo-` and execute the corresponding Python scripts:

| Command | Script | Purpose |
|---------|--------|---------|
| `/fukugyo-setup` | `python3 scripts/setup.py` | Initial configuration |
| `/fukugyo-timecard` | `python3 scripts/timecard.py today` | Record today's work |
| `/fukugyo-timecard-month [YYYY-MM]` | `python3 scripts/timecard.py month` | Monthly time summary |
| `/fukugyo-contract <file>` | `python3 scripts/contract.py read` | Analyze contract PDF |
| `/fukugyo-invoice [YYYY-MM]` | `python3 scripts/invoice.py create` | Generate invoice |
| `/fukugyo-payment` | `python3 scripts/payment.py check` | Check payments/send reminders |
| `/fukugyo-escalate <ID>` | `python3 scripts/escalate.py start` | Legal action documents |

## Data Architecture

All data is stored locally in `.fukugyo/` directory (excluded from git):

```
.fukugyo/
├── config.json       # User settings, client info, bank details
├── timecard.json     # Time tracking records
├── invoices.json     # Invoice registry
├── invoices/         # Generated invoice files
├── contracts/        # Contract analysis results
└── escalate/         # Legal documents
```

### Configuration Structure
The `config.json` follows the template in `templates/config.sample.json` with:
- Personal info (name, address, bank details)
- Client configurations (hourly rates, addresses)
- Slack integration settings
- URL patterns for Chrome history analysis
- Keywords for time tracking detection

## Integration Points

### Slack MCP Integration
When Slack MCP is available, timecard commands automatically:
1. Retrieve messages from configured channels
2. Set `FUKUGYO_SLACK_DATA` environment variable
3. Parse check-in/check-out keywords from messages

### freee MCP Integration
Optional accounting integration for automatic invoice registration.

## Development Commands

### Testing/Development
- Use `python3 scripts/<script>.py --help` to see available options
- Configuration can be tested with sample data from `templates/config.sample.json`

### File Operations
- All file paths should be absolute when passed to scripts
- PDF contract files are processed through AI analysis
- Generated documents are saved as both JSON (data) and Markdown (formatted)

## Security Considerations

- All sensitive data (bank details, client info) stays in `.fukugyo/config.json`
- Slack tokens are stored in Claude Code's MCP settings, not in project files
- Contract analysis results may contain sensitive business terms

## Localization

This tool is primarily designed for Japanese freelancers:
- All user-facing text is in Japanese
- Legal documents follow Japanese legal formats
- Tax calculations use Japanese rates (10% default)
- Bank integration assumes Japanese banking systems