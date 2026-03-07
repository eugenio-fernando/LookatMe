# CLAUDE.md

This file provides persistent context for Claude when working on the LookatMe repository.

Claude must read and follow this document before making any code changes.

---

# Project: LookatMe

LookatMe is a productivity web application that helps users manage:

- tasks
- workspaces
- messages
- learning items
- timers
- activity tracking

The application is deployed on Fly.io.

Production URL:
https://lookatme.fly.dev

---

# Technology Stack

Backend
- Python
- Flask
- Flask-SocketIO
- Prisma ORM (prisma-client-py)

Database
- SQLite
- Stored on Fly.io persistent volume

Deployment
- Docker
- Fly.io Machines

Frontend
- HTML templates
- CSS
- Vanilla JavaScript

Email (planned)
- Resend.com

---

# Repository Structure

LookatMe/

run.py  
Dockerfile  
fly.toml  
schema.prisma  
README.md  

app/

extensions.py  
models/  
routes/  
templates/  
static/  

services/ (future email services)

---

# Important Rules

Claude MUST follow these rules.

## Do not break production

The deployed application currently works.

Any changes must be incremental and safe.

Never introduce changes that could break the running deployment.

---

## Branch workflow

main  
production branch

dev  
development branch

All features must be implemented in `dev`.

Only merge to `main` once verified.

---

## Database persistence

The SQLite database must always be stored in the Fly volume.

Correct location:

/data/lookatme.db

Never store the database inside the container filesystem.

Prisma datasource must use:

file:/data/lookatme.db

---

## Deployment configuration

Fly configuration is defined in:

fly.toml

Important values:

internal_port = 8080

Application must listen on:

0.0.0.0:8080

---

# Authentication System

Authentication is implemented using Flask sessions.

Planned improvements:

- email verification
- magic login links
- password reset

Email provider:
Resend

---

# Email Architecture (Planned)

New module:

app/services/email_service.py

Responsibilities:

send_verification_email  
send_magic_login_link  
send_password_reset_email

Verification link format:

https://lookatme.fly.dev/verify/<token>

Magic login link format:

https://lookatme.fly.dev/login/<token>

---

# UI Goals

The interface must be:

- responsive
- mobile friendly
- usable on phones
- usable on tablets
- desktop optimized

Responsive breakpoints must be added.

---

# Code Quality Rules

Claude must:

- avoid large rewrites
- avoid introducing unnecessary dependencies
- maintain existing architecture
- keep Flask blueprint structure
- document new modules
- ensure code readability

---

# Git Workflow

When modifying the repository Claude must:

1. show planned changes
2. show file diffs
3. show git commands before executing them
4. commit logically grouped changes

---

# Tasks Claude Will Help With

Claude may assist with:

- backend features
- database migrations
- authentication improvements
- email integration
- UI responsiveness
- documentation
- deployment fixes

Claude must prioritize stability over speed.

---

# Deployment Command

Deployment is performed using:

fly deploy

Application status:

fly status -a lookatme

Logs:

fly logs -a lookatme

---

# Final Rule

If unsure about a change, Claude must ask before modifying critical components such as:

- schema.prisma
- Dockerfile
- fly.toml
- authentication routes